import json
from pathlib import Path

import pytest

from conflict_sim.agent import Agent
from conflict_sim.conversation import TALK, WIKI
from conflict_sim.models import (
    AgentSpec,
    BlockedTask,
    Config,
    Message,
    Outcome,
    PlanItem,
    Received,
    Rejected,
    TaskView,
    Thread,
    Utterance,
    View,
)

ROOT = Path(__file__).resolve().parents[1]


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def complete(self, **request):
        self.requests.append(request)
        return self.response

    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


def seed():
    return Thread(
        [
            Utterance(
                id="root", speaker="A", text="Please check this source.", reply_to=None, timestamp=0
            )
        ]
    )


def config(**overrides):
    fields = dict(
        n_agents=3,
        agents=[AgentSpec(name=n, persona="Works.") for n in "ABC"],
        model_decide="small",
        model_speak="large",
        persona_placement="payload",
    )
    return Config(**(fields | overrides))


def make_agent(llm, **overrides):
    spec = AgentSpec(
        name="B", persona="Prefers independent sources. Writes concise replies.", availability=0.8
    )
    return Agent(spec, config(**overrides), llm)


def view(**fields):
    return View(
        **{
            "agent": "B",
            "day": 0,
            "tick": 5,
            "phase": "morning",
            "place": "dev-office",
            "places": {"lobby": "lobby", "dev-office": "office", "cafeteria": "cafeteria"},
            "tasks": [TaskView(id="api", description="Ship it", owner="B", progress=0.2, due=28)],
            "stress": 0.1,
            "mood": 0.0,
        }
        | fields
    )


def action_json(**fields):
    return json.dumps(
        {
            "kind": "rest",
            "expression": "tired",
            "reflection": "Waiting on the spec.",
            "importance": 4,
            "valence": -0.3,
            "arousal": 0.3,
        }
        | fields
    )


def decision_json(**fields):
    return json.dumps(
        {
            "urge": 0,
            "reply_to": None,
            "reflection": "Nothing new.",
            "expression": "neutral",
            "importance": 3,
            "valence": 0,
            "arousal": 0,
        }
        | fields
    )


def test_decide_parses_valid_json_and_uses_only_the_decision_model():
    llm = FakeLLM(decision_json(urge=0.6, reply_to="root", reflection="I need a citation."))
    agent = make_agent(llm)
    decision = agent.decide(seed(), WIKI.decide, seen=0, tick=1)
    assert (decision.urge, decision.reply_to) == (0.6, "root")
    assert agent.reflections == ["I need a citation."]
    assert len(llm.requests) == 1
    assert llm.requests[0]["model"] == "small"
    assert llm.requests[0]["json_mode"] is True
    payload = json.loads(llm.requests[0]["prompt"])
    assert payload["utterances"][0]["text"] == "Please check this source."


@pytest.mark.parametrize(
    "response",
    [
        "not json",
        "[]",
        "{}",
        '{"urge": true, "reply_to": null, "reflection": "Still unsure."}',
        '{"urge": -0.1, "reply_to": null, "reflection": "Still unsure."}',
        '{"urge": 1.1, "reply_to": null, "reflection": "Still unsure."}',
        '{"urge": NaN, "reply_to": null, "reflection": "Still unsure."}',
        '{"urge": "0.5", "reply_to": null, "reflection": "Still unsure."}',
        '{"urge": 0.5, "reply_to": 12, "reflection": "Still unsure."}',
        '{"urge": 0.5, "reply_to": "missing", "reflection": "Still unsure."}',
        '{"urge": 0.5, "reply_to": null}',
        '{"urge": 0.5, "reply_to": null, "reflection": " "}',
        '{"urge": 0.5, "reply_to": null, "reflection": "Still unsure."}',
        decision_json(expression="furious"),
        decision_json(importance=0),
    ],
)
def test_invalid_decisions_fail_instead_of_becoming_silence(response):
    agent = make_agent(FakeLLM(response))
    agent.observe("An earlier concern.", tick=0, type="reflection")
    with pytest.raises(ValueError):
        agent.decide(seed(), WIKI.decide, seen=0, tick=1)
    assert agent.reflections == ["An earlier concern."]


