import json
import random

import pytest

from conflict_sim.agent import Agent
from conflict_sim.company_runtime import (
    apply_initial_relationships,
    build_company_config,
    generate_manager_tasks,
    load_c15_scenario,
)
from conflict_sim.environment import Environment
from conflict_sim.experiment import run_scenario
from conflict_sim.llm import DemoBackend
from conflict_sim.loop import Loop
from conflict_sim.models import Action, Outcome


class Recorder:
    def __init__(self):
        self.rows = []
        self.checkpoints = []

    def write_tick(self, events, memory_rows, retrieval_rows):
        self.rows.append((list(events), list(memory_rows), list(retrieval_rows)))

    def write_checkpoint(self, day, data):
        self.checkpoints.append((day, data))

    @property
    def events(self):
        return [event for events, _, _ in self.rows for event in events]


def runtime(scenario="s0_smoke"):
    cfg = build_company_config(scenario)
    llm = DemoBackend(
        blocked_nudge_ticks=cfg.blocked_nudge_ticks,
        blocked_report_ticks=cfg.blocked_report_ticks,
    )
    agents = [Agent(spec, cfg, llm) for spec in cfg.agents]
    apply_initial_relationships(agents)
    env = Environment(cfg.environment, cfg.agents)
    loop = Loop(cfg, agents, env, llm, random.Random(cfg.random_seed), Recorder())
    return cfg, loop


def action(kind, **kwargs):
    return Action(
        kind=kind,
        expression="neutral",
        reflection="Structured test action.",
        importance=3,
        valence=0,
        arousal=0,
        **kwargs,
    )


def test_c14_adapter_builds_twenty_agent_executable_config_without_changing_baseline():
    cfg = build_company_config("s0_baseline")
    assert len(cfg.agents) == cfg.n_agents == 20
    assert len(cfg.environment.org.tasks) == 15
    assert {agent.disc for agent in cfg.agents} == {"D", "i", "S", "C"}
    assert cfg.agents[0].name == "HDS-001" and cfg.agents[0].display_name == "김민재"


def test_openai_company_runtime_uses_the_existing_company_decision_limit():
    cfg = build_company_config("s0_baseline", backend="openai")
    assert cfg.max_tokens_decide == 2048
    assert cfg.max_total_tokens == 500_000
    assert all(agent.name.startswith("HDS-") for agent in cfg.agents)
    assert all(agent.project_goal.isascii() for agent in cfg.agents)


def test_scoped_authority_permits_owner_and_rejects_ungranted_member():
    _, loop = runtime()
    task = loop.env.org.tasks["T14"]
    task.worked = task.spec.effort_ticks
    task.lifecycle = "review"
    allowed = loop.env.apply("HDS-001", action("approve", task="T14"), tick=1)
    assert allowed is None and task.done

    other = loop.env.org.tasks["T11"]
    other.worked = other.spec.effort_ticks
    other.lifecycle = "review"
    denied = loop.env.apply("HDS-016", action("approve", task="T11"), tick=1)
    assert denied is not None and "may not approve" in denied.reason


def test_task_dependency_work_review_reject_rework_and_approve():
    _, loop = runtime("s0_baseline")
    env = loop.env
    env.office.location["HDS-003"] = "office"
    blocked = env.apply("HDS-003", action("work", task="T03"), tick=1)
    assert blocked is not None and "blocked by" in blocked.reason

    for task_id in ("T01", "T02"):
        task = env.org.tasks[task_id]
        task.done_tick = 1
        task.lifecycle = "done"
    env.advance(2)
    assert env.apply("HDS-003", action("work", task="T03"), tick=2) is None
    task = env.org.tasks["T03"]
    task.worked = task.spec.effort_ticks - 1
    assert env.apply("HDS-003", action("work", task="T03"), tick=3) is None
    assert task.status == "review"
    assert env.apply("HDS-002", action("reject", task="T03"), tick=4) is None
    assert task.lifecycle == "in_progress" and task.remaining == 1
    assert env.apply("HDS-003", action("work", task="T03"), tick=5) is None
    assert env.apply("HDS-002", action("approve", task="T03"), tick=6) is None
    assert task.done_tick == 6


def test_scheduled_meeting_has_explicit_participants_turns_and_duration():
    _, loop = runtime()
    loop.run_until(13)
    meetings = [meta for meta in loop.sessions.values() if meta["kind"] == "meeting"]
    assert len(meetings) == 1
    meeting = meetings[0]
    assert meeting["agenda"].startswith("Integration smoke review")
    assert meeting["end"] == 12
    assert set(meeting["participants"]) == {
        "HDS-001",
        "HDS-002",
        "HDS-005",
        "HDS-011",
        "HDS-014",
        "HDS-017",
        "HDS-019",
    }


def test_hearsay_is_private_and_keeps_provenance():
    _, loop = runtime()
    sender = loop.agent("HDS-003")
    loop._send(
        sender,
        action("gossip", target="HDS-020", subject="HDS-005", text="The review moved."),
        tick=1,
        day=0,
    )
    loop.inbox["HDS-020"] = loop.outbox["HDS-020"]
    view = loop._view(loop.agent("HDS-020"), tick=2, day=0, phase="morning")
    records = loop.agent("HDS-020").perceive(view, 2)
    assert records[-1].type == "hearsay"
    assert "HDS-005" in records[-1].subjects
    assert all(
        "The review moved" not in record.description
        for record in loop.agent("HDS-005").memory.records
    )


