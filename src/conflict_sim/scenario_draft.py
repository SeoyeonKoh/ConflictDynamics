"""The draft a scenario generator edits: one company and one scenario, checked by the engine."""

import copy
from collections import Counter
from datetime import date

import yaml
from pydantic import ValidationError

from .company import (
    CONF_DIR,
    CompanyAgent,
    CompanyEnvironment,
    CompanyPreset,
    ConflictEvent,
    DiscPolicy,
    OfficeSpec,
    OrganizationIdentity,
    OrganizationRules,
    OrganizationSpec,
    PersonaDataset,
    ProjectDefinition,
    RaciEntry,
    RuntimeReadiness,
    WorkflowSpec,
    WorkflowTask,
    load_company_preset,
)
from .company_runtime import (
    TASK_AUTHORITY_SCOPE,
    C15Scenario,
    Experiment,
    build_config,
    load_c15_scenario,
)
from .models import Config, NonEmptyText, ValidatedModel

FACTORS = ("structure", "work", "disposition", "event")
OFFICE = "large_korean_enterprise"
FIXED = "korean_enterprise_10_ko"  # the preset whose fixed org and persona values a draft reuses
IGNORED = ("scenario.id", "scenario.research_question")
STRUCTURE_FIELDS = {"reports_to", "authorities", "department", "team", "position", "title", "role"}
# The engine's persona text is built from role, department, style, goal, priority and pressure
# (company_runtime._agent_spec); each of those is compared on its own field, so it is skipped.
DERIVED_FIELDS = {"persona"}
DISPOSITION_FIELDS = {
    "communication_style",
    "pressure_response",
    "conflict_style",
    "relationship_notes",
    "work_priority",
    "disc",
    "backstory",
}


class PatchError(ValueError):
    pass


class Department(ValidatedModel):
    id: NonEmptyText
    name: NonEmptyText


class CompanyDraft(ValidatedModel):
    organization: NonEmptyText  # company name
    project: NonEmptyText  # project name
    departments: list[Department]
    people: list[CompanyAgent]
    tasks: list[WorkflowTask]  # authority_scope filled explicitly
    conflict_events: list[ConflictEvent] = []
    raci: dict[NonEmptyText, RaciEntry] = {}


class Version(ValidatedModel):
    company: CompanyDraft
    scenario: dict  # C15Scenario fields except id, preset and experiment


def _yaml(path):
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def version_from_scenario(name: str) -> Version:
    """An existing scenario and its preset as a draft that builds the same config."""
    scenario = load_c15_scenario(name)
    preset = load_company_preset(scenario.preset)
    org = preset.environment.org
    tasks = [
        task.model_copy(
            update={"authority_scope": task.authority_scope or TASK_AUTHORITY_SCOPE.get(task.id)}
        )
        for task in org.workflow.tasks
    ]
    company = CompanyDraft(
        organization=org.organization.name,
        project=org.project.name,
        departments=[
            Department(id=d, name=org.department_names.get(d, d)) for d in org.departments
        ],
        people=list(preset.personas.agents),
        tasks=tasks,
        conflict_events=list(org.conflict_events),
        raci=dict(org.raci),
    )
    data = scenario.model_dump(mode="json", exclude={"id", "preset", "experiment"})
    return Version(company=company, scenario=data)


