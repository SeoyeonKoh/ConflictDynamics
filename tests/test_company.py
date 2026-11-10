from collections import Counter
from pathlib import Path

import pytest
from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf

from conflict_sim.cli import parse_config
from conflict_sim.company import CompanyPreset, load_company_preset

PROJECT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT / "conf"


def preset_data():
    return load_company_preset().model_dump()


def test_c14_company_preset_composes_and_validates_cross_file_references():
    preset = load_company_preset()
    agents = preset.personas.agents
    org = preset.environment.org

    assert preset.baseline == "A1B1C1"
    assert len(agents) == 20
    assert len({agent.id for agent in agents}) == 20
    assert len({agent.name.casefold() for agent in agents}) == 20
    assert Counter(agent.disc for agent in agents) == Counter(D=5, i=5, S=5, C=5)
    assert [agent.id for agent in agents if agent.reports_to is None] == ["HDS-001"]
    assert len(org.workflow.tasks) == 15
    assert len(org.conflict_events) == 10
    assert preset.runtime.executable_on_current_engine


def test_every_agent_has_work_and_only_catalogued_org_fields_and_authorities():
    preset = load_company_preset()
    agents = preset.personas.agents
    org = preset.environment.org
    participation = set()

    for task in org.workflow.tasks:
        participation.update([task.owner, *task.contributors, *task.reviewers, *task.handoff_to])
    for entry in org.raci.values():
        participation.update(
            [entry.accountable, *entry.responsible, *entry.consulted, *entry.informed]
        )

    assert participation == {agent.id for agent in agents}
    assert all(agent.department in org.departments for agent in agents)
    assert all(agent.job_family in org.job_families for agent in agents)
    assert all(agent.role in org.roles for agent in agents)
    assert all(grant.kind in org.authority_kinds for agent in agents for grant in agent.authorities)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data["personas"]["agents"][1].__setitem__("reports_to", "missing"),
        lambda data: data["personas"]["agents"][0].__setitem__("reports_to", "HDS-002"),
        lambda data: data["environment"]["org"]["workflow"]["tasks"][0]["predecessors"].append(
            "T15"
        ),
        lambda data: data["environment"]["org"]["workflow"]["tasks"][0]["predecessors"].append(
            "missing"
        ),
        lambda data: data["environment"]["org"]["rules"].__setitem__("evaluation_authority", []),
        lambda data: data["environment"]["org"]["conflict_events"][0].__setitem__(
            "type", "unsupported_event"
        ),
    ],
)
def test_invalid_company_references_are_rejected(mutate):
    data = preset_data()
    mutate(data)
    with pytest.raises(ValueError):
        CompanyPreset.model_validate(data)


def test_existing_six_agent_demo_config_still_resolves_and_validates():
    with initialize_config_dir(version_base="1.3", config_dir=str(CONFIG_DIR)):
        raw = compose(config_name="config")
    cfg = parse_config(OmegaConf.create(OmegaConf.to_container(raw, resolve=True)))

    assert cfg.n_agents == 6
    assert len(cfg.agents) == 6
    assert cfg.backend == "demo"


def test_ten_agent_korean_preset_is_a_cut_of_the_twenty():
    preset = load_company_preset("korean_enterprise_10_ko")
    twenty = {a.id: a for a in load_company_preset("large_korean_enterprise_20_ko").personas.agents}
    agents = preset.personas.agents
    assert len(agents) == 10
    assert Counter(agent.disc for agent in agents) == Counter(D=3, i=3, S=2, C=2)
    assert all(twenty[a.id].name == a.name and twenty[a.id].role == a.role for a in agents)
    assert len(preset.environment.org.workflow.tasks) == 15


def _korean_10():
    return load_company_preset("korean_enterprise_10_ko").model_dump()


def _drop_people(data, gone):
    """Remove people and every reference to them; owners and parents fall back to the root."""
    keep = [a for a in data["personas"]["agents"] if a["id"] not in gone]
    root = next(a["id"] for a in keep if a["reports_to"] is None)
    for a in keep:
        if a["reports_to"] in gone:
            a["reports_to"] = root
        a["main_dependencies"] = [i for i in a["main_dependencies"] if i not in gone]
    data["personas"]["agents"] = keep
    data["personas"]["disc_policy"]["target_counts"] = dict(Counter(a["disc"] for a in keep))
    org = data["environment"]["org"]
    org["rules"]["evaluation_authority"] = [
        i for i in org["rules"]["evaluation_authority"] if i not in gone
    ]
    for entry in org["raci"].values():
        if entry["accountable"] in gone:
            entry["accountable"] = root
        for key in ("responsible", "consulted", "informed"):
            entry[key] = [i for i in entry[key] if i not in gone]
    for task in org["workflow"]["tasks"]:
        if task["owner"] in gone:
            task["owner"] = root
        for key in ("contributors", "reviewers", "handoff_to"):
            task[key] = [i for i in task[key] if i not in gone]
    return data


def _generated():
    data = _korean_10()
    data["generated"] = True
    return data


def test_a_generated_company_may_have_any_size_from_three_to_twenty():
    data = _generated()
    gone = {a["id"] for a in data["personas"]["agents"] if a["department"] == "Quality Engineering"}
    preset = CompanyPreset.model_validate(_drop_people(data, gone))
    assert len(preset.personas.agents) == 8


def test_a_generated_company_needs_one_root_but_not_the_project_manager():
    data = _generated()
    manager = data["environment"]["org"]["project"]["manager_id"]
    for a in data["personas"]["agents"]:
        if a["id"] == manager:
            a["reports_to"] = "HDS-002"
        elif a["id"] == "HDS-002":
            a["reports_to"] = None
    assert CompanyPreset.model_validate(data).generated


def test_a_generated_company_keeps_its_bounds():
    ids = [a["id"] for a in _generated()["personas"]["agents"]]
    with pytest.raises(ValueError, match="3 to 20 agents"):
        CompanyPreset.model_validate(_drop_people(_generated(), set(ids[2:])))

    data = _generated()
    data["environment"]["org"]["departments"] += ["Extra A", "Extra B", "Extra C"]
    with pytest.raises(ValueError, match="at most 6 departments"):
        CompanyPreset.model_validate(data)

    data = _generated()
    child = next(a for a in data["personas"]["agents"] if a["reports_to"] is not None)
    child["reports_to"] = None
    with pytest.raises(ValueError, match="exactly one reporting root"):
        CompanyPreset.model_validate(data)

    data = _generated()
    data["environment"]["org"]["workflow"]["tasks"] = []
    with pytest.raises(ValueError, match="at least one workflow task"):
        CompanyPreset.model_validate(data)


def test_a_generated_company_may_have_no_conflict_events():
    data = _generated()
    data["environment"]["org"]["conflict_events"] = []
    assert CompanyPreset.model_validate(data).environment.org.conflict_events == []


def test_an_existing_company_keeps_the_locked_rules():
    data = _korean_10()
    data["personas"]["agents"] = data["personas"]["agents"][:8]
    with pytest.raises(ValueError, match="20 agents"):
        CompanyPreset.model_validate(data)
