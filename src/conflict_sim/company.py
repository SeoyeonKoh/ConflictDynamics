"""Compose and validate research-backed company-world presets without running the engine."""

import argparse
from collections import Counter
from pathlib import Path
from typing import Literal, Self

from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf
from pydantic import Field, model_validator

from .models import NonEmptyText, ValidatedModel

CONF_DIR = Path(__file__).resolve().parents[2] / "conf"

AgentId = NonEmptyText
CareerLevel = Literal["CL1", "CL2", "CL3", "CL4"]
Position = Literal["member", "senior_member", "functional_lead", "team_manager"]
DiscStyle = Literal["D", "i", "S", "C"]
AuthorityKind = Literal["assign", "approve", "reject", "evaluate"]
EXPECTED_CONFLICT_EVENTS = {
    "task_dependency_failure",
    "deadline_compression",
    "scarce_resource_competition",
    "priority_disagreement",
    "role_ambiguity_or_overlap",
    "unequal_workload_allocation",
    "evaluation_or_promotion_salience",
    "information_delay_or_missing_handoff",
    "public_criticism_or_face_threat",
    "ignored_or_refused_request",
}


class AuthorityGrant(ValidatedModel):
    kind: AuthorityKind
    scope: NonEmptyText


class DiscPolicy(ValidatedModel):
    purpose: Literal["communication_tendency_only"]
    target_counts: dict[DiscStyle, int]
    prohibited_inferences: list[NonEmptyText]


class CompanyAgent(ValidatedModel):
    id: AgentId
    name: NonEmptyText
    department: NonEmptyText
    job_family: NonEmptyText
    role: NonEmptyText
    career_level: CareerLevel
    position: Position
    reports_to: AgentId | None
    authorities: list[AuthorityGrant]
    skills: list[NonEmptyText]
    tenure_band: NonEmptyText
    disc: DiscStyle
    hobbies: list[NonEmptyText]
    project_goal: NonEmptyText
    personal_work_priority: NonEmptyText
    communication_style: NonEmptyText
    pressure_response: NonEmptyText
    conflict_engagement_style: NonEmptyText
    main_dependencies: list[AgentId]
    initial_relationship_notes: NonEmptyText
    evidence_assumption_tags: list[NonEmptyText]


class PersonaDataset(ValidatedModel):
    schema_version: Literal[1]
    dataset_id: NonEmptyText
    synthetic: Literal[True]
    project: NonEmptyText
    disc_policy: DiscPolicy
    agents: list[CompanyAgent]


class OfficeTime(ValidatedModel):
    tick_minutes: int = Field(gt=0)
    normal_workday_ticks: int = Field(gt=0)
    standard_review_ticks: int = Field(gt=0)


class OfficePlace(ValidatedModel):
    id: NonEmptyText
    capacity: int = Field(gt=0)
    visibility: Literal["public", "team_visible", "attendee_only", "private", "nearby"]
    mechanisms: list[NonEmptyText]


class OfficeSpec(ValidatedModel):
    schema_version: Literal[1]
    id: NonEmptyText
    label: NonEmptyText
    reference_note: NonEmptyText
    time: OfficeTime
    places: list[OfficePlace]
    constraints: list[NonEmptyText]
    evidence_tags: list[NonEmptyText]


class OrganizationIdentity(ValidatedModel):
    name: NonEmptyText
    synthetic: Literal[True]
    reference_note: NonEmptyText


class ProjectDefinition(ValidatedModel):
    name: NonEmptyText
    structure: Literal["functional_matrix_lite"]
    product_type: Literal["connected_digital_product_service_feature"]
    manager_id: AgentId


class OrganizationRules(ValidatedModel):
    one_formal_manager_per_agent: Literal[True]
    career_level_grants_authority: Literal[False]
    peer_review_is_narrative_input: Literal[True]
    evaluation_authority: list[AgentId]


class RaciEntry(ValidatedModel):
    accountable: AgentId
    responsible: list[AgentId]
    consulted: list[AgentId] = Field(default_factory=list)
    informed: list[AgentId] = Field(default_factory=list)


