import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

PROJECT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT / "src/conflict_sim/conf"


def run_cli(cwd, *args):
    return subprocess.run(
        [sys.executable, "-m", "conflict_sim", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


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
    assert (output / "corpus/config.yaml").exists()
    assert metadata["seed"]["source"] == "synthetic"
    assert f"rule={rule}" in (output / ".hydra/overrides.yaml").read_text()


def test_existing_corpus_is_rejected_without_replacing_its_logs(tmp_path):
    output = tmp_path / "run"
    first = run_cli(tmp_path, f"hydra.run.dir={output}")
    assert first.returncode == 0, first.stderr
    before = (output / "corpus/run.json").read_bytes()
    second = run_cli(tmp_path, f"hydra.run.dir={output}")
    assert second.returncode != 0
    assert (output / "corpus/run.json").read_bytes() == before


def test_seed_speakers_must_have_configured_personas(tmp_path):
    process = run_cli(
        tmp_path,
        "agents.0.name=SomeoneElse",
        f"hydra.run.dir={tmp_path / 'run'}",
    )
    assert process.returncode != 0
    assert "seed speakers" in process.stderr.lower()
    assert not (tmp_path / "run/corpus").exists()


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
    seed_path = config_path.parent / "seed.json"
    seed_path.write_bytes((CONFIG_DIR / "seeds/example.json").read_bytes())
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
    assert result["config"]["seed_file"] == str(seed_path)