def test_work_pressure_blocks_recovery_and_records_workload():
    cfg, loop = runtime()
    agent = loop.agent("HDS-003")
    agent.state.stress = 0.2
    task = loop.env.org.tasks["T03"]
    task.blocked_since = 0
    view = loop._view(agent, tick=2, day=0, phase="morning")
    agent.end_tick(2, view, "morning")
    assert agent.state.stress >= 0.2 + cfg.p_blocked
    assert agent.state.workload > 0
    agent.end_tick(3, view, "overtime")
    assert agent.state.overtime_ticks == 1
    assert cfg.p_overtime is None  # observation is implemented; the undecided coefficient is not


def test_shock_schedule_is_deterministic_and_emits_changed_state():
    _, loop = runtime("s2_deadline_pressure")
    before = loop.env.org.tasks["T14"].due
    loop.run_until(4)
    shocks = [event for event in loop.writer.events if event.kind == "shock"]
    assert len(shocks) == 1 and shocks[0].payload["event_id"] == "E02"
    assert loop.env.org.tasks["T14"].due == before - 12


def test_refused_and_ignored_are_structured_outcome_facts():
    _, loop = runtime()
    requester = loop.agent("HDS-003")
    requester.apply_outcome(
        Outcome(session_id="test", public=False, refused=["HDS-002"], ignored=["HDS-004"]),
        tick=1,
    )
    assert requester.state.relation("HDS-002").relation < 0
    assert requester.state.relation("HDS-004").relation < 0


def test_manager_generated_tasks_validate_owner_deadline_and_dag():
    cfg = build_company_config("s0_smoke")

    class Scripted:
        def complete(self, **request):
            return json.dumps(
                {
                    "tasks": [
                        {
                            "id": "G01",
                            "description": "Check the release evidence",
                            "effort_ticks": 1,
                            "due": 8,
                            "owner": "HDS-014",
                            "depends_on": [],
                            "skills": ["quality_reporting"],
                        }
                    ]
                }
            )

    tasks = generate_manager_tasks(
        Scripted(),
        manager=cfg.agents[0],
        agents=cfg.agents,
        goal="Prepare release evidence",
        deadline=10,
        existing_tasks=cfg.environment.org.tasks,
    )
    assert tasks[0].owner == "HDS-014" and tasks[0].due <= 10


def test_c15_scenarios_change_only_the_declared_engine_manipulation():
    baseline = load_c15_scenario("s0_baseline")
    for name in (
        "s1_dependency_failure",
        "s2_deadline_pressure",
        "s3_resource_competition",
        "s4_evaluation_season",
    ):
        scenario = load_c15_scenario(name)
        assert scenario.task_runtime == baseline.task_runtime
        assert scenario.fixed_variables == baseline.fixed_variables
        assert len(scenario.engine.shocks) == 1


def test_c15_interventions_load_on_their_matching_scenario():
    expected = {
        "i1_manager_clarification": "manager_clarification",
        "i2_deadline_adjustment": "deadline_adjustment",
        "i3_private_mediation": "private_mediation",
    }
    for name, kind in expected.items():
        scenario = load_c15_scenario(name)
        assert len(scenario.engine.interventions) == 1
        assert scenario.engine.interventions[0].kind == kind


def test_evaluation_requires_season_and_scoped_authority():
    _, loop = runtime("s4_evaluation_season")
    loop.env.org.evaluation_season = True
    assert (
        loop.env.apply(
            "HDS-001", action("evaluate", target="HDS-005", rating=0.8, text="Release evidence."), 1
        )
        is None
    )
    assert loop.env.org.evaluations[-1].target == "HDS-005"
    denied = loop.env.apply(
        "HDS-005", action("evaluate", target="HDS-001", rating=0.8, text="Peer evidence."), 1
    )
    assert denied is not None and "may not evaluate" in denied.reason


def test_private_mediation_intervention_opens_nonpublic_session():
    _, loop = runtime("i3_private_mediation")
    loop.run_until(9)
    sessions = [meta for meta in loop.sessions.values() if meta["kind"] == "private"]
    assert len(sessions) == 1
    assert sessions[0]["public"] is False
    assert set(sessions[0]["participants"]) == {"HDS-001", "HDS-005"}


@pytest.mark.slow
def test_twenty_agent_one_day_scripted_smoke_completes_without_deadlock():
    cfg, loop = runtime()
    result = loop.run()
    assert result.ticks == cfg.ticks_per_day == 32
    assert len(loop.agents) == 20 and len(loop.env.org.tasks) == 15
    assert loop.live == {} and loop.busy == {}
    assert len(loop.writer.rows) == 32
    assert all(agent.name in loop.env.office.location for agent in loop.agents)


def test_experiment_runner_persists_reproducibility_bundle(tmp_path):
    output = tmp_path / "smoke"
    summary = run_scenario("s0_smoke", output)
    assert summary["run_status"] == "completed" and summary["agents"] == 20
    assert (output / "resolved_config.json").is_file()
    assert (output / "events.jsonl").is_file()
    assert (output / "memory.sqlite").is_file()
    assert (output / "frames.jsonl").is_file()
    assert (output / "corpus" / "run.json").is_file()
    assert json.loads((output / "manifest.json").read_text())["status"] == "completed"


def test_paid_experiment_is_blocked_without_explicit_cost_approval(tmp_path, monkeypatch):
    monkeypatch.delenv("ALLOW_PAID_API_EXPERIMENTS", raising=False)
    with pytest.raises(PermissionError, match="user cost approval"):
        run_scenario("s0_baseline", tmp_path / "paid", backend="openai", pilot=True)
