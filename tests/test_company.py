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
    assert not preset.runtime.executable_on_current_engine


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
