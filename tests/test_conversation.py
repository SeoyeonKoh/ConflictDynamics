import random
import threading
from copy import deepcopy
from dataclasses import dataclass, field

import pytest

from conflict_sim.conversation import TALK, WIKI, Participant, Session, run
from conflict_sim.models import Decision, Thread, Utterance

# Engine defaults live in Config; tests spell out the schedule they exercise.
SCHEDULE = {"rule": "bidding", "max_ticks": 12, "random_seed": 7}


def schedule(**overrides):
    return SCHEDULE | overrides


@dataclass(frozen=True)  # A session may call decide/speak; it must never assign to an agent.
class ScriptedAgent:
    name: str
    urge: float = 1.0
    availability: float = 1.0
    valence: float = 0.0
    arousal: float = 0.0
    observed: list[list[str]] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    threads: list[str] = field(default_factory=list)

    def decide(self, thread, instructions, *, seen, tick):
        self.threads.append(threading.current_thread().name)
        self.observed.append([u.id for u in thread.utterances[seen:]])
        self.instructions.append(instructions)
        return Decision(
            urge=self.urge,
            reply_to=thread.utterances[-1].id,
            reflection=f"{self.name}'s perspective after reading {len(self.observed)} times.",
            expression="neutral",
            importance=3,
            valence=self.valence,
            arousal=self.arousal,
        )

    def speak(self, thread, target, instructions, *, seen):
        self.instructions.append(instructions)
        return f"Reply from {self.name}"


def seed():
    return Thread(
        [
            Utterance(id="root", speaker="A", text="Source discussion", reply_to=None, timestamp=0),
            Utterance(
                id="seed-reply",
                speaker="B",
                text="Please check the source.",
                reply_to="root",
                timestamp=0,
            ),
        ]
    )


def session(agents, thread=None, *, kind="talk", seen=0, rng_seed=7, **overrides):
    options = {"rule": "bidding", "turns_per_tick": 1} | overrides
    return Session(
        id="s",
        kind=kind,
        participants=[Participant(agent, last_seen=seen) for agent in agents],
        thread=thread if thread is not None else seed(),
        rng=random.Random(rng_seed),
        instructions=TALK,
        **options,
    )


# --- the wiki wrapper keeps the old engine behaviour ---


@pytest.mark.parametrize("rule", ["round_robin", "random", "bidding", "event_driven"])
@pytest.mark.parametrize("limit", [1, 5])
def test_generated_post_cap_is_exact_even_in_the_middle_of_a_tick(rule, limit):
    result = run(
        [ScriptedAgent(name) for name in "ABC"], seed(), **schedule(rule=rule), max_utterances=limit
    )
    assert len(result.thread.utterances) == 2 + limit
    assert result.stop_reason == "max_utterances"
    assert sum(event["posted"] for event in result.decisions) == limit


@pytest.mark.parametrize("rule", ["round_robin", "random", "bidding", "event_driven"])
def test_live_updates_show_reflections_before_posts_without_changing_the_run(rule):
    snapshots = []

    def observe(result, message):
        snapshots.append((deepcopy(result), message))

    def simulate(callback=None):
        return run(
            [ScriptedAgent("A", urge=0), ScriptedAgent("B"), ScriptedAgent("C")],
            seed(),
            **schedule(rule=rule, max_ticks=2),
            on_update=callback,
        )

    assert simulate(observe) == simulate()
    assert len(snapshots[0][0].thread.utterances) == 2
    assert not snapshots[0][0].decisions
    assert any(
        len(result.thread.utterances) == 2
        and any(event.get("reflection") for event in result.decisions)
        for result, _ in snapshots
    )
    assert any(
        event.get("reflection") and event["urge"] == 0
        for result, _ in snapshots
        for event in result.decisions
    )
    assert snapshots[-1][0].ticks == 2


def test_initial_seed_and_later_posts_in_same_tick_are_not_lost():
    agents = [ScriptedAgent(name) for name in ["A", "B", "C"]]
    result = run(agents, seed(), **schedule(rule="round_robin", max_ticks=2))
    assert agents[0].observed[0] == ["root", "seed-reply"]
    assert len(agents[0].observed[1]) == 2  # B and C posted after A's first turn.
    assert [u.speaker for u in result.thread.utterances[2:]] == ["A", "B", "C"] * 2
    assert [u.timestamp for u in result.thread.utterances[2:]] == [1, 1, 1, 2, 2, 2]


