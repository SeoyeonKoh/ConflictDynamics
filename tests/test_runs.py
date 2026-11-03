import subprocess
import sys
import threading

from run_helpers import restore_demo, stop_when_tick

from conflict_sim.experiment import run_scenario
from conflict_sim.runs import discover_company_runs, people, scenario_catalog


def _row(root, name):
    rows, _ = discover_company_runs(root)
    return next(r for r in rows if r["run"] == name)


def test_runs_say_how_long_they_are_and_whether_they_resume(tmp_path, monkeypatch):
    run_scenario("s0_smoke", tmp_path / "done")
    done = _row(tmp_path, "done")
    assert done["resumable"] is False and done["paused_tick"] is None
    assert 0.9 <= done["days"] <= 1.0
    stop = threading.Event()
    stop_when_tick(monkeypatch, stop, 5)
    run_scenario("s0_smoke", tmp_path / "stopped", stop=stop)
    restore_demo(monkeypatch)
    stopped = _row(tmp_path, "stopped")
    assert stopped["status"] == "paused" and stopped["resumable"] is True
    assert stopped["paused_tick"] == 6


def test_people_are_named_from_the_config(tmp_path):
    run_scenario("s0_smoke", tmp_path / "r")
    found = people(tmp_path / "r")
    assert len(found) == 20 and all(p["name"] for p in found)
    assert {"id", "name", "title"} <= set(found[0])


def test_the_catalog_leads_with_the_recent_scenarios(tmp_path):
    catalog = scenario_catalog(tmp_path)
    assert [s["name"] for s in catalog[:2]] == ["r10_midweek", "r10_enterprise_weekly"]
    assert all(s["estimated_calls"] > 0 and s["research_question"] for s in catalog)
    midweek = catalog[0]
    assert midweek["extends"] == "r10_human" and midweek["tokens_per_day"] is None


def test_the_listing_does_not_need_the_dashboard():
    code = (
        "import sys, conflict_sim.runs\n"
        "print('pandas' in sys.modules, 'streamlit' in sys.modules)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False False"
