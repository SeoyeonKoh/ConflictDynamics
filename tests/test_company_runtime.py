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
from conflict_sim.frames import Frames
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
    denied = loop.env.apply("HDS-020", action("approve", task="T11"), tick=1)
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
    tick = task.due - 1  # its remaining work no longer fits before the due
    view = loop._view(agent, tick=tick, day=0, phase="morning")
    agent.end_tick(tick, view, "morning")
    assert agent.state.stress >= 0.2 + cfg.p_blocked
    assert agent.state.workload > 0
    agent.end_tick(3, view, "overtime")
    assert agent.state.overtime_ticks == 1
    assert cfg.p_overtime is None  # observation is implemented; the undecided coefficient is not


def test_a_wait_with_time_to_spare_is_not_pressure():
    cfg, loop = runtime("p0_kickoff")
    loop.env.org.advance(0)
    agent = loop.agent("HDS-008")
    view = loop._view(agent, tick=2, day=0, phase="morning")
    assert len(view.blocked) >= 3  # queued project steps
    agent.state.stress = 0.2
    agent.end_tick(2, view, "morning")
    assert agent.state.stress == pytest.approx(0.2 - cfg.stress_decay)


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


def test_experiment_frames_are_a_viewer_journal_on_the_company_map(tmp_path):
    output = tmp_path / "smoke"
    run_scenario("s0_smoke", output)
    rows = [json.loads(line) for line in (output / "frames.jsonl").read_text().splitlines()]
    assert rows[0]["type"] == "hello" and len(rows[0]["agents"]) == 20
    places = {
        prop["value"]
        for layer in rows[0]["map_data"]["layers"]
        for obj in layer.get("objects", [])
        for prop in obj.get("properties", [])
        if prop["name"] == "place_id"
    }
    assert {"office", "meeting_room", "focus_room"} <= places
    assert any(row["type"] == "frame" for row in rows)
    assert rows[-1] == rows[-1] | {"type": "status", "state": "completed"}
    assert (output / "inspect.jsonl").is_file()


def test_experiment_out_of_budget_pauses_at_its_checkpoint_and_resumes(tmp_path, monkeypatch):
    import conflict_sim.experiment as experiment
    from conflict_sim.llm import LLMError

    class Trips(DemoBackend):  # budget runs out on the second day
        def complete(self, **request):
            payload = json.loads(request["prompt"])
            tick = payload.get("view", {}).get("tick") or payload.get("tick")
            if tick is not None and tick >= 34:
                raise LLMError("Run token budget reached; no further API calls")
            return super().complete(**request)

    output = tmp_path / "run"
    monkeypatch.setattr(experiment, "DemoBackend", Trips)
    paused = run_scenario("s0_baseline", output)
    assert paused["run_status"] == "paused" and paused["checkpoint"] == 0
    assert json.loads((output / "manifest.json").read_text())["status"] == "paused"
    assert json.loads((output / "paused.json").read_text())["tick"] == 34
    assert not (output / "corpus").exists()
    rows = [json.loads(line) for line in (output / "frames.jsonl").read_text().splitlines()]
    assert rows[-1]["type"] == "status" and rows[-1]["state"] == "paused"

    monkeypatch.setattr(experiment, "DemoBackend", DemoBackend)
    summary = run_scenario("s0_baseline", output, resume=True)
    assert summary["run_status"] == "completed" and summary["ticks"] == 68
    assert not (output / "paused.json").exists()
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["status"] == "completed" and len(manifest["token_usage_segments"]) == 2
    rows = [json.loads(line) for line in (output / "frames.jsonl").read_text().splitlines()]
    ticks = [row["tick"] for row in rows if row["type"] == "frame"]
    assert ticks == list(range(68))  # the partial second day was replaced, not doubled
    assert sum(row["type"] == "hello" for row in rows) == 1


def test_resume_needs_a_paused_run(tmp_path):
    with pytest.raises(FileNotFoundError, match="No paused run"):
        run_scenario("s0_smoke", tmp_path / "none", resume=True)


