"""Bridge the locked C-14 company preset into the executable company-world engine."""

import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from .company import load_company_preset
from .models import (
    AgentSpec,
    Config,
    EnvironmentConfig,
    OfficeConfig,
    OrgConfig,
    PlaceSpec,
    ScenarioConfig,
    ScopedAuthority,
    TaskSpec,
    ValidatedModel,
)

CONF_DIR = Path(__file__).resolve().parents[2] / "conf"
COMPANY_MAP = Path(__file__).parent / "maps" / "company_office.json"  # the C-14 office

# Derived from the locked C-14 Job/Authority table. A missing entry means the task completes
# without an authority gate; named reviewers still remain interaction and evidence dependencies.
TASK_AUTHORITY_SCOPE = {
    "T03": "requirements",
    "T04": "experience_design",
    "T05": "architecture",
    "T06": "architecture",
    "T07": "architecture",
    "T08": "architecture",
    "T09": "quality_signoff",
    "T10": "deployment_checklist",
    "T11": "quality_signoff",
    "T12": "launch_plan",
    "T13": "quality_signoff",
    "T14": "release",
    "T15": "release",
}

PLACE_KIND = {
    "lobby": "lobby",
    "office": "office",
    "meeting_room": "meeting_room",
    "focus_room": "focus_room",
    "pantry": "pantry",
    "cafeteria": "cafeteria",
}


class TaskRuntime(ValidatedModel):
    id: str
    effort_ticks: int = Field(ge=1)
    due: int = Field(ge=0)


class C15Scenario(ValidatedModel):
    schema_version: Literal[1]
    id: str
    research_question: str
    manipulated_variable: str
    fixed_variables: list[str]
    max_days: int = Field(ge=1)
    overtime_ticks: int = Field(default=2, ge=0)
    seed: int
    task_runtime: list[TaskRuntime]
    engine: ScenarioConfig
    observable_outputs: list[str]
    theory_tags: list[str]
    manipulation_check: list[str]
    termination: Literal["max_days"] = "max_days"

    @model_validator(mode="after")
    def unique_runtime_tasks(self):
        ids = [task.id for task in self.task_runtime]
        if len(ids) != len(set(ids)):
            raise ValueError("Scenario task_runtime IDs must be unique")
        return self


class GeneratedTask(ValidatedModel):
    id: str
    description: str
    effort_ticks: int = Field(ge=1)
    due: int = Field(ge=0)
    owner: str
    depends_on: list[str] = []
    skills: list[str] = []


class GeneratedTaskPlan(ValidatedModel):
    tasks: list[GeneratedTask] = Field(min_length=1)


def load_c15_scenario(name: str) -> C15Scenario:
    path = CONF_DIR / "scenario" / "company_c15" / f"{name}.yaml"
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    parent = data.pop("extends", None)
    if parent is not None:
        base = load_c15_scenario(parent).model_dump()
        base.update(data)
        data = base
    return C15Scenario.model_validate(data)


def build_company_config(
    scenario_name: str = "s0_baseline",
    *,
    backend: Literal["demo", "openai"] = "demo",
) -> Config:
    """Compose C-14 once, then add only C-15 runtime/scenario assumptions."""
    preset = load_company_preset()
    scenario = load_c15_scenario(scenario_name)
    runtime = {task.id: task for task in scenario.task_runtime}
    workflow_ids = {task.id for task in preset.environment.org.workflow.tasks}
    if set(runtime) != workflow_ids:
        missing = sorted(workflow_ids - set(runtime))
        extra = sorted(set(runtime) - workflow_ids)
        raise ValueError(f"Scenario task_runtime mismatch; missing={missing}, extra={extra}")

    agents = [_agent_spec(agent) for agent in preset.personas.agents]
    office = OfficeConfig(
        places=[
            PlaceSpec(
                id=place.id,
                kind=PLACE_KIND[place.id],
                capacity=place.capacity,
            )
            for place in preset.environment.office.places
        ]
    )
    tasks = [
        TaskSpec(
            id=task.id,
            description=task.name.replace("_", " "),
            effort_ticks=runtime[task.id].effort_ticks,
            due=runtime[task.id].due,
            owner=task.owner,
            depends_on=list(task.predecessors),
            contributors=list(task.contributors),
            reviewers=list(task.reviewers),
            handoff_to=list(task.handoff_to),
            authority_scope=TASK_AUTHORITY_SCOPE.get(task.id),
        )
        for task in preset.environment.org.workflow.tasks
    ]
    org = OrgConfig(
        departments=list(preset.environment.org.departments),
        titles={position: [] for position in preset.environment.org.positions},
        tasks=tasks,
        max_task_workers=4,  # owner, contributors and helpers together
    )
    kwargs = {}
    if backend == "openai":
        kwargs = {
            "model_decide": "gpt-6-luna",
            "model_speak": "gpt-6-luna",
            "model_embed": "text-embedding-3-small",
            "reasoning_effort": "none",
            "max_tokens_decide": 2048,
            "max_total_tokens": 500_000,
        }
    return Config(
        backend=backend,
        n_agents=len(agents),
        agents=agents,
        environment=EnvironmentConfig(office=office, org=org, chase_cooldown_ticks=8),
        max_days=scenario.max_days,
        ticks_per_day=preset.environment.office.time.normal_workday_ticks,
        overtime_ticks_per_day=scenario.overtime_ticks,
        random_seed=scenario.seed,
        workers=4,
        relation_appraisal="listener",
        scenario=scenario.engine,
        language="English",
        stream_map=str(COMPANY_MAP),
        **kwargs,
    )