def test_a_round_without_a_post_ends_the_conversation_at_once():
    """Nobody has anything unread after a quiet round, so nothing could ever revive it."""
    agents = [ScriptedAgent(name, urge=0) for name in ["A", "B", "C"]]
    result = run(agents, seed(), **schedule())
    assert len(result.thread.utterances) == 2
    assert result.stop_reason == "silence"
    assert result.ticks == 1
    assert all(len(agent.observed) == 1 for agent in agents)


def test_bidding_evaluates_same_snapshot_and_only_highest_urge_can_post():
    agents = [ScriptedAgent("A", 0.1), ScriptedAgent("B", 1), ScriptedAgent("C", 0.2)]
    result = run(agents, seed(), **schedule(rule="bidding", max_ticks=1))
    assert [u.speaker for u in result.thread.utterances[2:]] == ["B"]
    assert all(agent.observed == [["root", "seed-reply"]] for agent in agents)
    assert sum(event["posted"] for event in result.decisions) == 1


def test_unavailable_bidder_cannot_block_other_agents():
    agents = [ScriptedAgent("A", 1, 0), ScriptedAgent("B", 1), ScriptedAgent("C", 0)]
    result = run(agents, seed(), **schedule(rule="bidding", max_ticks=1))
    assert result.thread.utterances[-1].speaker == "B"


def test_bidding_ties_are_not_always_awarded_to_first_agent():
    winners = set()
    for rng_seed in range(12):
        agents = [ScriptedAgent(name) for name in ["A", "B", "C"]]
        result = run(agents, seed(), **schedule(rule="bidding", max_ticks=1, random_seed=rng_seed))
        winners.add(result.thread.utterances[-1].speaker)
    assert len(winners) > 1


def test_random_order_is_reproducible():
    def simulate(rng_seed):
        agents = [ScriptedAgent(name) for name in ["A", "B", "C"]]
        return run(agents, seed(), **schedule(rule="random", random_seed=rng_seed)).thread

    assert simulate(7) == simulate(7)
    assert simulate(7) != simulate(8)


def test_event_driven_only_reacts_to_new_replies_or_exact_mentions():
    thread = seed()
    agents = [ScriptedAgent("A"), ScriptedAgent("B"), ScriptedAgent("C")]
    thread.add(
        Utterance(
            id="event",
            speaker="B",
            text="@C please check. @Ann is another editor.",
            reply_to="root",
            timestamp=1,
        )
    )
    convo = session(agents, thread, rule="event_driven", seen=2)
    convo.step(2)
    assert [u.speaker for u in thread.utterances[3:]] == ["A", "B", "C"]
    # B is addressed by A's immediate reply to event; C was explicitly mentioned.


def test_event_driven_does_not_match_part_of_a_name():
    thread = seed()
    agents = [ScriptedAgent("Ann"), ScriptedAgent("D"), ScriptedAgent("C")]
    thread.add(
        Utterance(id="event", speaker="B", text="@Anna please check.", reply_to="root", timestamp=1)
    )
    session(agents, thread, rule="event_driven", seen=2).step(2)
    assert len(thread.utterances) == 3


@pytest.mark.parametrize("rule", ["round_robin", "random", "bidding", "event_driven"])
def test_zero_availability_never_generates(rule):
    agents = [ScriptedAgent(name, availability=0) for name in ["A", "B", "C"]]
    convo = session(agents, rule=rule)
    convo.step(1)
    assert convo.finished == "silence"
    assert len(convo.thread.utterances) == 2
    assert all(p.last_seen == 0 and not p.agent.observed for p in convo.participants)
    assert all("reflection" not in event for event in convo.decisions)


def test_null_target_still_produces_a_single_tree():
    class RootReplyAgent(ScriptedAgent):
        def decide(self, thread, instructions, *, seen, tick):
            return Decision(
                urge=1,
                reply_to=None,
                reflection="The root needs a reply.",
                expression="neutral",
                importance=3,
                valence=0,
                arousal=0,
            )

    agents = [RootReplyAgent(name) for name in ["A", "B", "C"]]
    result = run(agents, seed(), **schedule(max_ticks=1))
    assert all(u.reply_to == "root" for u in result.thread.utterances[2:])


def fixed_draws(monkeypatch, *draws):
    rng = random.Random(7)
    values = iter(draws)
    monkeypatch.setattr(rng, "random", lambda: next(values))
    monkeypatch.setattr(rng, "shuffle", lambda agents: None)
    monkeypatch.setattr("conflict_sim.conversation.random.Random", lambda seed: rng)


