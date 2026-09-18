"""The rule-based demo backend: it must answer every prompt kind without an API."""

import json
import math

import pytest

from conflict_sim.llm import DemoBackend, expression_for
from conflict_sim.models import Action, Decision


def call(backend, payload, json_mode=True):
    return backend.complete(
        system="", prompt=json.dumps(payload), model="demo", temperature=0, json_mode=json_mode
    )


def view(**overrides):
    return {
        "agent": "Blake",
        "day": 0,
        "tick": 9,
        "phase": "morning",
        "place": "dev-office",
        "present": {},
        "tasks": [
            {
                "id": "api",
                "description": "Ship API",
                "owner": "Blake",
                "progress": 0.2,
                "due": 28,
                "depends_on": [],
            },
            {
                "id": "docs",
                "description": "Docs",
                "owner": "Blake",
                "progress": 0.0,
                "due": 20,
                "depends_on": [],
            },
        ],
        "blocked": [],
        "resources": {},
        "inbox": [],
        "unanswered": [],
        "rejected": None,
        "stress": 0.1,
        "mood": 0.0,
    } | overrides


def act(backend, **overrides):
    return Action.model_validate_json(call(backend, {"view": view(**overrides), "manager": "Alex"}))


def test_embeddings_are_deterministic_unit_vectors_of_fixed_size():
    backend = DemoBackend()
    first, second, other = backend.embed(["deadline moved", "deadline moved", "lunch"])
    assert first == second
    assert first != other
    assert len(first) == len(other) == DemoBackend.EMBED_DIM
    assert math.isclose(math.sqrt(sum(x * x for x in first)), 1.0, abs_tol=1e-9)
    assert backend.embed([]) == []


def test_session_decision_replies_to_the_latest_post_with_all_fields():
    payload = {
        "editor": "B",
        "utterances": [
            {"id": "root", "speaker": "A", "text": "Hi", "reply_to": None, "timestamp": 0},
            {"id": "r1", "speaker": "C", "text": "Hello", "reply_to": "root", "timestamp": 1},
        ],
        "unread_ids": ["r1"],
    }
    decision = Decision.model_validate_json(call(DemoBackend(), payload))
    assert decision.reply_to == "r1"
    assert decision.urge > 0
    assert decision.expression == "neutral"
    assert call(DemoBackend(), payload, json_mode=False).strip()


def test_act_works_on_the_earliest_due_task():
    action = act(DemoBackend())
    assert (action.kind, action.task) == ("work", "docs")


def test_act_rests_when_nothing_is_left():
    tasks = [view()["tasks"][0] | {"progress": 1.0}]
    assert act(DemoBackend(), tasks=tasks).kind == "rest"
    assert act(DemoBackend(), tasks=[]).kind == "rest"


def test_act_goes_to_eat_at_lunch_and_talks_once_others_are_there_too():
    places = {"dev-office": "office", "pantry": "pantry"}
    action = act(DemoBackend(), phase="lunch", places=places)
    assert (action.kind, action.place) == ("eat", "pantry")
    at_desk = act(DemoBackend(), phase="lunch", places=places, present={"Casey": "pleased"})
    assert at_desk.kind == "eat"  # company at the desk is not lunch company
    at_lunch = act(
        DemoBackend(), phase="lunch", places=places, place="pantry", present={"Casey": "pleased"}
    )
    assert (at_lunch.kind, bool(at_lunch.text)) == ("talk", True)


def test_act_nudges_the_owner_then_reports_to_the_manager_when_blocked():
    backend = DemoBackend(blocked_nudge_ticks=2, blocked_report_ticks=4)
    blocked = [{"task": "api", "waiting_on": "spec", "owner": "Alex", "since_tick": 7, "due": 28}]
    assert act(backend, blocked=blocked, tick=8).kind == "work"
    nudge = act(backend, blocked=blocked, tick=9)
    assert (nudge.kind, nudge.target, bool(nudge.text)) == ("message", "Alex", True)
    assert act(backend, blocked=blocked, tick=10).kind == "work"
    report = act(backend, blocked=blocked, tick=11)
    assert (report.kind, report.target, bool(report.text)) == ("report", "Alex", True)


def test_act_skips_the_report_without_a_manager():
    backend = DemoBackend(blocked_nudge_ticks=2, blocked_report_ticks=4)
    blocked = [{"task": "api", "waiting_on": "spec", "owner": "Alex", "since_tick": 7, "due": 28}]
    payload = {"view": view(blocked=blocked, tick=11), "manager": None}
    assert Action.model_validate_json(call(backend, payload)).kind == "work"


@pytest.mark.parametrize(
    "stress,mood,label",
    [
        (0.0, 0.0, "neutral"),
        (0.7, 0.0, "anxious"),
        (0.0, -0.6, "angry"),
        (0.0, -0.3, "annoyed"),
        (0.4, 0.0, "tired"),
        (0.0, 0.5, "amused"),
        (0.0, 0.2, "pleased"),
        (0.9, -0.9, "anxious"),
    ],
)
def test_expression_bands_map_internal_state_to_a_face(stress, mood, label):
    assert expression_for(stress, mood) == label
    action = act(DemoBackend(), stress=stress, mood=mood)
    assert action.expression == label


def test_daily_plan_is_executable_blocks_that_cover_the_day():
    from conflict_sim.models import PlanItem

    payload = {
        "speaker": "Blake", "day": 0, "tick": 0, "last_tick": 31, "place": "lobby",
        "places": {"lobby": "lobby", "dev-office": "office", "cafeteria": "cafeteria"},
        "tasks": view()["tasks"],
    }  # fmt: skip
    plan = [PlanItem.model_validate(i) for i in json.loads(call(DemoBackend(), payload))["plan"]]
    assert 5 <= len(plan) <= 8
    assert (plan[0].kind, plan[0].place) == ("move", "dev-office")
    assert any(i.kind == "eat" and i.place == "cafeteria" for i in plan)
    assert any(i.kind == "talk" and i.place == "cafeteria" and i.text for i in plan)
    assert any(i.kind == "work" and i.task == "docs" for i in plan)
    untils = [i.until for i in plan]
    assert untils == sorted(untils) and untils[-1] == 31  # the closing tick is left to judgement
    payload["tasks"] = []
    rest = [PlanItem.model_validate(i) for i in json.loads(call(DemoBackend(), payload))["plan"]]
    assert 5 <= len(rest) <= 8 and rest[-1].until == 31


def test_demo_answers_reflection_prompts_with_questions_then_insights():
    def row(id, description, valence, subject):
        return {"id": id, "tick": 1, "type": "observation", "description": description,
                "valence": valence, "subjects": [subject]}  # fmt: skip

    records = [row("Alex:0", "Blake looks angry.", -0.9, "Blake"),
               row("Alex:1", "Casey looks pleased.", 0.5, "Casey")]  # fmt: skip
    questions = json.loads(
        call(DemoBackend(), {"agent": "Alex", "language": "English", "records": records})
    )["questions"]
    assert questions and "Blake" in questions[0]
    insights = json.loads(
        call(
            DemoBackend(),
            {"agent": "Alex", "language": "English", "question": questions[0], "records": records},
        )
    )["insights"]
    assert insights[0]["evidence"] == ["Alex:0"] and insights[0]["subjects"] == ["Blake"]
    assert -1 <= insights[0]["valence"] <= 1 and 1 <= insights[0]["importance"] <= 10
