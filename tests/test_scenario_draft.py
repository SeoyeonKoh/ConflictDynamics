import shutil

import pytest
import yaml

from conflict_sim import company, company_runtime
from conflict_sim.company_runtime import Experiment, build_company_config
from conflict_sim.scenario_draft import (
    PatchError,
    Version,
    apply_ops,
    check,
    config_of,
    diff,
    files_of,
    preset_of,
    version_from_scenario,
)


def edit(version: Version, *ops: dict) -> Version:
    """Models are frozen: a version changes through a patch of its dump, as the generator does."""
    return Version.model_validate(apply_ops(version.model_dump(), list(ops)))


def test_an_existing_scenario_round_trips_to_the_same_config():
    v = version_from_scenario("r10_human")
    assert config_of(v).model_dump(exclude={"scenario"}) == build_company_config(
        "r10_human"
    ).model_dump(exclude={"scenario"})
    assert check(v) == []


def test_a_draft_company_is_generated_and_fills_authority_scopes():
    v = version_from_scenario("r10_human")
    scopes = {task.id: task.authority_scope for task in v.company.tasks}
    assert scopes["T03"] == "requirements" and scopes["T01"] is None
    preset = preset_of(v.company, "gen_x")
    assert preset.generated and preset.environment.org.project.manager_id == "HDS-001"
    assert preset.personas.disc_policy.target_counts == {"D": 3, "i": 3, "S": 2, "C": 2}


def test_a_broken_version_reports_engine_errors():
    v = version_from_scenario("r10_human")
    v = edit(v, {"op": "replace", "path": "/company/tasks/0/owner", "value": "NOBODY"})
    assert any("unknown agents" in e for e in check(v))
    with pytest.raises(ValueError):
        config_of(v)


def test_a_project_in_a_department_with_no_people_is_reported_not_raised():
    v = version_from_scenario("r10_human")
    v = edit(v, {"op": "replace", "path": "/scenario/projects/0/department", "value": "NOPE"})
    errors = check(v)
    assert errors and any("NOPE" in e for e in errors)


def test_a_cycle_in_project_steps_is_reported_not_raised():
    v = version_from_scenario("r10_human")
    v = edit(
        v, {"op": "replace", "path": "/scenario/projects/0/steps/0/after", "value": ["rollout"]}
    )
    errors = check(v)
    assert errors and any("P1" in e for e in errors)


def test_diff_compares_lists_with_repeated_ids_by_position():
    a = version_from_scenario("r10_human")
    shock = {"id": "x", "event_id": "E02", "kind": "deadline_compression", "day": 0}
    a2 = edit(a, {"op": "replace", "path": "/scenario/engine/shocks", "value": [
        {**shock, "tick": 5}, {**shock, "tick": 7}]})  # fmt: skip
    b2 = edit(a, {"op": "replace", "path": "/scenario/engine/shocks", "value": [
        {**shock, "tick": 6}, {**shock, "tick": 7}]})  # fmt: skip
    assert [(d["path"], d["factor"]) for d in diff(a2, b2)] == [("scenario.shocks", "event")]


def test_diff_names_the_factor_of_each_change():
    a = version_from_scenario("r10_human")
    b = edit(
        a,
        {
            "op": "replace",
            "path": "/company/people/2/communication_style",
            "value": "피드백할 때 깎아내리고 비꼬는 말을 쓴다.",
        },
        {"op": "replace", "path": "/company/people/3/reports_to", "value": a.company.people[1].id},
    )
    factors = {d["factor"] for d in diff(a, b)}
    assert factors == {"disposition", "structure"}


def test_diff_puts_shocks_and_arriving_work_under_event():
    a = version_from_scenario("r10_human")
    shock = {"id": "late", "event_id": "E02", "kind": "deadline_compression", "day": 0, "tick": 5}
    b = edit(a, {"op": "add", "path": "/scenario/engine/shocks/-", "value": shock})
    assert [(d["path"], d["factor"]) for d in diff(a, b)] == [("scenario.shocks.late", "event")]


def test_an_identical_copy_has_no_diff():
    a = version_from_scenario("r10_human")
    assert diff(a, a.model_copy(deep=True)) == []


def test_a_patch_to_a_missing_path_changes_nothing():
    doc = {"a": [1]}
    with pytest.raises(PatchError, match="no such path: /b/0"):
        apply_ops(doc, [{"op": "replace", "path": "/b/0", "value": 2}])
    assert doc == {"a": [1]}


def test_a_patch_adds_replaces_and_removes_on_a_copy():
    doc = {"a": [1, 2], "b": {"c": 3}}
    out = apply_ops(
        doc,
        [
            {"op": "add", "path": "/a/-", "value": 9},
            {"op": "add", "path": "/a/0", "value": 0},
            {"op": "replace", "path": "/b/c", "value": 4},
            {"op": "remove", "path": "/a/1"},
            {"op": "add", "path": "/d", "value": "new"},
        ],
    )
    assert out == {"a": [0, 2, 9], "b": {"c": 4}, "d": "new"}
    assert doc == {"a": [1, 2], "b": {"c": 3}}


def test_a_patch_without_a_value_says_so():
    with pytest.raises(PatchError, match="op needs a value: /a/0"):
        apply_ops({"a": [1]}, [{"op": "replace", "path": "/a/0"}])


@pytest.fixture
def conf_copy(tmp_path, monkeypatch):
    conf = tmp_path / "conf"
    shutil.copytree(company.CONF_DIR, conf)
    monkeypatch.setattr(company, "CONF_DIR", conf)
    monkeypatch.setattr(company_runtime, "CONF_DIR", conf)
    return conf


def write(conf, files):
    for path, text in files.items():
        (conf / path).write_text(text, encoding="utf-8")


def test_written_files_load_through_hydra(conf_copy):
    files = files_of(version_from_scenario("r10_human"), "t1", experiment=None, reuse_preset=None)
    assert sorted(files) == [
        "company/gen_t1.yaml",
        "environment/org/gen_t1.yaml",
        "personas/gen_t1.yaml",
        "scenario/company_c15/gen_t1.yaml",
    ]
    note = "# Generated by the scenario generator ("
    # Hydra reads `# @package` only from the leading lines, so the company file puts it first.
    assert files["company/gen_t1.yaml"].startswith("# @package _global_\n" + note)
    assert all(t.startswith(note) for p, t in files.items() if not p.startswith("company/"))
    write(conf_copy, files)
    config = build_company_config("gen_t1")
    assert config.n_agents == 10
    assert company.load_company_preset("gen_t1").generated


def test_a_variant_that_keeps_the_company_writes_only_its_scenario(conf_copy):
    experiment = Experiment(id="x1", role="variant", factor="event")
    files = files_of(
        version_from_scenario("r10_human"),
        "t2",
        experiment=experiment,
        reuse_preset="korean_enterprise_10_ko",
    )
    assert list(files) == ["scenario/company_c15/gen_t2.yaml"]
    data = yaml.safe_load(files["scenario/company_c15/gen_t2.yaml"])
    assert data["preset"] == "korean_enterprise_10_ko" and data["experiment"]["id"] == "x1"
    write(conf_copy, files)
    assert build_company_config("gen_t2").n_agents == 10
