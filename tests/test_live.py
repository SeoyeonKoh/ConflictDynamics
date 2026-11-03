import json
import shutil
import subprocess
import sys
import time

import pytest

from conflict_sim import live
from conflict_sim.experiment import run_scenario
from conflict_sim.runs import discover_company_runs

FAST = {"tick_delay": 0.05}


def _start(root, **kw):
    args = dict(scenario="s0_smoke", days=1, max_total_tokens=None, backend="demo", models={},
                paid_confirmed=False) | FAST | kw  # fmt: skip
    return live.start(root, **args)


def _row(root, run):
    rows, _ = discover_company_runs(root)
    live.mark(root, rows)
    return next(r for r in rows if r["run"] == run)


def _wait_exit(root, started, timeout=60):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if not any(a["id"] == started["id"] for a in live.active(root)):
            return
        time.sleep(0.1)
    raise AssertionError("run did not exit")


def test_start_list_stop_and_resume_a_demo_run(tmp_path):
    started = _start(tmp_path)
    assert [a["id"] for a in live.active(tmp_path)] == [started["id"]]
    assert started["port"] > 0
    live.stop(tmp_path, started["id"])
    _wait_exit(tmp_path, started)
    row = _row(tmp_path, started["run"])
    assert row["status"] == "paused" and row["resumable"] and row["live"] is None
    again = live.resume(tmp_path, started["run"], max_total_tokens=None, paid_confirmed=False,
                        **FAST)  # fmt: skip
    assert again["run"] == started["run"]
    log = (tmp_path / started["id"] / "live.log").read_text()
    assert again["port"] == int(live.PORT_LINE.findall(log)[-1])  # this segment's, not the first
    assert len(live.PORT_LINE.findall(log)) == 2
    _wait_exit(tmp_path, again)
    assert _row(tmp_path, started["run"])["status"] == "completed"


def test_paid_runs_need_confirmation(tmp_path):
    with pytest.raises(PermissionError):
        _start(tmp_path, backend="openai")


def test_a_dead_pid_is_not_live(tmp_path):
    run = tmp_path / "ui-x" / "s0_smoke" / "replicate-1"
    run_scenario("s0_smoke", run)
    manifest = json.loads((run / "manifest.json").read_text())
    (run / "manifest.json").write_text(json.dumps(manifest | {"status": "running"}))
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    (run / live.RECORD).write_text(json.dumps({"id": "ui-x", "pid": gone.pid, "port": 1}))
    assert live.active(tmp_path) == []
    row = _row(tmp_path, "ui-x/s0_smoke/replicate-1")
    assert row["status"] == "paused" and row["resumable"] and row["live"] is None


def test_two_starts_in_one_second_get_two_folders(tmp_path):
    a, b = _start(tmp_path), _start(tmp_path)
    try:
        assert a["run"] != b["run"]
        assert {x["id"] for x in live.active(tmp_path)} == {a["id"], b["id"]}
    finally:
        for started in (a, b):
            live.stop(tmp_path, started["id"])
            _wait_exit(tmp_path, started)


def test_resume_without_tape_or_checkpoint_is_refused(tmp_path):
    run = tmp_path / "old" / "s0_smoke" / "replicate-1"
    run_scenario("s0_smoke", run)
    (run / "tape.sqlite").unlink()
    shutil.rmtree(run / "checkpoints")
    (run / "paused.json").write_text(json.dumps({"status": "paused", "tick": 3}))
    with pytest.raises(ValueError):
        live.resume(tmp_path, "old/s0_smoke/replicate-1", max_total_tokens=None,
                    paid_confirmed=False)  # fmt: skip


def test_a_live_json_of_another_shape_is_ignored(tmp_path):
    run = tmp_path / "old" / "x"
    run.mkdir(parents=True)
    (run / "live.json").write_text(json.dumps({"pid": 1, "something": "else"}))
    (run / live.RECORD).write_text(json.dumps({"pid": 1, "something": "else"}))
    assert live.active(tmp_path) == []