@pytest.mark.parametrize("rule", ["round_robin", "random", "bidding", "event_driven"])
def test_a_failed_gate_is_final_the_decision_is_not_retried(monkeypatch, rule):
    """Live speech: a judgement is one draw; nothing is kept to roll again later."""
    fixed_draws(monkeypatch, 0.9, 0.1)
    agents = [ScriptedAgent("A", 0.5), ScriptedAgent("B", 0), ScriptedAgent("C", 0)]
    result = run(agents, seed(), **schedule(rule=rule, max_ticks=4))
    assert len(result.thread.utterances) == 2 and result.stop_reason == "silence"
    assert result.ticks == 1 and len(agents[0].observed) == 1
    events = [event for event in result.decisions if event["agent"] == "A"]
    assert len(events) == 1 and events[0]["reason"] == "probability_gate"
    assert "decision_source" not in events[0] and "decision_tick" not in events[0]


def test_bidding_losers_judge_again_only_after_the_winner_posts(monkeypatch):
    fixed_draws(monkeypatch, 0.1, 0.9)
    agents = [ScriptedAgent("A", 0.8), ScriptedAgent("B", 0.4), ScriptedAgent("C", 0)]
    result = run(agents, seed(), **schedule(max_ticks=3))
    assert [u.speaker for u in result.thread.utterances[2:]] == ["A"]
    assert len(agents[1].observed) == 2  # B read A's post and judged it afresh
    assert agents[1].observed[1] == [result.thread.utterances[-1].id]
    loser = [event for event in result.decisions if event["agent"] == "B"]
    assert [event["reason"] for event in loser] == ["not_selected", "probability_gate"]
    assert loser[0]["reflection"] != loser[1]["reflection"]


def test_a_new_post_makes_an_agent_judge_again_and_zero_urge_is_silence(monkeypatch):
    class RevisingAgent(ScriptedAgent):
        def decide(self, thread, instructions, *, seen, tick):
            if self.observed:
                object.__setattr__(self, "urge", 0)
            return super().decide(thread, instructions, seen=seen, tick=tick)

    fixed_draws(monkeypatch, 0.9, 0.1)
    agents = [RevisingAgent("A", 0.8), ScriptedAgent("B", 0), ScriptedAgent("C", 1)]
    result = run(agents, seed(), **schedule(rule="round_robin", max_ticks=3))
    # A fails the gate; C posts; A reads C and judges afresh, this time with nothing to say.
    assert result.thread.utterances[-1].speaker == "C"
    events = [event for event in result.decisions if event["agent"] == "A"]
    assert [event["reason"] for event in events] == ["probability_gate", "no_urge"]
    assert events[1]["reflection"] != events[0]["reflection"]
    assert len(agents[0].observed) == 2
    assert result.stop_reason == "silence" and result.ticks == 2


def test_event_driven_agents_judge_again_only_when_addressed(monkeypatch):
    fixed_draws(monkeypatch, 0.9, 0.1)
    agents = [ScriptedAgent("A", 0.8), ScriptedAgent("B", 0), ScriptedAgent("C", 1)]
    result = run(agents, seed(), **schedule(rule="event_driven", max_ticks=3))
    # C's reply to B is no event for A: A's lost draw is not revisited.
    assert [u.speaker for u in result.thread.utterances[2:]] == ["C"]
    events = [event for event in result.decisions if event["agent"] == "A"]
    assert [event["reason"] for event in events] == ["probability_gate", "no_event"]
    assert len(agents[0].observed) == 1


def test_wiki_wrapper_passes_wiki_instructions_and_starts_from_one_utterance():
    agents = [ScriptedAgent(name) for name in "ABC"]
    result = run(agents, Thread(seed().utterances[:1]), **schedule(rule="round_robin", max_ticks=1))
    assert len(result.thread.utterances) == 4
    assert result.thread.utterances[-1].timestamp == 1
    assert agents[0].instructions == [WIKI.decide, WIKI.speak]
    assert "Wikipedia" in WIKI.decide and "Wikipedia" not in TALK.decide


# --- Session.step: rounds, session kinds, end conditions, outcomes ---


def test_step_repeats_the_rule_turns_per_tick_times_within_one_tick():
    agents = [ScriptedAgent(name) for name in "ABC"]
    convo = session(agents, rule="round_robin", turns_per_tick=3)
    events = convo.step(5)
    assert len(convo.thread.utterances) == 2 + 9
    assert {u.timestamp for u in convo.thread.utterances[2:]} == {5}
    assert len(events) == 9 and all(event["session"] == "s" for event in events)
    assert convo.finished is None and not hasattr(convo, "silence")