def preset_of(company: CompanyDraft, preset_id: str) -> CompanyPreset:
    """The generated company preset of a draft; fixed fields come from the existing presets."""
    fixed_org = _yaml(CONF_DIR / "environment" / "org" / f"{FIXED}.yaml")
    fixed_personas = _yaml(CONF_DIR / "personas" / f"{FIXED}.yaml")
    people = company.people
    root = next((p.id for p in people if p.reports_to is None), "none")
    discs = Counter(p.disc for p in people)
    evaluators = [p.id for p in people if any(g.kind == "evaluate" for g in p.authorities)]
    org = OrganizationSpec(
        schema_version=1,
        id=preset_id,
        organization=OrganizationIdentity(
            name=company.organization,
            synthetic=True,
            reference_note="A synthetic company written by the scenario generator.",
        ),
        project=ProjectDefinition(
            name=company.project,
            structure="functional_matrix_lite",
            product_type="connected_digital_product_service_feature",
            manager_id=root,
        ),
        departments=[d.id for d in company.departments],
        department_names={d.id: d.name for d in company.departments if d.name != d.id},
        job_families=list(dict.fromkeys(p.job_family for p in people)),
        roles=list(dict.fromkeys(p.role for p in people)),
        career_levels=fixed_org["career_levels"],
        positions=fixed_org["positions"],
        authority_kinds=fixed_org["authority_kinds"],
        rules=OrganizationRules(**{**fixed_org["rules"], "evaluation_authority": evaluators}),
        raci=company.raci,
        workflow=WorkflowSpec(
            task_states=fixed_org["workflow"]["task_states"], tasks=company.tasks
        ),
        conflict_events=company.conflict_events,
        engine_handoff=fixed_org["engine_handoff"],
        evidence_tags=["generated"],
    )
    personas = PersonaDataset(
        schema_version=1,
        dataset_id=preset_id,
        synthetic=True,
        project=company.project,
        disc_policy=DiscPolicy(
            purpose="communication_tendency_only",
            target_counts={d: discs[d] for d in ("D", "i", "S", "C") if discs[d]},
            prohibited_inferences=fixed_personas["disc_policy"]["prohibited_inferences"],
        ),
        agents=people,
    )
    office = OfficeSpec.model_validate(
        _yaml(CONF_DIR / "environment" / "office" / f"{OFFICE}.yaml")
    )
    return CompanyPreset(
        preset_id=preset_id,
        baseline="A1B1C1",
        generated=True,
        personas=personas,
        environment=CompanyEnvironment(office=office, org=org),
        runtime=RuntimeReadiness(
            executable_on_current_engine=True,
            validation_command=f"uv run conflict-company-validate {preset_id}",
            smoke_test_scope="deterministic demo run of its scenario; no paid LLM call.",
        ),
    )


def scenario_of(
    version: Version, scenario_id: str, preset: str, experiment: Experiment | None
) -> C15Scenario:
    return C15Scenario.model_validate(
        {**version.scenario, "id": scenario_id, "preset": preset, "experiment": experiment}
    )


def config_of(version: Version) -> Config:
    """The engine config the draft runs as; raises when the engine rejects it."""
    scenario = scenario_of(version, "draft", "draft", None)
    return build_config(scenario, preset_of(version.company, "draft"))


def check(version: Version) -> list[str]:
    """The engine's objections to the draft, one per line; [] when it builds."""
    try:
        config_of(version)
    except ValidationError as error:
        return [
            f"{'.'.join(map(str, e['loc']))}: {e['msg']}" if e["loc"] else e["msg"]
            for e in error.errors()
        ]
    except ValueError as error:
        return [str(error)]
    except Exception as error:  # the engine assumes what it does not check; say what broke
        return _project_problems(version) or [f"{type(error).__name__}: {error}"]
    return []


def _project_problems(version: Version) -> list[str]:
    """What the project rotation needs and the engine does not check: people in each step's
    department, and steps that do not follow each other in a circle."""
    departments = {p.department for p in version.company.people}
    problems = []
    for project in scenario_of(version, "draft", "draft", None).projects:
        for step in project.steps:
            if (department := step.department or project.department) not in departments:
                problems.append(f"Project {project.id} step {step.key}: no one in {department}")
        pending = {step.key: set(step.after) for step in project.steps}
        while ready := {key for key, after in pending.items() if not after & set(pending)}:
            pending = {key: after for key, after in pending.items() if key not in ready}
        if pending:
            problems.append(f"Project {project.id} steps follow each other in a cycle")
    return problems


def _keyed(items):
    """A list as a dict by item name or id, when every item has a distinct one."""
    keys = [i.get("name") or i.get("id") if isinstance(i, dict) else None for i in items]
    if None in keys or len(set(keys)) != len(keys):
        return None
    return dict(zip(keys, items))


def _walk(path, a, b, out):
    if a == b or path in IGNORED:
        return
    parts = path.split(".")
    if parts[0] == "agents" and len(parts) == 3 and parts[2] in DERIVED_FIELDS:
        return
    if isinstance(a, list) and isinstance(b, list) and None not in (_keyed(a), _keyed(b)):
        a, b = _keyed(a), _keyed(b)
    if isinstance(a, dict) and isinstance(b, dict):
        for key in dict.fromkeys([*a, *b]):
            _walk(f"{path}.{key}" if path else str(key), a.get(key), b.get(key), out)
    else:
        out.append((path, a, b))


def _under(path, *prefixes):
    return any(path == p or path.startswith(p + ".") for p in prefixes)


