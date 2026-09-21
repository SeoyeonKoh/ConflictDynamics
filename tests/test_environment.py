from pathlib import Path

import pytest
from hydra import compose, initialize_config_dir

from conflict_sim.cli import parse_config
from conflict_sim.environment import Environment
from conflict_sim.models import Action, AgentSpec, Config, EnvironmentConfig, Rejected

CONF = Path(__file__).resolve().parents[1] / "conf"
SRC = Path(__file__).resolve().parents[1] / "src" / "conflict_sim"


def environment_config():
    return EnvironmentConfig.model_validate(
        {
            "office": {
                "places": [
                    {"id": "lobby", "kind": "lobby"},
                    {"id": "dev-office", "kind": "office"},
                    {"id": "meeting-room", "kind": "meeting_room", "capacity": 2},
                    {"id": "cafeteria", "kind": "cafeteria"},
                ]
            },
            "org": {
                "departments": ["dev"],
                "titles": {"manager": ["assign", "approve", "reject", "evaluate"], "engineer": []},
                "tasks": [
                    {
                        "id": "spec",
                        "description": "Write the spec",
                        "effort_ticks": 2,
                        "due": 4,
                        "owner": "Alex",
                    },
                    {
                        "id": "api",
                        "description": "Ship the API",
                        "effort_ticks": 3,
                        "due": 10,
                        "owner": "Blake",
                        "depends_on": ["spec"],
                    },
                    {"id": "docs", "description": "Write the docs", "effort_ticks": 2, "due": 12},
                ],
            },
        }
    )


def agents():
    return [
        AgentSpec(name="Erin", persona="Leads.", department="dev", title="manager"),
        AgentSpec(
            name="Alex", persona="Specs.", department="dev", title="engineer", reports_to="Erin"
        ),
        AgentSpec(
            name="Blake", persona="Builds.", department="dev", title="engineer", reports_to="Erin"
        ),
        AgentSpec(
            name="Casey", persona="Reviews.", department="dev", title="engineer", reports_to="Erin"
        ),
    ]


def action(kind, **fields):
    return Action(
        kind=kind,
        expression="neutral",
        reflection="Carry on.",
        importance=3,
        valence=0,
        arousal=0,
        **fields,
    )


@pytest.fixture
def env():
    return Environment(environment_config(), agents())


def test_company_config_composes_from_the_environment_groups():
    with initialize_config_dir(version_base="1.3", config_dir=str(CONF)):
        cfg = parse_config(compose(config_name="company"))
    assert isinstance(cfg, Config) and cfg.environment is not None
    assert cfg.backend == "demo" and cfg.n_agents == 6
    assert {p.kind for p in cfg.environment.office.places} >= {"meeting_room", "cafeteria"}
    assert any(t.depends_on for t in cfg.environment.org.tasks)
    assert all(t.due < cfg.ticks_per_day for t in cfg.environment.org.tasks)
    manager = [a for a in cfg.agents if a.reports_to is None]
    assert len(manager) == 1 and all(
        a.reports_to == manager[0].name for a in cfg.agents if a is not manager[0]
    )
    Environment(cfg.environment, cfg.agents)


def test_environment_imports_neither_agent_nor_storage_nor_llm():
    for path in (SRC / "environment").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for banned in ["agent", "storage", "llm", "conversation", "engine"]:
            assert f"from .{banned}" not in text and f"from ..{banned}" not in text, path
            assert f"import {banned}" not in text, path


def test_everyone_starts_in_the_lobby(env):
    assert env.env_view("Alex").place == "lobby"
    assert env.env_view("Alex").places["meeting-room"] == "meeting_room"
    assert sorted(env.env_view("Alex").present) == ["Blake", "Casey", "Erin"]


def test_move_changes_place_and_co_presence(env):
    assert env.apply("Alex", action("move", place="dev-office"), tick=0) is None
    assert env.env_view("Alex").place == "dev-office"
    assert env.env_view("Alex").present == ()
    assert "Alex" not in env.env_view("Blake").present


