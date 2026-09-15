import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

PROJECT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT / "conf"
# The installed console script is the only documented entry point.
ENTRY_POINT = Path(sys.executable).with_name("conflict-sim")


def run_cli(cwd, *args):
    return subprocess.run(
        [str(ENTRY_POINT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_live_cli_saves_progress_and_the_same_completed_corpus(tmp_path):
    output = tmp_path / "live"
    process = run_cli(tmp_path, "live=true", "max_ticks=1", f"hydra.run.dir={output}")
    assert process.returncode == 0, process.stderr
    live = json.loads((output / "live.json").read_text())
    assert live["status"] == "completed"
    assert live["ticks"] == 1
    assert len(live["utterances"]) >= 2
    saved = [
        json.loads(row) for row in (output / "corpus/decisions.jsonl").read_text().splitlines()
    ]
    assert live["decisions"] == saved
    assert "reflection" not in live["utterances"][0]
    assert not (output / "live.tmp").exists()


def test_live_cli_reports_invalid_seed_as_failure_without_a_corpus(tmp_path):
    output = tmp_path / "failed"
    process = run_cli(tmp_path, "live=true", "seed_file=missing.json", f"hydra.run.dir={output}")
    assert process.returncode != 0
    live = json.loads((output / "live.json").read_text())
    assert live["status"] == "failed"
    assert "missing.json" in live["message"]
    assert not (output / "corpus").exists()


def test_live_llm_failure_retains_reflections_without_saving_a_completed_corpus(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from hydra import compose, initialize_config_dir

    from conflict_sim import cli

    with initialize_config_dir(version_base="1.3", config_dir=str(CONFIG_DIR)):
        raw = compose(config_name="config", overrides=["live=true"])
    runtime = SimpleNamespace(output_dir=str(tmp_path), cwd=str(tmp_path))
    monkeypatch.setattr(cli.HydraConfig, "get", lambda: SimpleNamespace(runtime=runtime))
    monkeypatch.setattr(cli, "sleep", lambda _: None)
    original = cli.DemoBackend.complete
    calls = 0

    def fail_on_second_call(self, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise cli.LLMError("LLM request failed: test failure")
        return original(self, **kwargs)

    monkeypatch.setattr(cli.DemoBackend, "complete", fail_on_second_call)
    with pytest.raises(SystemExit, match="LLM request failed"):
        cli.simulate.__wrapped__(raw)
    progress = json.loads((tmp_path / "live.json").read_text())
    assert progress["status"] == "failed"
    assert progress["decisions"][0]["reflection"]
    assert len(progress["utterances"]) == 2
    assert not (tmp_path / "corpus").exists()


@pytest.mark.parametrize("fail", [False, True])
def test_openai_usage_is_saved_for_completed_and_failed_runs(tmp_path, monkeypatch, fail):
    from types import SimpleNamespace

    from hydra import compose, initialize_config_dir

    from conflict_sim import cli

    with initialize_config_dir(version_base="1.3", config_dir=str(CONFIG_DIR)):
        raw = compose(config_name="config", overrides=["backend=openai", "max_ticks=1"])
    runtime = SimpleNamespace(output_dir=str(tmp_path), cwd=str(tmp_path))
    monkeypatch.setattr(cli.HydraConfig, "get", lambda: SimpleNamespace(runtime=runtime))
    monkeypatch.setattr(cli, "create_openai_client", lambda _: None)

    def complete(self, **kwargs):
        counts = self.usage["decide" if kwargs["json_mode"] else "speak"]
        counts["calls"] += 1
        counts["total_tokens"] += 15
        if fail:
            raise cli.LLMError("test response failure")
        return cli.DemoBackend().complete(**kwargs)

    monkeypatch.setattr(cli.OpenAIBackend, "complete", complete)
    if fail:
        with pytest.raises(SystemExit, match="test response failure"):
            cli.simulate.__wrapped__(raw)
        assert not (tmp_path / "corpus").exists()
    else:
        cli.simulate.__wrapped__(raw)
    usage = json.loads((tmp_path / "usage.json").read_text())
    assert usage["decide"]["total_tokens"] >= 15
    if not fail:
        assert json.loads((tmp_path / "corpus/run.json").read_text())["llm_usage"] == usage


@pytest.mark.parametrize("rule", ["round_robin", "random", "bidding", "event_driven"])
def test_demo_cli_runs_with_hydra_overrides_from_another_directory(tmp_path, rule):
    output = tmp_path / rule
    process = run_cli(tmp_path, f"rule={rule}", f"hydra.run.dir={output}")
    assert process.returncode == 0, process.stderr
    metadata = json.loads((output / "corpus/run.json").read_text())
    assert metadata["config"]["rule"] == rule
    assert metadata["config"]["backend"] == "demo"
    assert 1 <= metadata["ticks"] <= 12
    assert metadata["generated_utterances"] > 0
    assert not (output / "corpus/config.yaml").exists()
    assert not (output / "live.json").exists()
    assert json.loads((output / "corpus/seed.json").read_text())["source"] == "synthetic"
    assert f"rule={rule}" in (output / ".hydra/overrides.yaml").read_text()


def test_existing_corpus_is_rejected_without_replacing_its_logs(tmp_path):
    output = tmp_path / "run"
    first = run_cli(tmp_path, f"hydra.run.dir={output}")
    assert first.returncode == 0, first.stderr
    before = {
        path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()
    }
    second = run_cli(tmp_path, "rule=round_robin", "live=true", f"hydra.run.dir={output}")
    assert second.returncode != 0
    assert {
        path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()
    } == before


def test_failed_run_directory_is_also_protected(tmp_path):
    output = tmp_path / "failed"
    assert run_cli(tmp_path, "seed_file=missing.json", f"hydra.run.dir={output}").returncode != 0
    before = (output / ".hydra/config.yaml").read_bytes()
    assert run_cli(tmp_path, "rule=random", f"hydra.run.dir={output}").returncode != 0
    assert (output / ".hydra/config.yaml").read_bytes() == before


def test_existing_sweep_and_colliding_job_paths_are_rejected_before_writing(tmp_path):
    sweep = tmp_path / "sweep"
    args = ("-m", "max_ticks=1", f"hydra.sweep.dir={sweep}")
    assert run_cli(tmp_path, *args, "rule=bidding,random").returncode == 0
    before = {p.relative_to(sweep): p.read_bytes() for p in sweep.rglob("*") if p.is_file()}
    assert run_cli(tmp_path, *args, "rule=round_robin,random").returncode != 0
    assert {p.relative_to(sweep): p.read_bytes() for p in sweep.rglob("*") if p.is_file()} == before
    new = tmp_path / "collision"
    assert (
        run_cli(tmp_path, "-m", f"hydra.sweep.dir={new}", "hydra.sweep.subdir=same").returncode != 0
    )
    assert not new.exists()


def test_two_processes_cannot_claim_the_same_run(tmp_path):
    output = tmp_path / "race"
    args = [str(ENTRY_POINT), "max_ticks=1", f"hydra.run.dir={output}"]
    processes = [
        subprocess.Popen(args, cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(2)
    ]
    for process in processes:
        process.communicate(timeout=20)
    assert sorted(p.returncode for p in processes) == [0, 1]
    assert (output / "corpus/run.json").is_file()


@pytest.mark.parametrize("mode", ["none", "summary", "full"])
def test_memory_modes_are_wired_through_the_cli_and_saved(tmp_path, mode):
    output = tmp_path / mode
    process = run_cli(tmp_path, f"memory_mode={mode}", f"hydra.run.dir={output}")
    assert process.returncode == 0, process.stderr
    meta = json.loads((output / "corpus/run.json").read_text())
    assert meta["config"]["memory_mode"] == mode
    assert meta["prompt_version"] == "2"
    assert meta["schema_version"] == 2
    decisions = [
        json.loads(line) for line in (output / "corpus/decisions.jsonl").read_text().splitlines()
    ]
    assert any(event.get("decision_source") == "new" for event in decisions)
    for event in decisions:
        if "urge" in event:
            assert event["reflection"]
            assert event["decision_tick"] <= event["tick"]
    public = (output / "corpus/utterances.jsonl").read_text()
    assert "reflection" not in public and "private_memory" not in public


def test_seed_speakers_must_have_configured_personas(tmp_path):
    process = run_cli(
        tmp_path,
        "agents.0.name=SomeoneElse",
        f"hydra.run.dir={tmp_path / 'run'}",
    )
    assert process.returncode != 0
    assert "seed speakers" in process.stderr.lower()
    assert not (tmp_path / "run/corpus").exists()


@pytest.mark.parametrize("scenario", ["wording", "editing"])
def test_scenarios_run_with_matching_seed_and_personas(tmp_path, scenario):
    output = tmp_path / scenario
    process = run_cli(
        tmp_path,
        f"+scenario={scenario}",
        f"seed_file={CONFIG_DIR / 'seeds' / f'{scenario}.json'}",
        "max_ticks=1",
        f"hydra.run.dir={output}",
    )
    assert process.returncode == 0, process.stderr
    meta = json.loads((output / "corpus/run.json").read_text())
    seed = json.loads((output / "corpus/seed.json").read_text())
    assert seed["utterances"][0]["id"] == f"{scenario}-root"
    assert meta["config"]["n_agents"] == len(meta["config"]["agents"]) == 4
    assert all(agent["stance"] for agent in meta["config"]["agents"])


def test_multirun_saves_each_rule_and_random_seed_separately(tmp_path):
    sweep = tmp_path / "sweep"
    process = run_cli(
        tmp_path,
        "-m",
        "rule=round_robin,bidding,event_driven",
        "random_seed=7,42",
        f"hydra.sweep.dir={sweep}",
    )
    assert process.returncode == 0, process.stderr
    results = [json.loads(path.read_text()) for path in sweep.glob("*/corpus/run.json")]
    assert len(results) == 6
    assert {(r["config"]["rule"], r["config"]["random_seed"]) for r in results} == {
        (rule, seed) for rule in ("round_robin", "bidding", "event_driven") for seed in (7, 42)
    }


@pytest.mark.parametrize("flag", ["--config-path", "--config-dir"])
@pytest.mark.parametrize("config_name", ["experiment", "nested/experiment"])
def test_custom_config_seed_path_survives_hydra_chdir(tmp_path, flag, config_name):
    custom = tmp_path / "custom"
    config_path = custom / f"{config_name}.yaml"
    config_path.parent.mkdir(parents=True)
    data = yaml.safe_load((CONFIG_DIR / "config.yaml").read_text())
    data["seed_file"] = "seed.json"
    config_path.write_text("# @package _global_\n" + yaml.safe_dump(data))
    # Relative seed paths are read from the launch directory, not the config directory
    # and not the directory Hydra chdirs into.
    (tmp_path / "seed.json").write_bytes((CONFIG_DIR / "seeds/example.json").read_bytes())
    output = tmp_path / "result"
    process = run_cli(
        tmp_path,
        flag,
        str(custom),
        "--config-name",
        config_name,
        "hydra.job.chdir=true",
        f"hydra.run.dir={output}",
    )
    assert process.returncode == 0, process.stderr
    result = json.loads((output / "corpus/run.json").read_text())
    assert result["config"]["seed_file"] == "seed.json"
    assert result["generated_utterances"] > 0


def test_persona_placement_is_wired_through_the_cli_and_saved(tmp_path):
    output = tmp_path / "system"
    process = run_cli(tmp_path, "persona_placement=system", f"hydra.run.dir={output}")
    assert process.returncode == 0, process.stderr
    meta = json.loads((output / "corpus/run.json").read_text())
    assert meta["config"]["persona_placement"] == "system"
    assert meta["prompt_version"] == "2"