def apply_initial_relationships(agents) -> None:
    """Load the symmetric C-14 baseline; no pair starts hostile or aggrieved."""
    path = CONF_DIR / "relations" / "hds_initial.yaml"
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    by_name = {agent.name: agent for agent in agents}
    for row in data["relations"]:
        for source, target in ((row["a"], row["b"]), (row["b"], row["a"])):
            relation = by_name[source].state.relation(target)
            relation.relation = row["valence"]
            relation.familiarity = row["familiarity"]
            relation.task_trust = row["task_trust"]


def _agent_spec(agent) -> AgentSpec:
    persona = (
        f"{agent.role} in {agent.department}. {agent.communication_style} "
        f"Project goal: {agent.project_goal} Work priority: {agent.personal_work_priority} "
        f"Under pressure: {agent.pressure_response} DISC is only a communication tendency."
    )
    return AgentSpec(
        name=agent.id,
        display_name=agent.name,
        persona=persona,
        disc=agent.disc,
        department=agent.department,
        title=agent.position,
        position=agent.position,
        role=agent.role,
        career_level=agent.career_level,
        job_family=agent.job_family,
        reports_to=agent.reports_to,
        skills=list(agent.skills),
        hobbies=list(agent.hobbies),
        tenure_band=agent.tenure_band,
        project_goal=agent.project_goal,
        work_priority=agent.personal_work_priority,
        authorities=[
            ScopedAuthority(kind=grant.kind, scope=grant.scope) for grant in agent.authorities
        ],
    )


def generate_manager_tasks(
    llm,
    *,
    manager: AgentSpec,
    agents: list[AgentSpec],
    goal: str,
    deadline: int,
    existing_tasks: list[TaskSpec],
) -> list[TaskSpec]:
    """Generate and validate an optional manager plan without changing the static baseline."""
    payload = {
        "manager": manager.name,
        "goal": goal,
        "deadline": deadline,
        "agents": [
            {"id": agent.name, "role": agent.role, "skills": agent.skills} for agent in agents
        ],
        "existing_task_graph": [task.model_dump() for task in existing_tasks],
    }
    text = llm.complete(
        system=(
            "Generate a small work-task DAG. Use only supplied agent IDs, keep every due tick at "
            "or before the deadline, and return only JSON matching the supplied schema."
        ),
        prompt=json.dumps(payload, ensure_ascii=False),
        model="demo",
        temperature=0,
        json_mode=True,
        schema=GeneratedTaskPlan,
    )
    plan = GeneratedTaskPlan.model_validate_json(text)
    known = {agent.name for agent in agents}
    if unknown := {task.owner for task in plan.tasks} - known:
        raise ValueError(f"Generated tasks contain unknown owners: {sorted(unknown)}")
    if late := [task.id for task in plan.tasks if task.due > deadline]:
        raise ValueError(f"Generated tasks exceed the deadline: {late}")
    generated = [TaskSpec(**task.model_dump()) for task in plan.tasks]
    OrgConfig(
        departments=[manager.department or "company"], titles={"manager": []}, tasks=generated
    )
    return generated
