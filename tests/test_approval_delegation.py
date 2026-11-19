"""Manipulation-check and ceteris-paribus tests for the approval delegation experiment (S / D / M)."""

from __future__ import annotations

import copy
import json
import pytest

from conflict_sim.company import load_company_preset
from conflict_sim.company_runtime import build_company_config
from conflict_sim.environment.org import Org, Task
from conflict_sim.experiment import run_scenario


SCENARIOS = ("r10_auth_single", "r10_auth_scoped", "r10_auth_cross")
PRESETS = (
    "korean_enterprise_10_ko_auth_single",
    "korean_enterprise_10_ko",
    "korean_enterprise_10_ko_auth_cross",
)


@pytest.mark.parametrize("preset_name", PRESETS)
def test_approval_delegation_presets_validate(preset_name: str):
    preset = load_company_preset(preset_name)
    assert len(preset.personas.agents) == 10
    assert len(preset.environment.org.workflow.tasks) == 15


def _strip_authorities(cfg_dump: dict) -> dict:
    d = copy.deepcopy(cfg_dump)
    for agent in d["agents"]:
        agent.pop("authorities", None)
    org = d["environment"]["org"]
    if isinstance(org.get("agents"), dict):
        for agent in org["agents"].values():
            agent.pop("authorities", None)
    elif isinstance(org.get("agents"), list):
        for agent in org["agents"]:
            agent.pop("authorities", None)
    org.pop("grants", None)
    return d


def test_ceteris_paribus_only_authorities_differ():
    """S, D, M resolved configs must be byte-identical outside agent authorities."""
    dumps = {name: build_company_config(name, backend="demo").model_dump() for name in SCENARIOS}
    base = _strip_authorities(dumps["r10_auth_scoped"])
    assert _strip_authorities(dumps["r10_auth_single"]) == base
    assert _strip_authorities(dumps["r10_auth_cross"]) == base

    # Assign scopes must also be identical across all three conditions.
    for name in ("r10_auth_single", "r10_auth_cross"):
        for a_var, a_base in zip(dumps[name]["agents"], dumps["r10_auth_scoped"]["agents"]):
            assign_var = [g for g in a_var["authorities"] if g["kind"] == "assign"]
            assign_base = [g for g in a_base["authorities"] if g["kind"] == "assign"]
            assert assign_var == assign_base, f"assign mismatch for {a_var['name']} in {name}"


def _signers_for(scenario: str, task_id: str, owner: str) -> set[str]:
    cfg = build_company_config(scenario, backend="demo")
    org = Org(cfg.environment.org, cfg.agents)
    spec = next(t for t in cfg.environment.org.tasks if t.id == task_id)
    task = Task(spec=spec, due=spec.due, owner=owner, worked_by={owner: 2})
    return org.signers(task)


@pytest.mark.parametrize(
    "task_id,owner,expected_s,expected_d,expected_m",
    [
        ("T03", "HDS-003", {"HDS-001"}, {"HDS-002"}, {"HDS-002", "HDS-011"}),
        ("T04", "HDS-013", {"HDS-001"}, {"HDS-011"}, {"HDS-011", "HDS-002"}),
        ("T05", "HDS-005", {"HDS-001"}, {"HDS-001"}, {"HDS-014"}),
        ("T06", "HDS-006", {"HDS-001"}, {"HDS-005"}, {"HDS-005", "HDS-014"}),
        ("T09", "HDS-014", {"HDS-001"}, {"HDS-001"}, {"HDS-005"}),
        ("T10", "HDS-008", {"HDS-001"}, {"HDS-005", "HDS-014"}, {"HDS-005", "HDS-014"}),
        ("T11", "HDS-015", {"HDS-001"}, {"HDS-014"}, {"HDS-014", "HDS-005"}),
        ("T12", "HDS-002", {"HDS-001"}, {"HDS-001", "HDS-011"}, {"HDS-011"}),
        ("T13", "HDS-014", {"HDS-001"}, {"HDS-001"}, {"HDS-005"}),
        ("T14", "HDS-001", {"HDS-001"}, {"HDS-001"}, {"HDS-001"}),
        ("T15", "HDS-001", {"HDS-001"}, {"HDS-001"}, {"HDS-001"}),
    ],
)
def test_org_signers_branch_by_condition(
    task_id: str,
    owner: str,
    expected_s: set[str],
    expected_d: set[str],
    expected_m: set[str],
):
    """Org.signers must match Section 2.3's expected signer table for S, D, and M."""
    assert _signers_for("r10_auth_single", task_id, owner) == expected_s
    assert _signers_for("r10_auth_scoped", task_id, owner) == expected_d
    assert _signers_for("r10_auth_cross", task_id, owner) == expected_m


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_demo_smoke_run_completes(scenario: str, tmp_path):
    """Each condition completes a full demo-backend run cleanly."""
    run_dir = tmp_path / scenario
    run_scenario(scenario, run_dir, backend="demo")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