def test_speak_includes_target_outside_recent_context_and_uses_generation_model():
    thread = seed()
    for index in range(12):
        thread.add(
            Utterance(id=str(index), speaker="A", text="Later text", reply_to="root", timestamp=1)
        )
    llm = FakeLLM("  Could you provide the original citation?  ")
    text = make_agent(llm).speak(thread, "root", WIKI.speak, seen=0)
    assert text == "Could you provide the original citation?"
    assert llm.requests[0]["model"] == "large"
    payload = json.loads(llm.requests[0]["prompt"])
    assert payload["target"]["text"] == "Please check this source."


def test_empty_speech_is_an_error():
    with pytest.raises(ValueError):
        make_agent(FakeLLM(" ")).speak(seed(), "root", WIKI.speak, seen=0)


def test_small_context_keeps_unread_text_until_it_has_been_seen():
    thread = seed()
    thread.add(
        Utterance(
            id="reply",
            speaker="C",
            text="An independent source is available.",
            reply_to="root",
            timestamp=0,
        )
    )
    llm = FakeLLM(decision_json(urge=0.5, reply_to="reply", reflection="I see a new source."))
    agent = make_agent(llm, context_size=1)
    agent_seen = 0
    agent.decide(thread, WIKI.decide, seen=agent_seen, tick=1)
    payload = json.loads(llm.requests[-1]["prompt"])
    assert [u["id"] for u in payload["utterances"]] == ["root", "reply"]
    assert payload["utterances"][0]["text"] == "Please check this source."

    agent_seen = 2
    thread.add(
        Utterance(
            id="new", speaker="C", text="Here is the citation.", reply_to="reply", timestamp=1
        )
    )
    agent.decide(thread, WIKI.decide, seen=agent_seen, tick=1)
    payload = json.loads(llm.requests[-1]["prompt"])
    assert [u["id"] for u in payload["utterances"]] == ["new"]


@pytest.mark.parametrize("mode", ["summary", "full"])
def test_private_memory_is_updated_even_when_silent_and_passed_to_speech(mode):
    llm = FakeLLM("")
    agent = make_agent(llm, memory_mode=mode)
    reflections = [
        "I doubt the source.",
        "The source helps, but wording remains disputed.",
        "I accept the revised wording and have nothing to add.",
    ]
    for index, reflection in enumerate(reflections):
        llm.response = decision_json(reflection=reflection)
        agent.decide(seed(), WIKI.decide, seen=0, tick=1)
        payload = json.loads(llm.requests[-1]["prompt"])
        previous = reflections[:index]
        assert payload["private_memory"] == (previous[-1:] if mode == "summary" else previous)
    assert agent.reflections == reflections

    llm.response = "The wording now matches the source."
    agent.speak(seed(), "root", WIKI.speak, seen=0)
    payload = json.loads(llm.requests[-1]["prompt"])
    assert payload["private_memory"] == (reflections[-1:] if mode == "summary" else reflections)
    assert agent.reflections == reflections

    other = make_agent(llm)
    other.speak(seed(), "root", WIKI.speak, seen=0)
    assert json.loads(llm.requests[-1]["prompt"])["private_memory"] == []
    assert len(llm.requests) == 5  # Three decisions, two speeches; no separate memory call.


def test_memory_mode_none_records_reflections_without_feeding_them_back():
    llm = FakeLLM("")
    agent = make_agent(llm, memory_mode="none")
    for reflection in ["I doubt the source.", "The wording still misreads it."]:
        llm.response = decision_json(reflection=reflection)
        agent.decide(seed(), WIKI.decide, seen=0, tick=1)
        assert json.loads(llm.requests[-1]["prompt"])["private_memory"] == []
    llm.response = "Comment."
    agent.speak(seed(), "root", WIKI.speak, seen=0)
    assert json.loads(llm.requests[-1]["prompt"])["private_memory"] == []
    # The log still gets every reflection, so the ablation keeps the same decision schema.
    assert agent.reflections == ["I doubt the source.", "The wording still misreads it."]


def test_payload_placement_keeps_the_persona_in_the_payload():
    llm = FakeLLM(decision_json(urge=0.2))
    agent = make_agent(llm)
    agent.decide(seed(), WIKI.decide, seen=0, tick=1)
    llm.response = "Comment."
    agent.speak(seed(), "root", WIKI.speak, seen=0)
    for request in llm.requests:
        assert "Prefers independent sources" not in request["system"]
        assert json.loads(request["prompt"])["persona"] == agent.persona