def test_forced_block_refusal_names_when_the_task_is_free_again():
    _, loop = runtime("s0_baseline")
    env = loop.env
    task = env.org.tasks["T01"]
    env.office.location[task.owner] = "office"
    task.forced_block_until = 10
    refused = env.apply(task.owner, action("work", task="T01"), tick=2)
    assert refused is not None and refused.reason == "T01 is unavailable until tick 10"


def test_paid_experiment_is_blocked_without_explicit_cost_approval(tmp_path, monkeypatch):
    monkeypatch.delenv("ALLOW_PAID_API_EXPERIMENTS", raising=False)
    with pytest.raises(PermissionError, match="user cost approval"):
        run_scenario("s0_baseline", tmp_path / "paid", backend="openai", pilot=True)


def test_chase_cooldown_refuses_asking_a_blocker_owner_again_until_it_passes():
    _, loop = runtime("s0_baseline")
    env = loop.env
    assert env.chase_cooldown == 8
    env.advance(0)  # marks T02 blocked
    ask = action("message", target="HDS-002", text="When is T01 done?")
    assert env.apply("HDS-012", ask, tick=1) is None  # T02 waits on HDS-002's T01
    (blocked,) = [b for b in env.env_view("HDS-012").blocked if b.owner == "HDS-002"]
    assert blocked.asked_tick == 1
    again = env.apply("HDS-012", ask, tick=5)
    assert again is not None and "until tick 9" in again.reason
    assert env.apply("HDS-012", ask, tick=9) is None
    other = action("message", target="HDS-005", text="Lunch?")
    assert env.apply("HDS-012", other, tick=9) is None  # not a blocker owner: no cooldown
    restored = Environment(loop.cfg.environment, loop.cfg.agents)
    restored.restore(env.snapshot())
    assert restored.chased == {"HDS-012>HDS-002": 9}


def test_helpers_join_a_ready_task_up_to_the_cap_and_work_on_it():
    _, loop = runtime("s0_baseline")
    env = loop.env
    assert env.org.max_workers == 4
    env.advance(0)
    t01 = env.org.tasks["T01"]  # HDS-002 owns it, HDS-003 contributes
    for name in ("HDS-002", "HDS-010", "HDS-016"):
        env.office.location[name] = "office"
    blocked = env.apply("HDS-010", action("help", task="T03"), tick=1)
    assert blocked is not None and "blocked by" in blocked.reason
    assert all(h.task != "T01" for h in env.env_view("HDS-010").help_wanted)
    assert env.apply("HDS-002", action("ask_help", task="T01", text="Two hands?"), tick=1) is None
    (offer,) = env.env_view("HDS-010").help_wanted
    assert (offer.task, offer.free_slots) == ("T01", 2)
    assert env.apply("HDS-010", action("help", task="T01"), tick=1) is None
    assert env.apply("HDS-016", action("help", task="T01"), tick=1) is None
    full = env.apply("HDS-020", action("help", task="T01"), tick=1)
    assert full is not None and "already has 4 people" in full.reason
    assert env.env_view("HDS-020").help_wanted == ()
    assert env.apply("HDS-010", action("work", task="T01"), tick=2) is None
    (mine,) = [t for t in env.env_view("HDS-010").tasks if t.id == "T01"]
    assert mine.role == "helper" and t01.worked == 1
    restored = Environment(loop.cfg.environment, loop.cfg.agents)
    restored.restore(env.snapshot())
    assert restored.org.tasks["T01"].helpers == ["HDS-010", "HDS-016"]


def test_the_company_map_seats_each_department_behind_its_own_partition():
    cfg, _ = runtime("s0_baseline")
    frames = Frames(cfg, "test")
    dept = {agent.name: agent.department for agent in cfg.agents}
    names = [agent.name for agent in cfg.agents][:16]
    spots = frames.spots("office", names, [agent.name for agent in cfg.agents])
    assert all(frames.seat_dept[spots[name]] == dept[name] for name in names)
    zones = {
        prop["value"]
        for layer in frames.map["layers"]
        for obj in layer.get("objects", [])
        for prop in obj.get("properties", [])
        if prop["name"] == "zone"
    }
    assert set(dept.values()) <= zones  # plus the focus room's two booths


