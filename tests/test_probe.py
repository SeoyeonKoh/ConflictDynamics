from conflict_sim.models import Action
from conflict_sim.probe import build, check, situation


def act(**fields):
    return Action.model_validate(
        {"expression": "neutral", "reflection": "-", "importance": 1, "valence": 0, "arousal": 0}
        | fields
    )


def test_expectations_fail_with_a_reason_and_when_limits_a_rule():
    rules = [{"when": {"kind": "work"}, "field": "task", "not_in": ["T04"]},
             {"field": "text", "matches": r"\d{1,2}:\d{2}"}]  # fmt: skip
    assert check(act(kind="message", target="A", text="11:15에 드릴게요"), rules) == []
    assert check(act(kind="work", task="T04", text="10:00"), rules) == ["task='T04' in ['T04']"]
    assert check(act(kind="rest"), rules[1:]) == ["text does not match '\\\\d{1,2}:\\\\d{2}'"]


def test_a_case_lays_its_context_over_the_world_without_a_paid_call():
    case = {
        "base": {"scenario": "p0_documents_ko", "warmup": 1},
        "agent": "HDS-011",
        "tick": 6,
        "world": {"tasks": {"T04": {"owner": "HDS-011", "lifecycle": "ready"}}},
        "context": {
            "place": "office",
            "inbox": [{"sender": "HDS-002", "text": "T04 언제 볼 수 있을까요?"}],
            "plan": [{"kind": "work", "task": "T04", "until": 14, "text": "T04 작업"}],
            "relations": {"HDS-002": -0.4},
        },
    }
    loop, _ = build(case, None)  # demo completions and embeddings: no API at all
    agent, view, tick = situation(case, loop, "HDS-011")
    assert (tick, view.clock, view.place) == (6, "10:30", "office")
    assert loop.env.office.location["HDS-011"] == "office"
    assert [m.sender for m in view.inbox] == ["HDS-002"] and agent.plan[0].task == "T04"
    assert agent.state.relations["HDS-002"].relation == -0.4
    assert agent._known(view).workable == []  # T04 waits on T03: the briefing says so