def test_a_quiet_round_ends_the_tick_and_the_session():
    agents = [ScriptedAgent(name, urge=0) for name in "ABC"]
    convo = session(agents, rule="round_robin", turns_per_tick=12)
    convo.step(1)
    assert all(len(agent.observed) == 1 for agent in agents)
    assert len(convo.decisions) == 3 and convo.finished == "silence"
    with pytest.raises(ValueError):
        convo.step(2)


def test_message_session_ends_after_one_round_without_a_post():
    convo = session([ScriptedAgent("A", urge=0), ScriptedAgent("B", urge=0)], kind="message")
    convo.step(1)
    assert convo.finished == "silence"
    assert convo.public is False


def test_message_session_keeps_going_while_someone_posts():
    convo = session([ScriptedAgent("A"), ScriptedAgent("B")], kind="message", turns_per_tick=2)
    convo.step(1)
    assert convo.finished is None
    assert len(convo.thread.utterances) == 4


def test_finish_closes_a_session_from_outside():
    convo = session([ScriptedAgent(name) for name in "ABC"])
    convo.step(1)
    convo.finish("phase_end")
    assert convo.finished == "phase_end"
    with pytest.raises(ValueError):
        convo.step(2)


def test_outcomes_weigh_each_post_by_the_listener_s_own_appraisal():
    """A post aimed at me counts with how I judged it right after (the valence and arousal of my
    next judgement), not with how its author felt: in the real runs the author's own valence set
    the listener's relation, so an anxious Blake lowered Erin's view of Blake."""
    agents = [
        ScriptedAgent("A", valence=-0.5, arousal=0.8),
        ScriptedAgent("B", urge=0, valence=0.6, arousal=0.1),
        ScriptedAgent("C", urge=0),
    ]
    thread = Thread([Utterance(id="root", speaker="B", text="Status?", reply_to=None, timestamp=0)])
    convo = session(agents, thread, rule="round_robin")
    convo.step(1)  # A replies to B's root; B then judges it.
    outcomes = convo.outcomes()
    assert set(outcomes) == {"A", "B", "C"}
    assert [(r.speaker, r.valence, r.arousal) for r in outcomes["B"].received] == [("A", 0.6, 0.1)]
    assert outcomes["A"].received == [] and outcomes["C"].received == []
    assert outcomes["B"].session_id == "s" and outcomes["B"].public is True
    assert outcomes["B"].refused == [] and outcomes["B"].opposed == []


def test_outcomes_count_mentions_but_not_seed_posts_without_a_decision():
    class MentioningAgent(ScriptedAgent):
        def speak(self, thread, target, instructions, *, seen):
            return "@C what do you think?"

    agents = [
        MentioningAgent("A", valence=0.4, arousal=0.2),
        ScriptedAgent("B", 0, valence=-0.3),
        ScriptedAgent("C", 0, valence=0.2),
    ]
    convo = session(agents, rule="round_robin")
    convo.step(1)
    outcomes = convo.outcomes()
    assert [(r.speaker, r.valence) for r in outcomes["C"].received] == [("A", 0.2)]
    assert [(r.speaker, r.valence) for r in outcomes["B"].received] == [("A", -0.3)]  # A replied
    assert outcomes["A"].received == []  # B's seed reply to A's root carries no decision.


def test_a_post_the_listener_never_judged_counts_for_nothing():
    agents = [ScriptedAgent("A", valence=-0.9), ScriptedAgent("B", availability=0)]
    thread = Thread([Utterance(id="root", speaker="B", text="Status?", reply_to=None, timestamp=0)])
    convo = session(agents, thread, rule="round_robin")
    convo.step(1)  # A replies; B is unavailable and never reads it.
    assert convo.outcomes()["B"].received == []


def test_bidding_judges_in_parallel_but_posts_in_order():
    from concurrent.futures import ThreadPoolExecutor

    def run_with(pool):
        agents = [ScriptedAgent("A", 0.9), ScriptedAgent("B", 0.4), ScriptedAgent("C", 0.7)]
        session = Session(
            id="root", kind="talk", participants=[Participant(a) for a in agents], thread=seed(),
            rng=random.Random(3), instructions=TALK, rule="bidding", turns_per_tick=3, pool=pool,
        )  # fmt: skip
        events = session.step(1)
        posts = [u.model_dump() for u in session.thread.utterances]
        threads = {name for a in agents for name in a.threads}
        return posts, events, [len(a.observed) for a in agents], threads

    with ThreadPoolExecutor(max_workers=3) as pool:
        parallel = run_with(pool)
    sequential = run_with(None)
    assert parallel[:3] == sequential[:3]
    assert (
        len(sequential[3]) == 1 and len(parallel[3]) > 1
    )  # the first round really ran in the pool