def test_move_to_an_unknown_place_is_rejected(env):
    rejected = env.apply("Alex", action("move", place="roof"), tick=0)
    assert isinstance(rejected, Rejected) and "roof" in rejected.reason


def test_a_full_room_rejects_the_next_mover(env):
    for name in ["Erin", "Alex"]:
        assert env.apply(name, action("move", place="meeting-room"), tick=0) is None
    rejected = env.apply("Blake", action("move", place="meeting-room"), tick=0)
    assert isinstance(rejected, Rejected) and "meeting-room" in rejected.reason
    assert env.env_view("Blake").resources["meeting-room"] == 0


def test_work_needs_a_desk_and_advances_progress_by_effort(env):
    rejected = env.apply("Alex", action("work", task="spec"), tick=0)
    assert isinstance(rejected, Rejected) and "lobby" in rejected.reason
    env.apply("Alex", action("move", place="dev-office"), tick=0)
    assert env.apply("Alex", action("work", task="spec"), tick=1) is None
    (task,) = env.env_view("Alex").tasks
    assert (task.id, task.progress) == ("spec", 0.5)
    assert env.apply("Alex", action("work", task="spec"), tick=2) is None
    assert env.env_view("Alex").tasks[0].progress == 1.0
    assert isinstance(env.apply("Alex", action("work", task="spec"), tick=3), Rejected)


def test_only_the_owner_works_a_task(env):
    env.apply("Blake", action("move", place="dev-office"), tick=0)
    rejected = env.apply("Blake", action("work", task="spec"), tick=0)
    assert isinstance(rejected, Rejected) and "Alex" in rejected.reason


def test_a_task_is_blocked_until_its_prerequisite_is_done(env):
    env.apply("Blake", action("move", place="dev-office"), tick=0)
    env.advance(3)
    rejected = env.apply("Blake", action("work", task="api"), tick=3)
    assert isinstance(rejected, Rejected) and "spec" in rejected.reason
    (blocked,) = env.env_view("Blake").blocked
    assert (blocked.task, blocked.waiting_on, blocked.owner, blocked.due) == (
        "api",
        "spec",
        "Alex",
        10,
    )
    assert blocked.since_tick == 3  # first advance() that saw the block
    env.apply("Alex", action("move", place="dev-office"), tick=3)
    env.apply("Alex", action("work", task="spec"), tick=3)
    env.apply("Alex", action("work", task="spec"), tick=4)
    env.advance(5)
    assert env.env_view("Blake").blocked == ()
    assert env.apply("Blake", action("work", task="api"), tick=5) is None


def test_advance_reports_overdue_and_blocked_transitions(env):
    assert env.advance(0) == [("api", "blocked")]
    assert env.advance(1) == []
    assert env.advance(5) == [("spec", "overdue")]
    assert env.advance(6) == []
    assert env.snapshot()["tasks"]["spec"]["status"] == "overdue"


def test_assign_needs_authority_and_moves_ownership(env):
    rejected = env.apply("Alex", action("assign", task="docs", target="Casey"), tick=0)
    assert isinstance(rejected, Rejected) and "assign" in rejected.reason
    assert env.apply("Erin", action("assign", task="docs", target="Casey"), tick=0) is None
    assert [t.id for t in env.env_view("Casey").tasks] == ["docs"]
    rejected = env.apply("Erin", action("assign", task="docs", target="Nobody"), tick=0)
    assert isinstance(rejected, Rejected) and "Nobody" in rejected.reason


def test_extension_request_is_approved_or_rejected_by_authority(env):
    assert isinstance(env.apply("Erin", action("approve", task="spec"), tick=1), Rejected)
    assert isinstance(env.apply("Blake", action("request", task="spec"), tick=1), Rejected)
    assert env.apply("Alex", action("request", task="spec"), tick=1) is None
    assert isinstance(env.apply("Alex", action("approve", task="spec"), tick=1), Rejected)
    assert env.apply("Erin", action("reject", task="spec"), tick=1) is None
    assert env.env_view("Alex").tasks[0].due == 4
    env.apply("Alex", action("request", task="spec"), tick=2)
    assert env.apply("Erin", action("approve", task="spec"), tick=2) is None
    assert env.env_view("Alex").tasks[0].due == 6  # remaining effort added to the deadline
    assert isinstance(env.apply("Erin", action("approve", task="spec"), tick=2), Rejected)


