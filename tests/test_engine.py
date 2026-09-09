from dataclasses import dataclass, field

import pytest

from conflict_sim.engine import RunConfig, run
from conflict_sim.models import Decision, Thread, Utterance


@dataclass
class ScriptedAgent:
    name: str
    urge: float = 1.0
    availability: float = 1.0
    last_seen: int = 0
    observed: list[list[str]] = field(default_factory=list)

    def decide(self, thread):
        self.observed.append([u.id for u in thread.utterances[self.last_seen :]])
        return Decision(urge=self.urge, reply_to=thread.utterances[-1].id)

    def speak(self, thread, target):
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


def test_initial_seed_and_later_posts_in_same_tick_are_not_lost():
    agents = [ScriptedAgent(name) for name in ["A", "B", "C"]]
    result = run(agents, seed(), RunConfig(rule="round_robin", max_ticks=2))
    assert agents[0].observed[0] == ["root", "seed-reply"]
    assert len(agents[0].observed[1]) == 2  # B and C posted after A's first turn.
    assert [u.speaker for u in result.thread.utterances[2:]] == ["A", "B", "C"] * 2
    assert [u.timestamp for u in result.thread.utterances[2:]] == [1, 1, 1, 2, 2, 2]


def test_silence_stops_without_generating_or_redeciding_old_posts():
    agents = [ScriptedAgent(name, urge=0) for name in ["A", "B", "C"]]
    result = run(agents, seed(), RunConfig(silence_limit=2))
    assert len(result.thread.utterances) == 2
    assert result.stop_reason == "silence"
    assert result.ticks == 2
    assert all(len(agent.observed) == 1 for agent in agents)


def test_bidding_evaluates_same_snapshot_and_only_highest_urge_can_post():
    agents = [ScriptedAgent("A", 0.1), ScriptedAgent("B", 1), ScriptedAgent("C", 0.2)]
    result = run(agents, seed(), RunConfig(rule="bidding", max_ticks=1))
    assert [u.speaker for u in result.thread.utterances[2:]] == ["B"]
    assert all(agent.observed == [["root", "seed-reply"]] for agent in agents)
    assert sum(event["posted"] for event in result.decisions) == 1


def test_unavailable_bidder_cannot_block_other_agents():
    agents = [ScriptedAgent("A", 1, 0), ScriptedAgent("B", 1), ScriptedAgent("C", 0)]
    result = run(agents, seed(), RunConfig(rule="bidding", max_ticks=1))
    assert result.thread.utterances[-1].speaker == "B"


def test_bidding_ties_are_not_always_awarded_to_first_agent():
    winners = set()
    for rng_seed in range(12):
        agents = [ScriptedAgent(name) for name in ["A", "B", "C"]]
        result = run(agents, seed(), RunConfig(rule="bidding", max_ticks=1, random_seed=rng_seed))
        winners.add(result.thread.utterances[-1].speaker)
    assert len(winners) > 1


def test_random_order_is_reproducible():
    def simulate(rng_seed):
        agents = [ScriptedAgent(name) for name in ["A", "B", "C"]]
        return run(agents, seed(), RunConfig(rule="random", random_seed=rng_seed)).thread

    assert simulate(7) == simulate(7)
    assert simulate(7) != simulate(8)


def test_event_driven_only_reacts_to_new_replies_or_exact_mentions():
    thread = seed()
    agents = [ScriptedAgent("A"), ScriptedAgent("B"), ScriptedAgent("C")]
    for agent in agents:
        agent.last_seen = 2
    thread.add(
        Utterance(
            id="event",
            speaker="B",
            text="@C please check. @Ann is another editor.",
            reply_to="root",
            timestamp=1,
        )
    )
    result = run(agents, thread, RunConfig(rule="event_driven", max_ticks=1))
    assert [u.speaker for u in result.thread.utterances[3:]] == ["A", "B", "C"]
    # B is addressed by A's immediate reply to event; C was explicitly mentioned.


def test_event_driven_does_not_match_part_of_a_name():
    thread = seed()
    agents = [ScriptedAgent("Ann"), ScriptedAgent("D"), ScriptedAgent("C")]
    for agent in agents:
        agent.last_seen = 2
    thread.add(
        Utterance(id="event", speaker="B", text="@Anna please check.", reply_to="root", timestamp=1)
    )
    result = run(agents, thread, RunConfig(rule="event_driven", max_ticks=1))
    assert len(result.thread.utterances) == 3


@pytest.mark.parametrize("rule", ["round_robin", "random", "bidding", "event_driven"])
def test_zero_availability_never_generates(rule):
    agents = [ScriptedAgent(name, availability=0) for name in ["A", "B", "C"]]
    result = run(agents, seed(), RunConfig(rule=rule))
    assert len(result.thread.utterances) == 2


def test_null_target_still_produces_a_single_tree():
    class RootReplyAgent(ScriptedAgent):
        def decide(self, thread):
            return Decision(urge=1, reply_to=None)

    agents = [RootReplyAgent(name) for name in ["A", "B", "C"]]
    result = run(agents, seed(), RunConfig(max_ticks=1))
    assert all(u.reply_to == "root" for u in result.thread.utterances[2:])