def test_leaving_early_needs_all_my_work_done_and_nothing_to_review():
    _, loop = runtime("s0_baseline")
    env = loop.env
    env.office.location["HDS-002"] = "office"
    refused = env.apply("HDS-002", action("leave"), tick=1)
    assert refused is not None and "T01 is not done yet" in refused.reason
    env.org.tasks["T01"].done_tick = 1
    assert env.apply("HDS-020", action("leave"), tick=2) is not None  # T12 still open
    assert env.apply("HDS-004", action("leave"), tick=2) is not None  # contributes to T03
    t03 = env.org.tasks["T03"]
    t03.worked, t03.lifecycle = t03.spec.effort_ticks, "review"
    waiting = env.apply("HDS-002", action("leave"), tick=2)
    assert waiting is not None and "T03 waits for your review" in waiting.reason
    for task in env.org.tasks.values():  # HDS-002 also contributes to T14
        task.done_tick, task.lifecycle = 2, "done"
    assert env.apply("HDS-002", action("leave"), tick=3) is None
    assert env.office.location["HDS-002"] == "lobby"


def test_kickoff_scenario_leaves_five_tasks_unowned_for_the_assigner():
    cfg, loop = runtime("p0_kickoff")
    unowned = {t.id for t in cfg.environment.org.tasks if t.owner is None}
    assert unowned == {"T04", "T05", "T06", "T09", "T12"}
    assert all(not t.contributors for t in cfg.environment.org.tasks if t.id in unowned)
    roles = {t.id: t.role for t in loop.env.env_view("HDS-001").tasks}
    assert all(roles[task] == "assigner" for task in unowned)
    assert "T04" not in {t.id for t in loop.env.env_view("HDS-013").tasks}  # not handed out yet
    assert {m.rule for m in cfg.scenario.meetings} == {"everyone"}


def test_review_work_is_shown_to_whoever_may_approve_it():
    _, loop = runtime("p0_kickoff")
    env = loop.env
    t04 = env.org.tasks["T04"]  # experience_design: HDS-011 approves but is not listed on it
    t04.owner, t04.worked, t04.lifecycle = "HDS-013", t04.spec.effort_ticks, "review"
    (seen,) = [t for t in env.env_view("HDS-011").tasks if t.id == "T04"]
    assert (seen.role, seen.lifecycle, seen.can_approve) == ("reviewer", "review", True)


def test_an_everyone_meeting_gives_each_participant_one_turn_without_a_judgement():
    _, loop = runtime("p0_kickoff")
    for tick in range(3):
        loop.tick(tick)
    meeting = loop.threads["meeting:kickoff:0"]
    speakers = [u.speaker for u in meeting.utterances[1:]]
    assert speakers == ["HDS-001", "HDS-002", "HDS-005", "HDS-011", "HDS-014", "HDS-017", "HDS-019"]


def test_a_finished_task_carries_its_record_and_the_owners_summary():
    """C-16: finished work was questioned ~300 times because nothing was on file."""
    _, loop = runtime("s0_baseline")
    for tick in range(12):
        loop.tick(tick)
    t03 = loop.env.org.tasks["T03"]
    assert t03.done and t03.summary and t03.approved_by == "HDS-002"
    (seen,) = [t for t in loop.env.env_view("HDS-004").tasks if t.id == "T03"]
    record = seen.record
    assert record["owner"] == "HDS-003" and record["summary"] == t03.summary
    # work ticks: one does less than a tick's effort under stress, which work itself raises
    assert sum(record["worked_by"].values()) >= t03.spec.effort_ticks
    assert record["started_tick"] <= record["review_tick"] <= record["done_tick"]
    assert [p["id"] for p in record["prerequisites"]] == ["T01", "T02"]
    board = loop.env.env_view("HDS-020").task_board  # everyone sees what is done
    assert any(line.startswith("T03 ") and "approved by HDS-002" in line for line in board)
    summaries = [e for e in loop.writer.events if e.payload.get("change") == "summary"]
    assert {e.actor for e in summaries} >= {"T01", "T02", "T03"}