def _factor(path, a, b, steps):
    parts = path.split(".")
    if parts[0] == "agents" and len(parts) == 2 or path == "n_agents":
        return "structure"  # a person joins or leaves
    if parts[0] == "agents" and len(parts) > 2 and parts[2] in STRUCTURE_FIELDS:
        return "structure"
    if _under(path, "environment.org.departments"):
        return "structure"
    if (
        parts[:3] == ["environment", "org", "tasks"]
        and len(parts) > 4
        and parts[3] in steps
        and parts[4] in ("owner", "reviewers", "authority_scope")
    ):
        return "structure"  # a project step's owner and reviewer follow the org (rotation, manager)
    if parts[0] == "agents" and len(parts) > 2 and parts[2] in DISPOSITION_FIELDS:
        return "disposition"
    if _under(path, "scenario.shocks", "scenario.interventions"):
        return "event"
    if parts[:3] == ["environment", "org", "tasks"]:
        if len(parts) > 4 and parts[4] == "arrives":
            return "event"
        if len(parts) == 4 and any(
            isinstance(v, dict) and v.get("arrives") is not None for v in (a, b)
        ):
            return "event"  # work that comes in during the run, added or dropped whole
    if _under(
        path,
        "environment.org.tasks",
        "scenario.meetings",
        "weekly_operations",
        "environment.weekly_operations",
    ):
        return "work"
    return "other"


def diff(a: Version, b: Version) -> list[dict]:
    """Where the two drafts' engine configs differ, each with the factor it belongs to."""
    dumps = config_of(a).model_dump(), config_of(b).model_dump()
    steps = {t["id"] for d in dumps for t in d["environment"]["org"]["tasks"] if t["group"]}
    out = []
    _walk("", *dumps, out)
    return [
        {"path": path, "factor": _factor(path, x, y, steps), "a": x, "b": y} for path, x, y in out
    ]


def _tokens(path):
    if not path.startswith("/"):
        raise PatchError(f"no such path: {path}")
    return [t.replace("~1", "/").replace("~0", "~") for t in path[1:].split("/")]


def _index(token):
    if not token.isdigit():
        raise ValueError(token)
    return int(token)


def apply_ops(doc: dict, ops: list[dict]) -> dict:
    """JSON-patch add / replace / remove on a copy of doc."""
    doc = copy.deepcopy(doc)
    for op in ops:
        kind, path = op.get("op"), op.get("path", "")
        if kind not in ("add", "replace", "remove"):
            raise PatchError(f"unsupported op: {kind}")
        if kind != "remove" and "value" not in op:
            raise PatchError(f"op needs a value: {path}")
        *parents, last = _tokens(path)
        target = doc
        try:
            for token in parents:
                target = target[_index(token) if isinstance(target, list) else token]
            if isinstance(target, list):
                if kind == "add" and last == "-":
                    target.append(copy.deepcopy(op["value"]))
                    continue
                index = _index(last)
                if not 0 <= index < len(target) + (kind == "add"):
                    raise IndexError(index)
                if kind == "add":
                    target.insert(index, copy.deepcopy(op["value"]))
                elif kind == "replace":
                    target[index] = copy.deepcopy(op["value"])
                else:
                    del target[index]
            elif isinstance(target, dict):
                if kind != "add" and last not in target:
                    raise KeyError(last)
                if kind == "remove":
                    del target[last]
                else:
                    target[last] = copy.deepcopy(op["value"])
            else:
                raise TypeError(path)
        except (KeyError, IndexError, ValueError, TypeError):
            raise PatchError(f"no such path: {path}") from None
    return doc


def _text(data, directive: str = "") -> str:
    """YAML under the generator's note; a hydra directive must come before any other line."""
    header = (
        f"# Generated by the scenario generator ({date.today().isoformat()}); "
        "edit through the generator or by hand.\n"
    )
    return directive + header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def files_of(
    version: Version, slug: str, *, experiment: Experiment | None, reuse_preset: str | None
) -> dict[str, str]:
    """The conf-relative YAML files a saved draft is: its company preset (unless it reuses one)
    and its scenario, all named gen_<slug>."""
    name = f"gen_{slug}"
    files = {}
    if reuse_preset is None:
        preset = preset_of(version.company, name)
        company = {
            "defaults": [
                {"/personas": name},
                {"/environment/office": OFFICE},
                {"/environment/org": name},
                "_self_",
            ],
            "preset_id": name,
            "baseline": preset.baseline,
            "generated": True,
            "runtime": preset.runtime.model_dump(mode="json"),
        }
        files[f"company/{name}.yaml"] = _text(company, "# @package _global_\n")
        files[f"personas/{name}.yaml"] = _text(preset.personas.model_dump(mode="json"))
        files[f"environment/org/{name}.yaml"] = _text(
            preset.environment.org.model_dump(mode="json")
        )
    scenario = scenario_of(version, name, reuse_preset or name, experiment)
    files[f"scenario/company_c15/{name}.yaml"] = _text(scenario.model_dump(mode="json"))
    return files
