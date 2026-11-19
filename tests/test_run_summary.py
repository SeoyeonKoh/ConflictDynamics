import json
import statistics

import pytest

from conflict_sim.run_summary import main, read_jsonl, stats, summarize, to_markdown

# A 10-tick day, lunch at ticks 5-8 by phase_of (half = 5, LUNCH_TICKS = 4), no overtime.
CONFIG = {
    "ticks_per_day": 10,
    "overtime_ticks_per_day": 0,
    "agents": [{"name": "A"}, {"name": "B"}, {"name": "C"}],
    "environment": {
        "org": {
            "tasks": [
                {"id": "T1", "owner": "A", "contributors": [], "depends_on": []},
                {"id": "T2", "owner": "B", "contributors": [], "depends_on": ["T1"]},
                {"id": "T3", "owner": "C", "contributors": [], "depends_on": []},
                {"id": "T4", "owner": "C", "contributors": [], "depends_on": []},
            ],
            "initial": {},
        }
    },
}


def _task(
    tid,
    owner,
    status,
    *,
    lifecycle=None,
    progress=0.0,
    due=9,
    on_time=None,
    done_tick=None,
    depends_on=(),
):
    return {
        "id": tid,
        "owner": owner,
        "status": status,
        "lifecycle": lifecycle or status,
        "progress": progress,
        "due": due,
        "depends_on": list(depends_on),
        "record": {"team": [owner], "on_time": on_time, "done_tick": done_tick},
    }


def _event(tick, event, actor, **payload):
    return {"tick": tick, "kind": event, "actor": actor, "payload": payload}


def _write(directory, name, rows):
    (directory / name).write_text("".join(json.dumps(r) + "\n" for r in rows))


@pytest.fixture
def run(tmp_path):
    events = [
        _event(0, "task", "T2", change="blocked"),
        _event(1, "action", "A", kind="work", task="T1"),
        _event(1, "task", "T1", change="in_progress"),
        _event(2, "action", "A", kind="work", task="T1"),
        _event(2, "task", "T1", change="review"),
        _event(2, "action", "C", kind="work", task="T3"),
        _event(2, "task", "T3", change="in_progress"),
        # tick 3: A's only task is in review; B's task waits on T1 in review; C rests with work
        _event(3, "action", "A", kind="rest"),
        _event(3, "action", "B", kind="rest"),
        _event(3, "action", "C", kind="rest"),
        _event(4, "action", "A", kind="approve", task="T1"),
        _event(4, "task", "T1", change="approved"),
        _event(4, "action", "C", kind="work", task="T3"),
        _event(4, "task", "T3", change="done"),
        # tick 6 is lunch: never counted
        _event(6, "action", "A", kind="rest"),
        # tick 9: A has nothing left (T1 done); a retry's plan line does not count as an act
        _event(9, "action", "A", kind="plan", items=[]),
        _event(9, "action", "A", kind="rest"),
        _event(9, "outcome", "A", a="A", b="B", relation_delta=-0.3, grievance="g1"),
    ]
    tasks = [
        _task("T1", "A", "done", progress=1.0, on_time=True, done_tick=4),
        _task("T2", "B", "ready", depends_on=["T1"]),
        _task("T3", "C", "done", progress=1.0, due=3, on_time=False, done_tick=4),
        _task("T4", "C", "in_progress", progress=0.5),
    ]
    frames = [
        {
            "type": "hello",
            "agents": [{"id": "A", "display_name": "Ann"}, {"id": "B"}, {"id": "C"}],
            "tasks": [_task(t["id"], t["owner"], "ready") for t in tasks],
        },
        {"type": "frame", "tick": 9, "tasks": tasks},
    ]
    inspect = [
        {
            "type": "inspect",
            "agent": "A",
            "tick": 0,
            "state": {"stress": 0.0},
            "relationships": [{"to": "B", "relation": 0.1}, {"to": "C", "relation": 0.0}],
        },
        {
            "type": "inspect",
            "agent": "B",
            "tick": 0,
            "state": {"stress": 0.2},
            "relationships": [{"to": "A", "relation": 0.1}],
        },
        {"type": "inspect", "agent": "C", "tick": 0, "state": {"stress": 0.4}, "relationships": []},
        {
            "type": "inspect",
            "agent": "A",
            "tick": 9,
            "state": {"stress": 0.6},
            "relationships": [{"to": "B", "relation": -0.3}, {"to": "C", "relation": 0.5}],
        },
        {
            "type": "inspect",
            "agent": "B",
            "tick": 9,
            "state": {"stress": 0.2},
            "relationships": [{"to": "A", "relation": -0.1}],
        },
    ]
    _write(tmp_path, "events.jsonl", events)
    _write(tmp_path, "frames.jsonl", frames)
    _write(tmp_path, "inspect.jsonl", inspect)
    (tmp_path / "resolved_config.json").write_text(json.dumps(CONFIG))
    (tmp_path / "manifest.json").write_text(json.dumps({"scenario": "toy", "status": "completed"}))
    return tmp_path