def test_approve_and_reject_notes_go_on_the_record():
    _, loop = runtime("s0_baseline")
    env, t03 = loop.env, loop.env.org.tasks["T03"]
    for task_id in ("T01", "T02"):
        env.org.tasks[task_id].done_tick = 0
    t03.worked, t03.lifecycle = t03.spec.effort_ticks, "review"
    note = action("reject", task="T03", text="Success criteria are not measurable yet.")
    assert env.apply("HDS-002", note, tick=4) is None
    assert t03.rejections == [{"by": "HDS-002", "tick": 4, "note": note.text}]
    t03.worked, t03.lifecycle = t03.spec.effort_ticks, "review"
    ok = action("approve", task="T03", text="Criteria now trace to the brief.")
    assert env.apply("HDS-002", ok, tick=6) is None
    assert (t03.approved_by, t03.approval_note) == ("HDS-002", ok.text)


def test_nobody_signs_off_their_own_work_and_the_manager_steps_in():
    """p0_kickoff: T10's owner held its approval scope and rejected its own work 14 times."""
    _, loop = runtime("s0_baseline")
    env, t10 = loop.env, loop.env.org.tasks["T10"]
    t10.worked, t10.lifecycle = t10.spec.effort_ticks, "review"
    t10.worked_by = {"HDS-010": 3}
    assert env.org.signers(t10) == {"HDS-005"}  # HDS-010 alone holds deployment_checklist
    own = env.apply("HDS-010", action("reject", task="T10", text="No checklist."), tick=1)
    assert own is not None and "own work" in own.reason
    (seen,) = [t for t in env.env_view("HDS-005").tasks if t.id == "T10"]
    assert seen.can_approve and seen.can_reject


def test_a_lead_who_helped_a_little_signs_and_one_who_did_more_passes_it_up():
    """r10_human-v5: the manager named each lead to help their report's task, the lead could not
    sign, nor could the lead as the report's manager, so the report signed their own work."""
    _, loop = runtime("r10_human")
    org = loop.env.org
    t09, t06, t04 = (org.tasks[t] for t in ("T09", "T06", "T04"))
    t09.owner, t09.assigned, t09.worked_by = "HDS-015", ["HDS-014"], {"HDS-015": 1}
    assert org.signers(t09) == {"HDS-014"}  # named to help, did nothing: QA's lead signs
    t04.owner, t04.assigned, t04.worked_by = "HDS-013", ["HDS-011"], {"HDS-013": 1, "HDS-011": 1}
    assert org.signers(t04) == {"HDS-011"}  # helped as much as the owner: may still sign
    t06.owner, t06.assigned, t06.worked_by = "HDS-006", ["HDS-005"], {"HDS-006": 1, "HDS-005": 2}
    assert org.signers(t06) == {"HDS-001"}  # did more than the owner: up the line, past them


def test_work_returned_twice_can_only_be_approved():
    _, loop = runtime("s0_baseline")
    env, t09 = loop.env, loop.env.org.tasks["T09"]
    t09.worked_by = {"HDS-014": 2}  # QA's lead owns T09 and alone holds quality_signoff
    assert env.org.signers(t09) == {"HDS-001"}  # so the owner's manager signs it
    for tick in (1, 3):
        t09.worked, t09.lifecycle = t09.spec.effort_ticks, "review"
        assert env.apply("HDS-001", action("reject", task="T09", text="Gap."), tick=tick) is None
    t09.worked, t09.lifecycle = t09.spec.effort_ticks, "review"
    again = env.apply("HDS-001", action("reject", task="T09", text="Gap."), tick=5)
    assert again is not None and "can only be approved" in again.reason
    assert env.apply("HDS-001", action("approve", task="T09", text="Fine."), tick=5) is None


def test_the_top_managers_own_release_task_is_signed_by_them():
    _, loop = runtime("s0_baseline")
    t14 = loop.env.org.tasks["T14"]  # HDS-001 owns it and alone holds `release`
    t14.worked_by = {"HDS-001": 2}
    assert loop.env.org.signers(t14) == {"HDS-001"}


