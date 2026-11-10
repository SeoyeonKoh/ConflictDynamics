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
    assert stopped["paused_tick"] == 6 and stopped["tape"] is True


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


def test_the_catalog_builds_each_scenario_once_until_its_files_change(tmp_path, monkeypatch):
    """Opening the live dialog rebuilt all 17 configs every time (1.5 s)."""
    import conflict_sim.company_runtime as runtime

    built = []
    real = runtime.build_company_config
    monkeypatch.setattr(runtime, "build_company_config",
                        lambda name: built.append(name) or real(name))  # fmt: skip
    monkeypatch.setattr("conflict_sim.runs._CATALOG", {})
    first = scenario_catalog(tmp_path)
    count = len(built)
    assert scenario_catalog(tmp_path) == first and len(built) == count  # nothing rebuilt
    monkeypatch.setattr("conflict_sim.runs._conf_stamp", lambda: ("changed",))
    scenario_catalog(tmp_path)
    assert len(built) == 2 * count  # a changed conf tree rebuilds


def test_a_run_row_does_not_parse_its_events_again_until_they_change(tmp_path, monkeypatch):
    run_scenario("s0_smoke", tmp_path / "r")
    first = _row(tmp_path, "r")
    events = (tmp_path / "r" / "events.jsonl").read_text().splitlines()
    assert first["events"] == len(events)
    import conflict_sim.runs as runs

    def parse_all(path):  # what the listing did for every run on every open (0.3 s for 35)
        raise AssertionError("re-read every event")

    monkeypatch.setattr(runs, "_read_jsonl", parse_all)
    again = _row(tmp_path, "r")
    assert again["events"] == first["events"] and again["ticks"] == first["ticks"]
