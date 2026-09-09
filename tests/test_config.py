from pathlib import Path

import pytest
import yaml
from hydra import compose, initialize_config_dir

from conflict_sim.cli import parse_config
from conflict_sim.models import Config


def config_data():
    return {
        "n_agents": 3,
        "seed_file": "seeds/example.json",
        "agents": [
            {"name": name, "persona": "Prefers primary sources.", "availability": 0.7}
            for name in ["A", "B", "C"]
        ],
    }


def write_config(tmp_path, data):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def load_config(path: Path, overrides: list[str] | None = None) -> Config:
    """Compose with Hydra's own API, then hand the result to the production parser."""
    with initialize_config_dir(version_base="1.3", config_dir=str(path.parent)):
        return parse_config(compose(config_name=path.stem, overrides=overrides or []))


def test_composed_config_is_validated(tmp_path):
    cfg = load_config(write_config(tmp_path, config_data()))
    assert cfg.seed_file == "seeds/example.json"
    assert len(cfg.agents) == 3


@pytest.mark.parametrize(
    "field,value",
    [
        ("n_agents", 4),
        ("n_agents", 2),
        ("max_ticks", 0),
        ("max_ticks", True),
        ("silence_limit", 0),
        ("temperature", float("nan")),
        ("temperature", -1),
        ("rule", "typo"),
        ("backend", "typo"),
        ("unknown_option", 5),
        ("seed_file", ""),
        ("context_size", 0),
    ],
)
def test_bad_config_is_rejected_before_running(tmp_path, field, value):
    data = config_data()
    data[field] = value
    with pytest.raises(ValueError):
        load_config(write_config(tmp_path, data))


def test_duplicate_agents_are_rejected(tmp_path):
    data = config_data()
    data["agents"][1]["name"] = "A"
    with pytest.raises(ValueError):
        load_config(write_config(tmp_path, data))


@pytest.mark.parametrize("availability", [-0.1, 1.1, float("nan"), True])
def test_availability_is_a_probability(tmp_path, availability):
    data = config_data()
    data["agents"][0]["availability"] = availability
    with pytest.raises(ValueError):
        load_config(write_config(tmp_path, data))


def test_hydra_composes_config_groups_and_resolves_overrides(tmp_path):
    group = tmp_path / "treatment"
    group.mkdir()
    (group / "bidding.yaml").write_text("# @package _global_\nrule: bidding\nmax_ticks: 3\n")
    (group / "random.yaml").write_text("# @package _global_\nrule: random\nmax_ticks: 5\n")
    data = config_data() | {
        "defaults": [{"treatment": "bidding"}, "_self_"],
        "silence_limit": "${max_ticks}",
        "random_seed": 7,
    }
    path = write_config(tmp_path, data)
    first = load_config(path)
    second = load_config(path, overrides=["treatment=random", "random_seed=12"])
    assert (first.rule, first.max_ticks, first.silence_limit) == ("bidding", 3, 3)
    assert (second.rule, second.max_ticks, second.silence_limit, second.random_seed) == (
        "random",
        5,
        5,
        12,
    )
