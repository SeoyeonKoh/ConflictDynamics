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
    MemoryConfig,
    OfficeConfig,
    OrgConfig,
    PlaceSpec,
    ScenarioConfig,
    ScopedAuthority,
    TaskSpec,
    ValidatedModel,
)
from .usage_audit import traced

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


class ProjectStep(ValidatedModel):
    key: str
    name: str
    effort_ticks: int = Field(ge=1)
    department: str | None = None  # another department's: a cross point; None: the project's own
    after: list[str] = []  # step keys within the same project


class Project(ValidatedModel):
    """A department's own project beside the joint core release. Its steps are owned in rotation
    within the department that does them and signed off by the project's lead; a step another
    department does is a cross point, where the project waits on help from outside."""

    id: str
    name: str
    department: str
    lead: str
    due: int
    start_after: list[str] = []  # core tasks the project waits for
    steps: list[ProjectStep]


class Deliverable(ValidatedModel):
    format: str
    criteria: str


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
    # Tasks that start with no owner and no contributors: the kickoff decides who takes them.
    unassigned: list[str] = []
    # Documents some tasks produce; the next tasks build on them and review checks them.
    deliverables: dict[str, Deliverable] = {}
    # When set, every other task (core and project steps) also ends in a document of this form.
    default_deliverable: Deliverable | None = None
    # What the office has on each task to work from (facts, figures, constraints), by task id.
    materials: dict[str, str] = {}
    # The company preset the scenario runs on, and the language its people speak and write in.
    preset: str = "large_korean_enterprise_20"
    language: str = "English"
    projects: list[Project] = []
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
    scenario = load_c15_scenario(scenario_name)
    preset = load_company_preset(scenario.preset)
    runtime = {task.id: task for task in scenario.task_runtime}
    workflow_ids = {task.id for task in preset.environment.org.workflow.tasks}
    if set(runtime) != workflow_ids:
        missing = sorted(workflow_ids - set(runtime))
        extra = sorted(set(runtime) - workflow_ids)
        raise ValueError(f"Scenario task_runtime mismatch; missing={missing}, extra={extra}")

    names = preset.environment.org.department_names
    agents = [_agent_spec(agent, scenario.language, names) for agent in preset.personas.agents]
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
            owner=None if task.id in scenario.unassigned else task.owner,
            depends_on=list(task.predecessors),
            contributors=[] if task.id in scenario.unassigned else list(task.contributors),
            reviewers=list(task.reviewers),
            handoff_to=list(task.handoff_to),
            authority_scope=TASK_AUTHORITY_SCOPE.get(task.id),
            deliverable=(
                scenario.deliverables[task.id].format if task.id in scenario.deliverables else None
            ),
            criteria=(
                scenario.deliverables[task.id].criteria
                if task.id in scenario.deliverables
                else None
            ),
        )
        for task in preset.environment.org.workflow.tasks
    ]
    tasks += _project_tasks(agents, scenario.projects)
    if unknown := set(scenario.materials) - {t.id for t in tasks}:
        raise ValueError(f"Materials for unknown tasks: {sorted(unknown)}")
    tasks = [
        t.model_copy(update={"materials": scenario.materials[t.id]})
        if t.id in scenario.materials
        else t
        for t in tasks
    ]
    if (default := scenario.default_deliverable) is not None:
        tasks = [
            t
            if t.deliverable
            else t.model_copy(update={"deliverable": default.format, "criteria": default.criteria})
            for t in tasks
        ]
    org = OrgConfig(
        departments=list(preset.environment.org.departments),
        titles={position: [] for position in preset.environment.org.positions},
        tasks=tasks,
        max_task_workers=4,  # owner, contributors and helpers together
        show_unowned=bool(scenario.unassigned),
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
        # Twenty people in one office observe each other constantly: at the default 150 the
        # C-16 run reflected 487 times (4 calls x 100 records each), most of its input tokens.
        stall_recheck_ticks=4,
        break_recovery=0.06,  # three times the passive decay: a break is worth taking
        memory=MemoryConfig(reflect_threshold=400, reflect_questions=2, reflect_window=50),
        scenario=scenario.engine,
        language=scenario.language,
        stream_map=str(COMPANY_MAP),
        **kwargs,
    )


def _project_tasks(agents, projects: list[Project]) -> list[TaskSpec]:
    members: dict[str, list] = {}
    for agent in agents:
        members.setdefault(agent.department, []).append(agent)
    turn = dict.fromkeys(members, 0)  # one rotation per department, across all projects
    manager = {agent.name: agent.reports_to for agent in agents}
    tasks = []
    for project in projects:
        steps = {step.key: step for step in project.steps}
        after = {key: [s.key for s in project.steps if key in s.after] for key in steps}

        def tail(key: str) -> int:  # the longest chain of effort still to come after this step
            return max((steps[k].effort_ticks + tail(k) for k in after[key]), default=0)

        for step in project.steps:
            department = step.department or project.department
            team = members[department]
            owner = team[turn[department] % len(team)].name
            turn[department] += 1
            # The project's lead signs off its steps, a cross point included (they asked for
            # it); the lead's own step goes to the lead's manager.
            reviewer = project.lead if owner != project.lead else manager[owner]
            tasks.append(
                TaskSpec(
                    id=f"{project.id}-{step.key}",
                    description=step.name,
                    effort_ticks=step.effort_ticks,
                    due=project.due - tail(step.key),
                    owner=owner,
                    depends_on=[f"{project.id}-{k}" for k in step.after] or project.start_after,
                    reviewers=[reviewer] if reviewer else [],
                    authority_scope="project" if reviewer else None,
                    group=f"{project.id} {project.name}",
                    cross=step.department is not None and step.department != project.department,
                )
            )
    return tasks


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


# The sentence a persona is told in, per language.
PERSONA_FORMS = {
    "English": "{role} in {department}. {style} Project goal: {goal} Work priority: {priority} "
    "Under pressure: {pressure} DISC is only a communication tendency.",
    "Korean": "{department} {role}. {style} 프로젝트 목표: {goal} 업무 우선순위: {priority}. "
    "압박을 받을 때: {pressure} DISC는 소통 성향일 뿐이다.",
}


def _agent_spec(agent, language: str = "English", department_names=None) -> AgentSpec:
    persona = PERSONA_FORMS.get(language, PERSONA_FORMS["English"]).format(
        role=agent.role,
        department=(department_names or {}).get(agent.department, agent.department),
        style=agent.communication_style,
        goal=agent.project_goal,
        priority=agent.personal_work_priority,
        pressure=agent.pressure_response,
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


@traced("manager_task_generation")
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
