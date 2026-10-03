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
    assert sum(record["worked_by"].values()) == t03.spec.effort_ticks
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