def test_whoever_did_most_of_the_work_writes_the_summary():
    """p0_kickoff: T02's owner never touched it and wrote that it was still blocked."""
    _, loop = runtime("s0_baseline")
    t02 = loop.env.org.tasks["T02"]
    t02.worked_by, t02.done_tick, t02.lifecycle = {"HDS-003": 2}, 3, "done"
    loop._to_summarize.append("T02")
    loop._summarize(3)
    (event,) = [e for e in loop._events if e.payload.get("change") == "summary"]
    assert (event.actor, event.target) == ("T02", "HDS-003") and t02.summary


def test_the_assigner_sees_what_the_kickoff_said():
    _, loop = runtime("p0_kickoff")
    for tick in range(3):
        loop.tick(tick)
    view = loop._view(loop.agent("HDS-001"), 3, 0, "morning")
    assert any(t.role == "assigner" for t in view.tasks)
    assert len(view.last_meeting) == 8 and view.last_meeting[1].startswith("HDS-001: ")
    assert loop._view(loop.agent("HDS-002"), 3, 0, "morning").last_meeting == []


def test_deliverable_tasks_write_a_document_the_next_task_builds_on():
    cfg, loop = runtime("p0_kickoff")
    specs = {t.id: t for t in cfg.environment.org.tasks}
    assert {i for i, t in specs.items() if t.deliverable} == {"T03", "T06", "T09", "T11"}
    assert "R<n>" in specs["T03"].deliverable and specs["T03"].criteria
    org, env = loop.env.org, loop.env
    t03 = org.tasks["T03"]
    t03.worked_by, t03.done_tick, t03.lifecycle = {"HDS-003": 3}, 8, "done"
    loop._to_summarize.append("T03")
    loop._summarize(8)
    assert t03.document and t03.summary
    t06 = org.tasks["T06"]
    t06.owner = "HDS-007"
    (seen,) = [t for t in env.env_view("HDS-007").tasks if t.id == "T06"]
    assert seen.deliverable and seen.criteria and seen.document is None
    inputs = {i["id"]: i for i in seen.inputs}
    assert inputs["T03"]["document"] == t03.document  # the next task reads the document


def test_a_rejected_deliverable_is_rewritten_with_the_note_in_hand():
    class Recording(DemoBackend):
        prompts = []

        def complete(self, **request):
            self.prompts.append(json.loads(request["prompt"]))
            return super().complete(**request)

    _, loop = runtime("p0_kickoff")
    llm = Recording()
    for agent in loop.agents:
        agent.llm = llm
    t03 = loop.env.org.tasks["T03"]
    t03.worked_by, t03.lifecycle = {"HDS-003": 3}, "review"
    t03.rejections = [{"by": "HDS-002", "tick": 7, "note": "R3 has no metric."}]
    loop._to_summarize.append("T03")
    loop._summarize(9)
    (asked,) = [p for p in llm.prompts if "finished_task" in p]
    assert asked["finished_task"]["rejections"][0]["note"] == "R3 has no metric."
    assert t03.document


def test_an_assignment_can_staff_a_task_with_a_team():
    _, loop = runtime("p0_kickoff")
    env, t06 = loop.env, loop.env.org.tasks["T06"]
    staffed = action("assign", task="T06", target="HDS-007", targets=["HDS-006", "HDS-008"])
    assert env.apply("HDS-001", staffed, tick=3) is None
    assert (t06.owner, t06.assigned) == ("HDS-007", ["HDS-006", "HDS-008"])
    assert t06.workers == ["HDS-007", "HDS-006", "HDS-008"]
    roles = {t.id: t.role for t in env.env_view("HDS-008").tasks}
    assert roles["T06"] == "contributor"
    crowd = action(
        "assign", task="T09", target="HDS-014", targets=["HDS-015", "HDS-016", "HDS-020", "HDS-018"]
    )
    too_many = env.apply("HDS-001", crowd, tick=4)
    assert too_many is not None and "at most 4 people" in too_many.reason