class WorkflowTask(ValidatedModel):
    id: NonEmptyText
    name: NonEmptyText
    owner: AgentId
    contributors: list[AgentId]
    reviewers: list[AgentId]
    handoff_to: list[AgentId]
    predecessors: list[NonEmptyText]


class WorkflowSpec(ValidatedModel):
    task_states: list[NonEmptyText]
    tasks: list[WorkflowTask]


class ConflictEvent(ValidatedModel):
    id: NonEmptyText
    type: NonEmptyText
    theory_tags: list[NonEmptyText]
    observable_fact: NonEmptyText
    possible_interactions: list[NonEmptyText]


class EngineHandoff(ValidatedModel):
    current_config_compatible: bool
    reason: NonEmptyText
    required_capabilities: list[NonEmptyText]


class OrganizationSpec(ValidatedModel):
    schema_version: Literal[1]
    id: NonEmptyText
    organization: OrganizationIdentity
    project: ProjectDefinition
    departments: list[NonEmptyText]
    # How a department is named to the agents, when not by its id (the Korean preset); the id
    # stays the key the office map, projects and personas share.
    department_names: dict[NonEmptyText, NonEmptyText] = {}
    job_families: list[NonEmptyText]
    roles: list[NonEmptyText]
    career_levels: list[CareerLevel]
    positions: list[Position]
    authority_kinds: list[AuthorityKind]
    rules: OrganizationRules
    raci: dict[NonEmptyText, RaciEntry]
    workflow: WorkflowSpec
    conflict_events: list[ConflictEvent]
    engine_handoff: EngineHandoff
    evidence_tags: list[NonEmptyText]


class CompanyEnvironment(ValidatedModel):
    office: OfficeSpec
    org: OrganizationSpec


class RuntimeReadiness(ValidatedModel):
    executable_on_current_engine: bool
    validation_command: NonEmptyText
    smoke_test_scope: NonEmptyText