def test_talk_needs_every_named_person_co_present(env):
    env.apply("Alex", action("move", place="dev-office"), tick=0)
    rejected = env.apply("Alex", action("talk", text="Blake?", targets=["Blake"]), tick=0)
    assert isinstance(rejected, Rejected) and rejected.reason == "Blake is not here"
    env.apply("Blake", action("move", place="dev-office"), tick=0)
    assert env.apply("Alex", action("talk", text="Blake?", targets=["Blake"]), tick=0) is None
    rejected = env.apply("Alex", action("talk", text="Both?", targets=["Blake", "Drew"]), tick=0)
    assert isinstance(rejected, Rejected) and rejected.reason == "Drew is not here"
    rejected = env.apply("Alex", action("talk", text="Me?", targets=["Alex", "Blake"]), tick=0)
    assert isinstance(rejected, Rejected) and rejected.reason == "Alex is not here"
    assert env.env_view("Alex").place == "dev-office"  # talk changes no state


def test_message_and_chat_need_a_real_other_agent(env):
    assert env.apply("Alex", action("message", target="Blake", text="Status?"), tick=0) is None
    assert isinstance(env.apply("Alex", action("chat", target="Alex"), tick=0), Rejected)
    assert isinstance(
        env.apply("Alex", action("message", target="Nobody", text="?"), tick=0), Rejected
    )


def test_report_goes_to_my_manager_only(env):
    assert env.apply("Alex", action("report", target="Erin", text="Blocked."), tick=0) is None
    rejected = env.apply("Alex", action("report", target="Blake", text="Blocked."), tick=0)
    assert isinstance(rejected, Rejected) and "Erin" in rejected.reason
    assert isinstance(
        env.apply("Erin", action("report", target="Alex", text="?"), tick=0), Rejected
    )


def test_eat_only_where_food_is(env):
    assert isinstance(env.apply("Alex", action("eat"), tick=0), Rejected)
    env.apply("Alex", action("move", place="cafeteria"), tick=0)
    assert env.apply("Alex", action("eat"), tick=0) is None
    assert env.apply("Alex", action("rest"), tick=0) is None


def test_unknown_actor_or_task_is_an_error_not_a_rejection(env):
    with pytest.raises(KeyError):
        env.apply("Nobody", action("rest"), tick=0)
    assert isinstance(env.apply("Alex", action("work", task="nope"), tick=0), Rejected)


def test_snapshot_is_plain_data_and_restores_the_same_world(env):
    env.apply("Alex", action("move", place="dev-office"), tick=0)
    env.apply("Alex", action("work", task="spec"), tick=1)
    snapshot = env.snapshot()
    assert snapshot["places"]["Alex"] == "dev-office"
    assert snapshot["tasks"]["spec"] == {
        "owner": "Alex", "due": 4, "worked": 1, "done_tick": None, "blocked_since": None,
        "overdue": False, "request": None, "progress": 0.5, "status": "open",
    }  # fmt: skip
    fresh = Environment(environment_config(), agents())
    fresh.restore(snapshot)
    assert fresh.snapshot() == snapshot and fresh.env_view("Alex").place == "dev-office"


def test_a_place_on_any_action_means_go_there_first(env):
    assert env.apply("Alex", action("eat", place="cafeteria"), tick=16) is None
    assert env.env_view("Alex").place == "cafeteria"
    assert env.apply("Alex", action("work", task="spec", place="dev-office"), tick=17) is None
    assert env.env_view("Alex").place == "dev-office"
    env.apply("Blake", action("move", place="meeting-room"), tick=17)
    env.apply("Casey", action("move", place="meeting-room"), tick=17)
    refused = env.apply("Alex", action("rest", place="meeting-room"), tick=18)
    assert refused.reason == "meeting-room is full" and env.env_view("Alex").place == "dev-office"
