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
    assert cfg.memory_mode == "summary"
    assert cfg.persona_placement == "system"


def test_silence_limit_is_gone_a_quiet_round_ends_a_session():
    with pytest.raises(ValueError, match="silence_limit"):
        Config(**(config_data() | {"silence_limit": 2}))


@pytest.mark.parametrize(
    "field,value",
    [
        ("n_agents", 4),
        ("n_agents", 2),
        ("max_ticks", 0),
        ("max_ticks", True),
        ("max_utterances", 0),
        ("max_tokens_decide", 0),
        ("max_tokens_speak", True),
        ("max_total_tokens", 0),
        ("max_input_chars", 0),
        ("temperature", float("nan")),
        ("temperature", -1),
        ("rule", "typo"),
        ("backend", "typo"),
        ("unknown_option", 5),
        ("seed_file", ""),
        ("context_size", 0),
        ("memory_mode", "typo"),
        ("persona_placement", "typo"),
        ("reasoning_effort", "typo"),
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


def test_hydra_overrides_memory_mode(tmp_path):
    data = config_data() | {"memory_mode": "summary"}
    cfg = load_config(write_config(tmp_path, data), ["memory_mode=full"])
    assert cfg.memory_mode == "full"


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
        "no_reply_ticks": "${max_ticks}",
        "random_seed": 7,
    }
    path = write_config(tmp_path, data)
    first = load_config(path)
    second = load_config(path, overrides=["treatment=random", "random_seed=12"])
    assert (first.rule, first.max_ticks, first.no_reply_ticks) == ("bidding", 3, 3)
    assert (second.rule, second.max_ticks, second.no_reply_ticks, second.random_seed) == (
        "random",
        5,
        5,
        12,
    )


# --- company simulation config (phase A) ---


def environment_data():
    return {
        "office": {
            "places": [
                {"id": "dev-office", "kind": "office"},
                {"id": "meeting-room", "kind": "meeting_room", "capacity": 4},
                {"id": "cafeteria", "kind": "cafeteria"},
            ]
        },
        "org": {
            "departments": ["dev"],
            "titles": {"manager": ["assign", "approve", "reject", "evaluate"], "engineer": []},
            "tasks": [
                {
                    "id": "spec",
                    "description": "Write the spec",
                    "effort_ticks": 8,
                    "due": 16,
                    "owner": "A",
                },
                {
                    "id": "api",
                    "description": "Ship the API",
                    "effort_ticks": 12,
                    "due": 28,
                    "owner": "B",
                    "depends_on": ["spec"],
                },
            ],
        },
    }


def company_data():
    data = config_data() | {"environment": environment_data()}
    for i, agent in enumerate(data["agents"]):
        agent.update(department="dev", title="manager" if i == 0 else "engineer")
        if i:
            agent["reports_to"] = "A"
    return data


def test_wiki_config_needs_no_environment(tmp_path):
    cfg = load_config(write_config(tmp_path, config_data()))
    assert cfg.environment is None
    assert (cfg.max_days, cfg.ticks_per_day) == (1, 32)


def test_memory_and_outcome_parameters_have_the_planned_defaults(tmp_path):
    cfg = load_config(write_config(tmp_path, config_data()))
    assert (cfg.memory.alpha_mood, cfg.memory.top_k, cfg.memory.relation_reflect_threshold) == (
        0.0,
        10,
        -30.0,
    )
    assert (cfg.w_valence, cfg.w_structural, cfg.public_mult, cfg.w_arousal) == (
        0.1,
        0.15,
        1.5,
        0.1,
    )
    assert (cfg.stress_decay, cfg.mood_window, cfg.no_reply_ticks) == (0.02, 8, 3)
    assert (cfg.blocked_nudge_ticks, cfg.blocked_report_ticks) == (2, 4)
    assert cfg.turns_per_tick == {"talk": 12, "message": 12}


def test_alpha_mood_is_the_only_free_parameter_and_is_overridable(tmp_path):
    data = config_data() | {"memory": {"alpha_mood": 0}}
    cfg = load_config(write_config(tmp_path, data), ["memory.alpha_mood=1"])
    assert cfg.memory.alpha_mood == 1.0
    with pytest.raises(ValueError):
        load_config(write_config(tmp_path, data), ["memory.alpha_mood=2"])


def test_twenty_agents_are_allowed(tmp_path):
    data = config_data() | {
        "n_agents": 20,
        "agents": [{"name": f"P{i}", "persona": "Works."} for i in range(20)],
    }
    assert len(load_config(write_config(tmp_path, data)).agents) == 20


def test_company_config_composes_environment_groups(tmp_path):
    cfg = load_config(write_config(tmp_path, company_data()))
    assert [place.id for place in cfg.environment.office.places][0] == "dev-office"
    assert cfg.environment.org.tasks[1].depends_on == ["spec"]
    assert cfg.agents[1].reports_to == "A"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["agents"][1].update(department="sales"),
        lambda d: d["agents"][1].update(title="intern"),
        lambda d: d["agents"][1].update(reports_to="Nobody"),
        lambda d: d["agents"][1].update(reports_to="B"),
        lambda d: d["environment"]["org"]["tasks"][0].update(owner="Nobody"),
        lambda d: d["environment"]["org"]["tasks"][1].update(depends_on=["missing"]),
        lambda d: d["environment"]["org"]["tasks"][1].update(id="spec"),
        lambda d: d["environment"]["office"]["places"][1].update(id="dev-office"),
        lambda d: d["environment"]["org"]["titles"].update(manager=["fire"]),
        lambda d: d["environment"]["office"]["places"][1].update(capacity=0),
    ],
)
def test_environment_references_must_resolve(tmp_path, mutate):
    data = company_data()
    mutate(data)
    with pytest.raises(ValueError):
        load_config(write_config(tmp_path, data))


def test_agents_may_reference_org_fields_only_with_an_environment(tmp_path):
    data = config_data()
    data["agents"][0]["department"] = "dev"
    with pytest.raises(ValueError):
        load_config(write_config(tmp_path, data))