def test_task_completion_status_and_deadlines(run):
    tasks = summarize(run)["tasks"]
    assert tasks["total"] == 4 and tasks["done"] == 2 and tasks["started"] == 3
    assert tasks["completion_pct"] == pytest.approx(50.0)
    assert tasks["mean_progress_pct"] == pytest.approx(62.5)
    assert tasks["by_status"] == {"done": 2, "in_progress": 1, "ready": 1}
    assert (tasks["on_time"], tasks["late"]) == (1, 1)


def test_idle_rests_split_three_ways_in_work_hours_only(run):
    idle = summarize(run)["idle"]
    # A@3: own T1 in review; B@3: T2 waits on T1 in review; C@3: T4 ready, rested anyway;
    # A@6 is lunch; A@9: T1 done, nothing workable.
    assert idle["counts"] == {"no_workable": 1, "waiting_approval": 2, "other_idle": 1}
    assert idle["work_ticks"] == 3 * 6  # ticks 0-4 and 9 of 0-9 are work hours, three agents
    assert idle["idle_pct"] == pytest.approx(100 * 4 / 18)
    assert idle["share_of_idle"]["waiting_approval"] == pytest.approx(50.0)
    assert idle["per_agent"]["A"] == {
        "no_workable": 1,
        "waiting_approval": 1,
        "other_idle": 0,
        "work_ticks": 6,
    }


def test_stress_mean_std_extremes_and_timeline_carry_forward(run):
    stress = summarize(run)["stress"]
    final = [0.6, 0.2, 0.4]  # C never changed after tick 0: carried forward
    assert stress["mean"] == pytest.approx(statistics.fmean(final))
    assert stress["std"] == pytest.approx(statistics.pstdev(final))
    assert (stress["min"], stress["max"]) == (0.2, 0.6)
    assert [a["agent"] for a in stress["agents"]] == ["A", "B", "C"]
    assert len(stress["timeline"]) == 10
    assert stress["timeline"][0]["mean"] == pytest.approx(0.2)
    assert stress["timeline"][5]["mean"] == pytest.approx(0.2)
    assert stress["timeline"][9]["mean"] == pytest.approx(0.4)


def test_relations_stats_negative_pairs_and_changes(run):
    rel = summarize(run)["relations"]
    edges = [-0.3, 0.5, -0.1]
    assert rel["mean"] == pytest.approx(statistics.fmean(edges))
    assert rel["std"] == pytest.approx(statistics.pstdev(edges))
    assert (rel["min"], rel["max"]) == (-0.3, 0.5)
    assert rel["negative_edges"] == 2 and rel["pairs"] == 2
    assert rel["negative_pairs"] == 1 and rel["conflict_pairs"] == 1
    assert rel["mutual_negative_pairs"] == 1 and rel["grievances"] == 1
    assert rel["changes"][0] == {"from": "A", "to": "C", "start": 0.0, "now": 0.5, "delta": 0.5}
    assert sum(b["n"] for b in rel["histogram"]) == 3


def test_live_run_half_written_line_and_no_summary_json(run):
    with open(run / "events.jsonl", "a") as f:
        f.write('{"tick": 10, "kind": "act')  # the writer is mid-line
    assert len(read_jsonl(run / "events.jsonl")) == 18
    got = summarize(run)
    assert got["tick"] == 9 and got["tasks"]["done"] == 2