def test_system_placement_moves_the_persona_out_of_the_payload():
    llm = FakeLLM(decision_json(urge=0.2))
    agent = make_agent(llm, persona_placement="system")
    agent.decide(seed(), WIKI.decide, seen=0, tick=1)
    llm.response = "Comment."
    agent.speak(seed(), "root", WIKI.speak, seen=0)
    assert len(llm.requests) == 2
    for request in llm.requests:
        assert request["system"].startswith("You are B. Prefers independent sources.")
        payload = json.loads(request["prompt"])
        assert "persona" not in payload
        assert payload["speaker"] == "B"
    assert "Return only a JSON object" in llm.requests[0]["system"]
    assert "Return only the comment text" in llm.requests[1]["system"]


def test_decide_prompt_asks_for_the_session_fields_and_keeps_impressions():
    from conflict_sim import agent
    from conflict_sim.conversation import MESSAGE

    assert agent.PROMPT_VERSION == "3"
    for kind in [WIKI, TALK, MESSAGE]:
        for name in ["expression", "importance", "valence", "arousal"]:
            assert f'"{name}"' in kind.decide
        assert "revise earlier impressions" not in kind.decide
        assert "Prior impressions can be mistaken" not in kind.decide
    source = (ROOT / "src/conflict_sim/agent/agent.py").read_text()
    assert "Wikipedia" not in source and "editor" not in source


def test_the_session_supplies_the_instructions_the_agent_sends():
    llm = FakeLLM(decision_json())
    agent = make_agent(llm)
    agent.decide(seed(), TALK.decide, seen=0, tick=1)
    llm.response = "Sure."
    agent.speak(seed(), "root", TALK.speak, seen=0)
    assert llm.requests[0]["system"] == TALK.decide
    assert llm.requests[1]["system"] == TALK.speak


def test_a_decision_becomes_a_reflection_record_about_the_speakers_read():
    thread = seed()
    thread.add(Utterance(id="r", speaker="C", text="No.", reply_to="root", timestamp=2))
    agent = make_agent(
        FakeLLM(decision_json(reflection="C is blunt.", valence=-0.5, expression="annoyed"))
    )
    agent.decide(thread, WIKI.decide, seen=0, tick=3)
    record = agent.memory.records[-1]
    assert (record.type, record.subjects, record.valence, record.created_tick) == (
        "reflection",
        ["A", "C"],
        -0.5,
        3,
    )
    assert agent.state.expression == "annoyed"


def test_plan_day_asks_once_and_stores_the_blocks_and_a_plan_record():
    llm = FakeLLM(
        json.dumps(
            {
                "plan": [
                    {"kind": "move", "place": "dev-office", "until": 1, "text": "Settle in."},
                    {"kind": "work", "task": "api", "until": 16, "text": "Build the API."},
                    {"kind": "eat", "place": "cafeteria", "until": 20, "text": "Lunch."},
                    {"kind": "work", "task": "api", "until": 32, "text": "Finish the API."},
                ]
            }
        )
    )
    agent = make_agent(llm)
    items = agent.plan_day(view(tick=0, phase="arrival", place="lobby"), tick=0)
    assert [i.kind for i in items] == ["move", "work", "eat", "work"] and agent.plan == items
    payload = json.loads(llm.requests[0]["prompt"])
    assert (
        "tasks" in payload and "view" not in payload and payload["places"]["dev-office"] == "office"
    )
    assert (
        agent.memory.records[-1].type == "plan"
        and "Build the API." in agent.memory.records[-1].description
    )


def test_act_follows_the_plan_without_calling_the_llm():
    llm = FakeLLM(action_json())
    agent = make_agent(llm)
    agent.plan = [
        PlanItem(kind="move", place="dev-office", until=1, text="Settle in."),
        PlanItem(kind="work", task="api", until=16, text="Build the API."),
    ]
    action = agent.act(view(tick=5), tick=5)
    assert (action.kind, action.task, action.reflection, action.expression) == (
        "work",
        "api",
        "Build the API.",
        "neutral",
    )
    assert llm.requests == [] and agent.memory.records == []