class CompanyPreset(ValidatedModel):
    preset_id: NonEmptyText
    baseline: Literal["A1B1C1"]
    personas: PersonaDataset
    environment: CompanyEnvironment
    runtime: RuntimeReadiness

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        agents = self.personas.agents
        org = self.environment.org
        ids = [agent.id for agent in agents]
        id_set = set(ids)

        if len(agents) != 20:
            raise ValueError("C-14 company preset must contain exactly 20 agents")
        if len(id_set) != len(ids):
            raise ValueError("Agent IDs must be unique")
        if len({agent.name.casefold() for agent in agents}) != len(agents):
            raise ValueError("Agent names must be unique (case insensitive)")
        if Counter(agent.disc for agent in agents) != Counter(
            self.personas.disc_policy.target_counts
        ):
            raise ValueError("Agent DISC counts must match disc_policy.target_counts")
        if self.personas.disc_policy.target_counts != {"D": 5, "i": 5, "S": 5, "C": 5}:
            raise ValueError("The locked C-14 baseline requires DISC D/i/S/C = 5/5/5/5")
        if self.personas.project != org.project.name:
            raise ValueError("Persona and organization project names must match")
        if "samsung" in org.organization.name.casefold():
            raise ValueError("The simulation organization must remain synthetic")

        roots = [agent.id for agent in agents if agent.reports_to is None]
        if roots != [org.project.manager_id]:
            raise ValueError("The project manager must be the sole reporting root")
        parents = {agent.id: agent.reports_to for agent in agents}
        for agent in agents:
            if agent.reports_to is not None and agent.reports_to not in id_set:
                raise ValueError(f"Unknown reports_to for {agent.id}: {agent.reports_to}")
            if agent.id in agent.main_dependencies:
                raise ValueError(f"Agent cannot depend on itself: {agent.id}")
            unknown = set(agent.main_dependencies) - id_set
            if unknown:
                raise ValueError(f"Unknown dependencies for {agent.id}: {sorted(unknown)}")
            if agent.department not in org.departments:
                raise ValueError(f"Unknown department for {agent.id}: {agent.department}")
            if agent.job_family not in org.job_families:
                raise ValueError(f"Unknown job family for {agent.id}: {agent.job_family}")
            if agent.role not in org.roles:
                raise ValueError(f"Unknown role for {agent.id}: {agent.role}")
            for grant in agent.authorities:
                if grant.kind not in org.authority_kinds:
                    raise ValueError(f"Unknown authority kind for {agent.id}: {grant.kind}")
        for start in id_set:
            seen = set()
            current = start
            while current is not None:
                if current in seen:
                    raise ValueError(f"Reporting cycle includes {current}")
                seen.add(current)
                current = parents[current]

        evaluators = {
            agent.id
            for agent in agents
            if any(grant.kind == "evaluate" for grant in agent.authorities)
        }
        if evaluators != set(org.rules.evaluation_authority):
            raise ValueError("Evaluate grants must match rules.evaluation_authority")

        referenced_agents = set()
        for entry in org.raci.values():
            references = {
                entry.accountable,
                *entry.responsible,
                *entry.consulted,
                *entry.informed,
            }
            unknown = references - id_set
            if unknown:
                raise ValueError(f"RACI contains unknown agents: {sorted(unknown)}")
            referenced_agents.update(references)
        if set(org.rules.evaluation_authority) - id_set:
            raise ValueError("Evaluation authority contains unknown agents")

        tasks = org.workflow.tasks
        if len(tasks) != 15:
            raise ValueError("C-14 requires exactly 15 workflow tasks")
        task_ids = [task.id for task in tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Task IDs must be unique")
        task_id_set = set(task_ids)
        participation = set(referenced_agents)
        for task in tasks:
            unknown_predecessors = set(task.predecessors) - task_id_set
            if unknown_predecessors:
                raise ValueError(
                    f"Task {task.id} has unknown predecessors: {sorted(unknown_predecessors)}"
                )
            references = {
                task.owner,
                *task.contributors,
                *task.reviewers,
                *task.handoff_to,
            }
            unknown_agents = references - id_set
            if unknown_agents:
                raise ValueError(
                    f"Task {task.id} contains unknown agents: {sorted(unknown_agents)}"
                )
            participation.update(references)
        pending = {task.id: set(task.predecessors) for task in tasks}
        completed = set()
        while pending:
            ready = {task_id for task_id, deps in pending.items() if deps <= completed}
            if not ready:
                raise ValueError("Task dependency graph must be acyclic")
            completed.update(ready)
            pending = {task_id: deps for task_id, deps in pending.items() if task_id not in ready}
        if participation != id_set:
            raise ValueError(
                f"Agents without meaningful work references: {sorted(id_set - participation)}"
            )

        event_ids = [event.id for event in org.conflict_events]
        event_types = {event.type for event in org.conflict_events}
        if len(event_ids) != 10 or len(set(event_ids)) != 10:
            raise ValueError("C-14 requires ten unique conflict event definitions")
        if event_types != EXPECTED_CONFLICT_EVENTS:
            raise ValueError("Conflict events do not match the locked C-14 taxonomy")
        if len({place.id for place in self.environment.office.places}) != len(
            self.environment.office.places
        ):
            raise ValueError("Office place IDs must be unique")
        return self


def load_company_preset(name: str = "large_korean_enterprise_20") -> CompanyPreset:
    """Hydra-compose one company preset and validate every cross-file reference."""
    with initialize_config_dir(version_base="1.3", config_dir=str(CONF_DIR)):
        raw = compose(config_name=f"company/{name}")
    return CompanyPreset.model_validate(
        OmegaConf.to_container(raw, resolve=True, throw_on_missing=True)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a composed C-14 company preset")
    parser.add_argument("preset", nargs="?", default="large_korean_enterprise_20")
    args = parser.parse_args()
    preset = load_company_preset(args.preset)
    print(
        f"Validated {preset.preset_id}: {len(preset.personas.agents)} agents, "
        f"{len(preset.environment.org.workflow.tasks)} tasks, "
        f"{len(preset.environment.org.conflict_events)} conflict events"
    )


if __name__ == "__main__":
    main()