def test_older_runs_fall_back_to_summary_json(run):
    (run / "inspect.jsonl").unlink()
    (run / "summary.json").write_text(
        json.dumps(
            {
                "summary": {
                    "stress": {"A": 0.1, "B": 0.3},
                    "relations": {"A": {"B": -0.5}, "B": {"A": 0.5}},
                }
            }
        )
    )
    got = summarize(run)
    assert got["stress"]["mean"] == pytest.approx(0.2) and got["stress"]["timeline"] == []
    rel = got["relations"]
    assert rel["conflict_pairs"] == 1 and rel["mutual_negative_pairs"] == 0


def test_stats_of_nothing():
    assert stats([]) == {"n": 0, "mean": None, "std": None, "min": None, "max": None}


# ---- review follow-ups: which rests count, when task states change, fallbacks ----


def _run(tmp_path, events, *, config=None, frames=None, manifest=None, summary=None, tasks=None):
    cfg = config or {
        "ticks_per_day": 10,
        "overtime_ticks_per_day": 0,
        "agents": [{"name": "A"}, {"name": "B"}, {"name": "C"}],
        "environment": {"org": {"tasks": tasks or [], "initial": {}}},
    }
    _write(tmp_path, "events.jsonl", events)
    if frames is not None:
        _write(tmp_path, "frames.jsonl", frames)
    (tmp_path / "resolved_config.json").write_text(json.dumps(cfg))
    (tmp_path / "manifest.json").write_text(json.dumps(manifest or {"status": "completed"}))
    if summary is not None:
        (tmp_path / "summary.json").write_text(json.dumps({"summary": summary}))
    return tmp_path


def _spec(tid, owner, depends_on=(), **extra):
    return {"id": tid, "owner": owner, "contributors": [], "depends_on": list(depends_on)} | extra


def _idle(path):
    return summarize(path)["idle"]["counts"]


def test_weekly_operations_count_only_breaks(tmp_path):
    config = {
        "ticks_per_day": 10,
        "overtime_ticks_per_day": 0,
        "weekly_operations": {"lunch_start_tick": 2},  # lunch is ticks 2-5
        "agents": [{"name": "A"}, {"name": "B"}, {"name": "C"}],
        "environment": {"org": {"tasks": [], "initial": {}}},
    }
    events = [
        # each accepted act is followed by its accepted_activity; it must not hide the rest
        _event(1, "action", "A", kind="rest", reflection="coffee"),
        _event(1, "action", "A", kind="accepted_activity", activity="break"),
        _event(1, "action", "B", kind="rest", reflection="[preparation] (T1 준비) 자료 정리"),
        _event(1, "action", "B", kind="accepted_activity", activity="preparation"),
        _event(1, "action", "C", kind="rest", reflection="wait"),
        _event(1, "action", "C", kind="accepted_activity", activity="interrupted"),
        _event(3, "action", "A", kind="rest", reflection="lunch"),  # lunch moved to tick 2
        _event(3, "action", "A", kind="accepted_activity", activity="break"),
        _event(6, "action", "A", kind="rest", reflection="after lunch"),
        _event(6, "action", "A", kind="accepted_activity", activity="break"),
    ]
    idle = summarize(_run(tmp_path, events, config=config))["idle"]
    assert idle["counts"] == {"no_workable": 2, "waiting_approval": 0, "other_idle": 0}
    assert idle["per_agent"]["A"]["no_workable"] == 2 and idle["per_agent"]["B"]["no_workable"] == 0


def test_refused_rests_do_not_count_but_a_retried_rest_does(tmp_path):
    events = [
        _event(1, "action", "A", kind="rest"),
        _event(1, "rejected", "A", reason="three colleagues are already resting"),
        _event(1, "action", "B", kind="rest"),
        _event(1, "rejected", "B", reason="no"),
        _event(1, "action", "B", kind="work", task="T1"),
        _event(1, "action", "C", kind="work", task="T9"),
        _event(1, "rejected", "C", reason="no such task"),
        _event(1, "action", "C", kind="rest"),
    ]
    assert _idle(_run(tmp_path, events)) == {
        "no_workable": 1,
        "waiting_approval": 0,
        "other_idle": 0,
    }


def test_overtime_ticks_are_not_work_hours(tmp_path):
    config = {
        "ticks_per_day": 10,
        "overtime_ticks_per_day": 2,
        "agents": [{"name": "A"}],
        "environment": {"org": {"tasks": [], "initial": {}}},
    }
    events = [_event(10, "action", "A", kind="rest"), _event(11, "action", "A", kind="rest")]
    idle = summarize(_run(tmp_path, events, config=config))["idle"]
    assert idle["idle_ticks"] == 0 and idle["work_ticks"] == 6  # 0-4 and 9; 5-8 lunch, 10-11 OT