def test_department_projects_meet_at_cross_points():
    cfg, loop = runtime("p0_kickoff")
    steps = {t.id: t for t in cfg.environment.org.tasks if t.group}
    assert len(steps) == 66 and sum(t.cross for t in steps.values()) == 24
    dept = {a.name: a.department for a in cfg.agents}
    screens = steps["P1-screens"]  # the payments project needs Product Experience
    assert screens.cross and dept[screens.owner] == "Product Experience"
    assert screens.reviewers == ["HDS-005"] and screens.depends_on == ["P1-arch"]
    assert steps["P1-client"].depends_on == ["P1-api", "P1-screens"]
    assert steps["P1-arch"].depends_on == ["T03"] and steps["P2-profile"].depends_on == []
    t = loop.env.org.tasks["P1-screens"]
    t.worked, t.lifecycle, t.worked_by = t.spec.effort_ticks, "review", {screens.owner: 5}
    assert loop.env.org.signers(t) == {"HDS-005"}  # the project's lead signs off the help
    (seen,) = [v for v in loop.env.env_view(screens.owner).tasks if v.id == "P1-screens"]
    assert seen.cross and seen.project == "P1 payments service"
    board = loop.env.env_view("HDS-020").task_board
    assert "P1 payments service: 0/7 steps done" in board


def test_a_rating_presses_its_target_and_is_remembered():
    _, loop = runtime("s4_evaluation_season")
    loop.env.org.evaluation_season = True
    target = loop.agent("HDS-005")
    before = target.state.stress
    rating = action("evaluate", target="HDS-005", rating=0.25, text="Release slipped.")
    assert loop._apply(loop.agent("HDS-001"), rating, 1, 0) is None
    assert target.state.stress == pytest.approx(before + loop.cfg.p_evaluated * 0.75)
    assert "HDS-001 evaluated my work: 0.25" in target.memory.records[-1].description


def test_a_default_deliverable_gives_every_other_task_a_document(monkeypatch):
    import conflict_sim.company_runtime as company_runtime

    scenario = load_c15_scenario("p0_kickoff")
    default = {"format": "The work product in lines.", "criteria": "It covers the task."}
    scenario = scenario.model_validate(scenario.model_dump() | {"default_deliverable": default})
    monkeypatch.setattr(company_runtime, "load_c15_scenario", lambda name: scenario)
    tasks = {t.id: t for t in build_company_config("p0_kickoff").environment.org.tasks}
    assert tasks["T03"].deliverable.startswith("A numbered list")  # its own form stands
    assert tasks["T01"].deliverable == tasks["P1-arch"].deliverable == default["format"]
    assert all(t.criteria for t in tasks.values())


def test_a_finished_task_shows_its_record_without_repeating_summary_or_document():
    _, loop = runtime("p0_kickoff")
    org, env = loop.env.org, loop.env
    t03 = org.tasks["T03"]
    t03.worked_by, t03.done_tick, t03.lifecycle = {"HDS-003": 3}, 8, "done"
    t03.summary, t03.document = "Requirements written.", "R1: fast - measured by p95"
    (seen,) = [t for t in env.env_view("HDS-003").tasks if t.id == "T03"]
    assert seen.summary is seen.document is seen.deliverable is None
    assert seen.record["summary"] == "Requirements written." and "document" not in seen.record
    full = env.task_view("HDS-003", "T03")  # the summary call still sees what it produces
    assert full.deliverable and full.document and full.record["document"]


def test_a_finished_prerequisite_is_announced_to_those_working_on_what_follows():
    _, loop = runtime("p0_kickoff")
    org = loop.env.org
    after = [t for t in org.tasks.values() if "T03" in t.spec.depends_on and t.workers]
    assert after
    for task in after:
        for name in task.workers:
            loop.agent(name).brief(task.id, [{"task": "T03", "owner": "HDS-003"}], 5)
    loop._notice("T03", "approved", 11)
    for task in after:
        for name in task.workers:
            note = loop.agent(name)._notes[task.id]
            assert note["how"] == "notice" and all(w["task"] != "T03" for w in note["waits_on"])
    loop._notice("T03", "review", 12)  # only a finished task is announced
    assert all(loop.agent(n)._notes[t.id]["noted_tick"] == 11 for t in after for n in t.workers)