@pytest.mark.parametrize(
    "trigger",
    [
        {"inbox": [Message(sender="A", text="Any update?", tick=4, session_id="dm:A:B:0")]},
        {"blocked": [BlockedTask(task="api", waiting_on="spec", owner="A", since_tick=3, due=28)]},
        {
            "rejected": Rejected(
                action=json.loads(action_json(kind="work", task="api")),
                reason="cannot work in lobby",
            )
        },
        {"tasks": []},  # plan exhausted: nothing left to follow
    ],
)
def test_act_reacts_through_the_llm_when_the_view_is_not_in_the_plan(trigger):
    llm = FakeLLM(action_json(kind="message", target="A", text="Any news on the spec?"))
    agent = make_agent(llm)
    agent.plan = (
        []
        if "tasks" in trigger
        else [PlanItem(kind="work", task="api", until=16, text="Build the API.")]
    )
    action = agent.act(view(**trigger), tick=5)
    assert (action.kind, action.target) == ("message", "A")
    payload = json.loads(llm.requests[0]["prompt"])
    assert payload["view"]["tick"] == 5 and payload["manager"] is None
    assert agent.state.expression == "tired"
    assert agent.memory.records[-1].type == "action" and agent.memory.records[-1].valence == -0.3


def test_perceive_records_faces_and_messages_without_an_llm_call():
    llm = FakeLLM("")
    agent = make_agent(llm)
    records = agent.perceive(
        view(
            present={"A": "annoyed", "C": "neutral"},
            inbox=[Message(sender="C", text="Lunch?", tick=4, session_id="dm:B:C:0")],
        ),
        tick=5,
    )
    assert [r.description for r in records] == [
        "A looks annoyed in the dev-office.",
        "C wrote to me: Lunch?",
    ]
    assert (
        records[0].valence == -0.6 and records[0].importance == 3 and records[0].subjects == ["A"]
    )
    assert records[1].subjects == ["C", "B"] and records[1].session_id == "dm:B:C:0"
    assert llm.requests == []


def test_apply_outcome_updates_state_and_files_a_grievance_record():
    agent = make_agent(FakeLLM(""))
    outcome = Outcome(
        session_id="talk:3",
        public=True,
        received=[Received(speaker="A", valence=-1, arousal=0.5)],
        refused=["A"],
    )
    events = agent.apply_outcome(outcome, tick=7)
    link = agent.state.relations["A"]
    assert link.relation == pytest.approx((0.2 * -1 - 0.15) * 1.5)
    assert len(link.grievances) == 1 and agent.memory.records[-1].id == link.grievances[0]
    assert "refused my request in front of others" in agent.memory.records[-1].description
    assert events == [
        {
            "a": "B",
            "b": "A",
            "relation_delta": pytest.approx(-0.525),
            "grievance": link.grievances[0],
        }
    ]


def test_end_tick_recomputes_mood_from_the_window_and_reflects_when_due():
    llm = FakeLLM(
        json.dumps(
            {
                "insights": [
                    {
                        "text": "A blocks me.",
                        "evidence": [],
                        "importance": 6,
                        "valence": -0.6,
                        "arousal": 0.4,
                        "subjects": ["A"],
                    }
                ]
            }
        )
    )
    agent = make_agent(llm, memory={"relation_reflect_threshold": -1})
    agent.observe("A refused.", tick=2, valence=-0.7, subjects=["A"])
    agent.observe("A ignored me.", tick=3, valence=-0.5, subjects=["A"])
    new = agent.end_tick(tick=3)
    assert agent.state.mood == pytest.approx(-0.6)
    assert [r.description for r in new] == ["A blocks me."]
    assert agent.state.relations["A"].summary == "A blocks me."
    assert agent.snapshot()["state"]["relations"]["A"]["summary"] == "A blocks me."


def test_a_block_whose_task_is_not_blocked_is_followed_even_while_another_task_waits():
    llm = FakeLLM(action_json())
    agent = make_agent(llm)
    agent.plan = [PlanItem(kind="move", place="dev-office", until=1, text="Settle in.")]
    blocked = [BlockedTask(task="api", waiting_on="spec", owner="A", since_tick=0, due=28)]
    action = agent.act(view(tick=0, blocked=blocked), tick=0)
    assert (action.kind, action.place) == ("move", "dev-office") and llm.requests == []


def test_a_refused_block_is_dropped_so_the_plan_moves_on():
    llm = FakeLLM(action_json())
    agent = make_agent(llm)
    agent.plan = [
        PlanItem(kind="work", task="api", until=16, text="Build the API."),
        PlanItem(kind="rest", until=32, text="Wind down."),
    ]
    refused = Rejected(
        action=json.loads(action_json(kind="work", task="api")), reason="api is already done"
    )
    agent.act(view(tick=5, rejected=refused), tick=5)  # reacts once through the LLM
    assert [i.kind for i in agent.plan] == ["rest"]
    action = agent.act(view(tick=6), tick=6)
    assert action.kind == "rest" and len(llm.requests) == 1