def test_engine_changes_at_a_tick_are_seen_by_those_deciding_then(tmp_path):
    tasks = [_spec("T1", "A"), _spec("T2", "B", ["T1"])]
    events = [
        # T2 blocked at tick 0, logged by Org.advance before B decided: B had nothing workable
        _event(0, "task", "T2", change="blocked"),
        _event(0, "action", "B", kind="rest"),
        # T1 finishes at 2 by A's act: B deciding at 2 did not see it yet
        _event(2, "action", "A", kind="work", task="T1"),
        _event(2, "task", "T1", change="done"),
        _event(2, "action", "B", kind="rest"),
        # unblocked by advance at 3, before B decided: B rested with work it could do
        _event(3, "task", "T2", change="unblocked"),
        _event(3, "action", "B", kind="rest"),
    ]
    assert summarize(_run(tmp_path, events, tasks=tasks))["idle"]["per_agent"]["B"] == {
        "no_workable": 2,
        "waiting_approval": 0,
        "other_idle": 1,
        "work_ticks": 4,
    }


def test_unblocked_returns_to_the_lifecycle_and_assigned_reopens(tmp_path):
    tasks = [_spec("T0", "C"), _spec("T1", "A", ["T0"]), _spec("T2", "B")]
    events = [
        _event(1, "action", "A", kind="work", task="T1"),
        _event(1, "task", "T1", change="review"),
        _event(1, "action", "B", kind="work", task="T2"),
        _event(1, "task", "T2", change="review"),
        _event(2, "task", "T1", change="blocked"),  # a forced block while in review
        _event(3, "task", "T1", change="unblocked"),
        _event(3, "action", "A", kind="rest"),  # still in review, not ready
        _event(4, "action", "C", kind="assign", task="T2"),
        _event(4, "task", "T2", change="assigned"),
        _event(9, "action", "B", kind="rest"),  # handed out again: ready to work
    ]
    per = summarize(_run(tmp_path, events, tasks=tasks))["idle"]["per_agent"]
    assert per["A"]["waiting_approval"] == 1 and per["A"]["other_idle"] == 0
    assert per["B"]["other_idle"] == 1


def test_waiting_on_review_through_an_unfinished_chain(tmp_path):
    tasks = [_spec("T1", "A"), _spec("T2", "B", ["T1"]), _spec("T3", "C", ["T2"])]
    events = [
        _event(0, "task", "T2", change="blocked"),
        _event(0, "task", "T3", change="blocked"),
        _event(1, "action", "A", kind="work", task="T1"),
        _event(1, "task", "T1", change="review"),
        _event(2, "action", "C", kind="rest"),
    ]
    assert _idle(_run(tmp_path, events, tasks=tasks))["waiting_approval"] == 1


def test_a_task_counts_only_once_it_arrives(tmp_path):
    tasks = [_spec("T1", "A", arrives=4)]
    events = [_event(2, "action", "A", kind="rest"), _event(4, "action", "A", kind="rest")]
    assert _idle(_run(tmp_path, events, tasks=tasks)) == {
        "no_workable": 1,
        "waiting_approval": 0,
        "other_idle": 1,
    }


def test_tasks_fall_back_to_summary_json_without_frames(tmp_path):
    tasks = [_spec("T1", "A", effort_ticks=4), _spec("T2", "B", effort_ticks=4)]
    summary = {
        "tasks": {
            "T1": {"owner": "A", "due": 5, "worked": 4, "done_tick": 3, "lifecycle": "done"},
            "T2": {"owner": "B", "due": 5, "worked": 1, "done_tick": None, "overdue": True,
                   "lifecycle": "in_progress", "helpers": ["C"]},
        }
    }  # fmt: skip
    events = [_event(9, "action", "C", kind="rest")]
    got = summarize(_run(tmp_path, events, tasks=tasks, summary=summary))
    assert got["tasks"]["total"] == 2 and got["tasks"]["done"] == 1
    assert got["tasks"]["by_status"] == {"done": 1, "overdue": 1}
    assert got["tasks"]["on_time"] == 1 and got["tasks"]["mean_progress_pct"] == 62.5
    assert got["idle"]["counts"]["other_idle"] == 1  # C helps on T2, which is open