def test_the_korean_scenario_keeps_the_graph_and_speaks_korean():
    english, korean = build_company_config("p0_documents"), build_company_config("p0_documents_ko")
    assert korean.language == "Korean" and english.language == "English"
    en = {t.id: t for t in english.environment.org.tasks}
    ko = {t.id: t for t in korean.environment.org.tasks}
    assert set(en) == set(ko)
    for task_id, task in ko.items():  # the same graph, people and timing; only the words differ
        other = en[task_id]
        assert (task.depends_on, task.owner, task.due, task.effort_ticks) == (
            other.depends_on, other.owner, other.due, other.effort_ticks,
        )  # fmt: skip
        assert any("가" <= ch <= "힣" for ch in task.description + task.deliverable)
    assert [a.department for a in korean.agents] == [a.department for a in english.agents]
    assert korean.agents[0].persona.startswith("제품전략팀 통합 제품 리드.")
    assert "프로젝트 킥오프" in korean.scenario.meetings[0].agenda


def test_materials_reach_those_working_on_an_open_task_and_the_view_tells_the_time():
    _, loop = runtime("p0_documents_ko")
    org, env = loop.env.org, loop.env
    (seen,) = [t for t in env.env_view("HDS-002").tasks if t.id == "T01"]
    assert "42만" in seen.materials  # the office's facts on the product brief
    t01 = org.tasks["T01"]
    t01.worked_by, t01.done_tick, t01.lifecycle = {"HDS-003": 3}, 3, "done"
    (done,) = [t for t in env.env_view("HDS-002").tasks if t.id == "T01"]
    assert done.materials is None  # a finished task shows its record only
    assert env.task_view("HDS-003", "T01").materials  # the summary call still has them
    view = loop._view(loop.agent("HDS-002"), 5, 0, "morning")
    assert view.clock == "10:15"


def test_ten_agent_repeat_scenario_runs_one_day_with_relations_among_the_ten(tmp_path):
    cfg, loop = runtime("r10_documents_ko")
    names = {agent.name for agent in cfg.agents}
    assert len(names) == 10 and cfg.max_days == 1
    assert {t.owner for t in cfg.environment.org.tasks if t.owner} <= names
    assert all(set(a.state.relations) <= names for a in loop.agents)
    summary = run_scenario("r10_documents_ko", tmp_path / "r10")
    assert summary["run_status"] == "completed" and summary["agents"] == 10


def test_a_project_under_way_starts_with_work_done_begun_and_on_everyones_desk():
    """r10_midweek: the early tasks are finished with their documents, others half done, every
    person has routine work, and four unowned tasks come in during the day."""
    cfg, loop = runtime("r10_midweek")
    org = loop.env.org
    t03, t06 = org.tasks["T03"], org.tasks["T06"]
    assert t03.done and t03.done_tick == -1 and t03.approved_by == "HDS-002" and t03.document
    assert (t06.lifecycle, t06.worked, t06.worked_by) == ("in_progress", 1, {"HDS-006": 1})
    org.advance(0)
    for agent in cfg.agents:  # nobody starts the day with nothing they can do
        assert any(agent.name in t.workers and not t.done and org.arrived(t)
                   and not org.unfinished_prerequisites(t) for t in org.tasks.values())  # fmt: skip


def test_work_that_comes_in_is_unknown_until_it_arrives_then_handed_out_once():
    _, loop = runtime("r10_midweek")
    env, org = loop.env, loop.env.org
    bug = org.tasks["BUG-payment"]  # arrives at 11:30 (tick 10), unowned, software's to assign
    org.advance(9)
    assert all(t is not bug for t, _ in org.participating("HDS-005"))
    early = env.apply("HDS-005", action("assign", task="BUG-payment", target="HDS-006"), tick=9)
    assert early is not None and early.reason == "unknown task BUG-payment"
    assert ("BUG-payment", "arrived") in org.advance(10)
    assert ("assigner") in {r for t, r in org.participating("HDS-005") if t is bug}
    assert {r for t, r in org.participating("HDS-001") if t is bug} == {"assigner"}  # the manager
    assert (
        env.apply("HDS-005", action("assign", task="BUG-payment", target="HDS-006"), tick=10)
        is None
    )
    late = env.apply("HDS-001", action("assign", task="BUG-payment", target="HDS-008"), tick=10)
    assert late is not None and late.reason == "BUG-payment belongs to HDS-006"