def test_an_empty_run(tmp_path):
    (tmp_path / "manifest.json").write_text("{}")
    got = summarize(tmp_path)
    assert got["tick"] == -1 and got["status"] == "unknown"
    assert got["tasks"]["total"] == 0 and got["tasks"]["completion_pct"] == 0.0
    assert got["idle"]["work_ticks"] == 0 and got["idle"]["idle_pct"] == 0.0
    assert got["stress"]["mean"] is None and got["stress"]["timeline"] == []
    assert got["relations"]["mean"] is None
    assert all(b["n"] == 0 for b in got["relations"]["histogram"])


def test_one_agent_has_no_spread(tmp_path):
    path = _run(tmp_path, [_event(0, "action", "A", kind="work")])
    _write(path, "inspect.jsonl", [{"agent": "A", "tick": 0, "state": {"stress": 0.3}}])
    assert summarize(path)["stress"]["std"] == 0.0


def test_the_stream_status_wins_and_a_live_runs_newest_tick_waits(tmp_path):
    events = [_event(1, "action", "A", kind="rest"), _event(2, "action", "A", kind="rest")]
    frames = [{"type": "status", "state": "running"}]
    got = summarize(_run(tmp_path, events, frames=frames, manifest={"status": "completed"}))
    assert got["status"] == "running"
    assert got["idle"]["idle_ticks"] == 1  # tick 2 may still be half written
    assert got["idle"]["work_ticks"] == 3 * 2


def test_frames_merge_tasks_that_changed(tmp_path):
    frames = [
        {"type": "hello", "tasks": [_task("T1", "A", "ready"), _task("T2", "B", "ready")]},
        {"type": "frame", "tick": 1, "tasks": [_task("T1", "A", "in_progress", progress=0.5)]},
    ]
    tasks = summarize(_run(tmp_path, [], frames=frames))["tasks"]
    assert tasks["by_status"] == {"in_progress": 1, "ready": 1} and tasks["started"] == 1


def test_older_journal_deadline_from_the_task_event_and_initial_done(tmp_path):
    frames = [
        {"type": "frame", "tick": 4, "tasks": [
            {"id": "T1", "status": "done", "due": 3},
            {"id": "T2", "status": "done", "due": None},
            {"id": "T0", "status": "done", "due": 3, "record": {"on_time": True, "done_tick": -1}},
        ]},
    ]  # fmt: skip
    events = [_event(4, "task", "T1", change="done"), _event(2, "task", "T2", change="approved")]
    tasks = summarize(_run(tmp_path, events, frames=frames))["tasks"]
    assert (tasks["on_time"], tasks["late"], tasks["done_before_start"]) == (2, 1, 1)


def test_malformed_rows_are_skipped(tmp_path):
    events = [{"tick": "x", "kind": "action"}, {"kind": "task"}, ["not", "a", "row"],
              _event(1, "action", "A", kind="rest")]  # fmt: skip
    path = _run(tmp_path, events, frames=[{"type": "frame", "tasks": [{"no": "id"}]}])
    _write(path, "inspect.jsonl", [{"agent": "A", "tick": 0, "state": {}}, {"agent": "B"}])
    got = summarize(path)
    assert got["idle"]["idle_ticks"] == 1 and got["tasks"]["total"] == 0
    assert got["stress"]["n"] == 0


def test_markdown_carries_every_section_with_names_and_rounded_percents(run):
    md = to_markdown(summarize(run), "exp/replicate-1")
    assert md.startswith("# Run summary: exp/replicate-1\n")
    for section in ("## Tasks", "## Idle", "## Stress", "## Relations"):
        assert section in md
    assert "| completion | 2/4 (50.0%) |" in md
    assert "| waiting_approval |" in md and "| other_idle |" in md
    assert "%%" not in md and "None" not in md


def test_cli_writes_json_and_markdown(run, tmp_path, capsys):
    assert main([str(run)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["tasks"] == summarize(run)["tasks"] and printed["run"]
    out = tmp_path / "metrics.md"
    assert main([str(run), "--format", "md", "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == to_markdown(summarize(run), printed["run"])
    assert capsys.readouterr().out == ""
