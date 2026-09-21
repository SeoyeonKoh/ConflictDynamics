"""Validated shapes: run configuration, LLM exchanges, and ordered reply trees.

Every model here is an immutable IO schema shared by `environment/`, `agent/` and the loop; mutable
runtime state (task progress, stress, relations) lives as a dataclass in the package that owns it.
Timestamps are simulation ticks, not wall-clock times; a tick is global and never resets at day end.
"""

from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonEmptyText = Annotated[str, StringConstraints(pattern=r"\S")]
Probability = Annotated[float, Field(ge=0, le=1)]
Valence = Annotated[float, Field(ge=-1, le=1)]
Importance = Annotated[float, Field(ge=1, le=10)]
Tick = Annotated[int, Field(ge=0)]

Expression = Literal[
    "neutral", "pleased", "amused", "surprised", "tired", "anxious", "annoyed", "angry"
]
# The face an agent shows others; an observer records the label's valence, never the emoji.
EXPRESSION_VALENCE: dict[Expression, float] = {
    "neutral": 0.0,
    "pleased": 0.5,
    "amused": 0.8,
    "surprised": 0.0,
    "tired": -0.3,
    "anxious": -0.5,
    "annoyed": -0.6,
    "angry": -0.9,
}

ActionKind = Literal[
    "move", "work", "rest", "eat", "talk", "message", "chat",
    "assign", "request", "approve", "reject", "report",
]  # fmt: skip
Authority = Literal["assign", "approve", "reject", "evaluate"]
SessionKind = Literal["talk", "message"]
Phase = Literal["arrival", "morning", "lunch", "afternoon", "closing", "overtime"]
PlaceKind = Literal["desk", "office", "meeting_room", "pantry", "cafeteria", "lobby"]
# Arguments each Action kind must carry; anything else the kind may leave unset.
ACTION_ARGUMENTS: dict[str, tuple[str, ...]] = {
    "move": ("place",),
    "work": ("task",),
    "talk": ("text",),
    "message": ("target", "text"),
    "chat": ("target",),
    "assign": ("task", "target"),
    "request": ("task",),
    "approve": ("task",),
    "reject": ("task",),
    "report": ("target", "text"),
}


class ValidatedModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class Utterance(ValidatedModel):
    id: NonEmptyText
    speaker: NonEmptyText
    text: NonEmptyText
    reply_to: str | None
    timestamp: Tick


class Decision(ValidatedModel):
    """One in-session judgement. The record axes ride along so no scoring call is needed."""

    urge: Probability
    reply_to: str | None
    reflection: NonEmptyText
    expression: Expression  # the face shown while judging; may differ from what is felt
    importance: Importance
    valence: Valence
    arousal: Probability


class Action(ValidatedModel):
    """What an agent does this tick. The LLM's output; `Environment.apply` judges validity."""

    kind: ActionKind
    target: NonEmptyText | None = None  # another agent
    place: NonEmptyText | None = None
    task: NonEmptyText | None = None
    text: NonEmptyText | None = None
    expression: Expression
    reflection: NonEmptyText
    importance: Importance
    valence: Valence
    arousal: Probability

    @model_validator(mode="after")
    def check_arguments(self) -> Self:
        missing = [n for n in ACTION_ARGUMENTS.get(self.kind, ()) if getattr(self, n) is None]
        if missing:
            raise ValueError(f"{self.kind} needs {', '.join(missing)}")
        return self


class PlanItem(ValidatedModel):
    """One block of a flat daily plan: what to do until which tick, executable without an LLM."""

    kind: ActionKind
    target: NonEmptyText | None = None
    place: NonEmptyText | None = None
    task: NonEmptyText | None = None
    until: Tick  # the block ends before this global tick
    text: NonEmptyText

    @model_validator(mode="after")
    def check_arguments(self) -> Self:
        needed = [n for n in ACTION_ARGUMENTS.get(self.kind, ()) if n != "text"]
        missing = [n for n in needed if getattr(self, n) is None]
        if missing:
            raise ValueError(f"{self.kind} needs {', '.join(missing)}")
        return self


class DayPlan(ValidatedModel):
    """The `plan_day` reply. Every LLM reply is an object: strict decoding needs a root object."""

    plan: list[PlanItem]


class AgentSpec(ValidatedModel):
    name: NonEmptyText
    persona: NonEmptyText
    stance: NonEmptyText | None = None  # Short observer label; never passed to the LLM.
    availability: Probability = 0.7
    # Company fields; wiki presets leave them unset. DISC is a style, never a rationality knob.
    disc: Literal["D", "I", "S", "C"] | None = None
    department: NonEmptyText | None = None
    title: NonEmptyText | None = None
    role: NonEmptyText | None = None
    reports_to: NonEmptyText | None = None
    skills: list[NonEmptyText] = []


class TaskSpec(ValidatedModel):
    """A task as the scenario states it. Progress and status live on `environment/org.py: Task`."""

    id: NonEmptyText
    description: NonEmptyText
    effort_ticks: int = Field(ge=1)
    due: Tick
    difficulty: int = Field(default=3, ge=1, le=5)
    owner: NonEmptyText | None = None
    depends_on: list[NonEmptyText] = []
    skills: list[NonEmptyText] = []


class PlaceSpec(ValidatedModel):
    id: NonEmptyText
    kind: PlaceKind
    capacity: int | None = Field(default=None, ge=1)  # None: unlimited


class OfficeConfig(ValidatedModel):
    places: list[PlaceSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique_ids(self) -> Self:
        if len({place.id for place in self.places}) != len(self.places):
            raise ValueError("Place ids must be unique")
        return self


class OrgConfig(ValidatedModel):
    departments: list[NonEmptyText] = Field(min_length=1)
    titles: dict[NonEmptyText, list[Authority]] = Field(min_length=1)
    tasks: list[TaskSpec] = []  # Static in A; a manager LLM generates them in C (plan §6 row 13).

    @model_validator(mode="after")
    def check_task_references(self) -> Self:
        ids = [task.id for task in self.tasks]
        if len(set(ids)) != len(ids):
            raise ValueError("Task ids must be unique")
        for task in self.tasks:
            for dependency in task.depends_on:
                if dependency not in ids or dependency == task.id:
                    raise ValueError(f"Task {task.id} depends on unknown task {dependency}")
        return self


class EnvironmentConfig(ValidatedModel):
    office: OfficeConfig
    org: OrgConfig


class MemoryConfig(ValidatedModel):
    """Retrieval and reflection parameters (plan §2-6). `alpha_mood` is the one free variable."""

    alpha_mood: Probability = 0
    top_k: int = Field(default=10, ge=0)
    recency_decay: Probability = 0.995
    reflect_threshold: float = Field(default=150, gt=0)
    relation_reflect_threshold: float = Field(default=-30, lt=0)
    reflect_window: int = Field(default=100, ge=1)
    reflect_questions: int = Field(default=3, ge=1)
    reflect_insights: int = Field(default=5, ge=1)
    observation_importance: Importance = 3


class Config(ValidatedModel):
    """The whole resolved run. Hydra composes it; Pydantic validates it."""

    rule: Literal["round_robin", "random", "bidding", "event_driven"] = "bidding"
    max_ticks: int = Field(default=12, ge=1)
    max_utterances: int | None = Field(default=None, ge=1)
    random_seed: int = 7
    n_agents: int = Field(default=4, ge=3)
    # None uses the seed shipped in conf/; a path is absolute or relative to the launch dir.
    seed_file: NonEmptyText | None = None
    agents: list[AgentSpec]
    backend: Literal["demo", "openai"] = "demo"
    live: bool = False
    model_decide: NonEmptyText | None = None
    model_speak: NonEmptyText | None = None
    model_embed: NonEmptyText | None = None  # only memory retrieval embeds; wiki runs never do
    embed_cache: NonEmptyText | None = (
        None  # sqlite path, relative to the launch dir; shared across runs
    )
    reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] | None = None
    max_tokens_decide: int = Field(default=512, ge=1)
    max_tokens_speak: int = Field(default=384, ge=1)
    max_total_tokens: int = Field(default=100_000, ge=1)
    max_input_chars: int = Field(default=64_000, ge=1)
    temperature: float = Field(default=0.8, ge=0, le=2)
    context_size: int = Field(default=10, ge=1)
    memory_mode: Literal["none", "summary", "full"] = "summary"
    persona_placement: Literal["payload", "system"] = "system"
    language: NonEmptyText = "English"

    # Company world (plan §1-1, §1-7, §2-6). None environment means a wiki run.
    environment: EnvironmentConfig | None = None
    resume: bool = False  # continue a paused run from its last checkpoint (same run dir)
    workers: int = Field(default=1, ge=1)  # threads for LLM judgements; applying stays sequential
    memory: MemoryConfig = MemoryConfig()
    max_days: int = Field(default=1, ge=1)
    ticks_per_day: int = Field(default=32, ge=1)
    turns_per_tick: dict[SessionKind, int] = {"talk": 12, "message": 12}
    w_valence: float = Field(default=0.2, ge=0)  # outcome → relation
    w_structural: float = Field(default=0.15, ge=0)  # a refusal or ignored request
    public_mult: float = Field(default=1.5, ge=1)  # face cost in front of others
    w_arousal: float = Field(default=0.1, ge=0)  # outcome → stress
    stress_decay: Probability = 0.02  # per tick
    mood_window: int = Field(default=8, ge=1)  # ticks
    blocked_nudge_ticks: int = Field(default=2, ge=1)  # demo rule: message the owner
    blocked_report_ticks: int = Field(default=4, ge=1)  # demo rule: report to the manager
    no_reply_ticks: int = Field(default=3, ge=1)

    @model_validator(mode="after")
    def check_relationships(self) -> Self:
        if self.n_agents != len(self.agents):
            raise ValueError("n_agents must match the number of configured agents")
        if len({agent.name.casefold() for agent in self.agents}) != self.n_agents:
            raise ValueError("Agent names must be unique (case insensitive)")
        if self.backend == "openai" and (self.model_decide is None or self.model_speak is None):
            raise ValueError("Set model_decide and model_speak before using the openai backend")
        if any(turns < 1 for turns in self.turns_per_tick.values()):
            raise ValueError("turns_per_tick values must be at least 1")
        if self.blocked_nudge_ticks > self.blocked_report_ticks:
            raise ValueError("blocked_nudge_ticks must not exceed blocked_report_ticks")
        self._check_org()
        return self

    def _check_org(self) -> None:
        names = {agent.name for agent in self.agents}
        org = self.environment.org if self.environment else None
        for agent in self.agents:
            if org is None:
                if agent.department or agent.title or agent.reports_to:
                    raise ValueError(f"{agent.name} has org fields but the run has no environment")
                continue
            if agent.department not in org.departments:
                raise ValueError(f"{agent.name}: unknown department {agent.department}")
            if agent.title not in org.titles:
                raise ValueError(f"{agent.name}: unknown title {agent.title}")
            if agent.reports_to is not None and (
                agent.reports_to not in names or agent.reports_to == agent.name
            ):
                raise ValueError(f"{agent.name} reports to unknown agent {agent.reports_to}")
        for task in org.tasks if org else []:
            if task.owner is not None and task.owner not in names:
                raise ValueError(f"Task {task.id} is owned by unknown agent {task.owner}")


class MemoryRecord(ValidatedModel):
    """One memory stream entry. Access times live in `MemoryStore.last_access`, not here."""

    id: NonEmptyText
    agent_id: NonEmptyText
    type: Literal["observation", "utterance", "action", "plan", "reflection"]
    description: NonEmptyText
    created_tick: Tick
    importance: Importance
    valence: Valence  # good or bad for me
    arousal: Probability  # how heated
    self_relevance: Probability  # my stake in it
    subjects: list[NonEmptyText] = []
    session_id: str | None = None
    evidence: list[NonEmptyText] = []  # record ids a reflection cites; the reflection tree


class Insight(ValidatedModel):
    """One reflection as the LLM returns it; stored as a `reflection` MemoryRecord."""

    text: NonEmptyText
    evidence: list[NonEmptyText] = []
    importance: Importance
    valence: Valence
    arousal: Probability
    subjects: list[NonEmptyText] = []


class Questions(ValidatedModel):
    """The first reflection reply: what to ask about recent memories."""

    questions: list[str]


class Insights(ValidatedModel):
    """The second reflection reply: the answers to one question."""

    insights: list[Insight]


class TaskView(ValidatedModel):
    id: NonEmptyText
    description: NonEmptyText
    owner: NonEmptyText | None
    progress: Probability
    due: Tick
    depends_on: list[NonEmptyText] = []


class BlockedTask(ValidatedModel):
    task: NonEmptyText  # mine
    waiting_on: NonEmptyText  # the unfinished prerequisite
    owner: NonEmptyText  # who owns the prerequisite
    since_tick: Tick
    due: Tick  # my deadline


class Message(ValidatedModel):
    sender: NonEmptyText
    text: NonEmptyText
    tick: Tick
    session_id: NonEmptyText


class Unanswered(ValidatedModel):
    to: NonEmptyText
    since_tick: Tick


class Rejected(ValidatedModel):
    action: Action
    reason: NonEmptyText


class View(ValidatedModel):
    """Everything one agent may see this tick; the loop assembles it, the agent only reads it."""

    agent: NonEmptyText
    day: Tick
    tick: Tick
    phase: Phase
    place: NonEmptyText
    places: dict[NonEmptyText, PlaceKind] = {}  # where I could move to
    present: dict[NonEmptyText, Expression] = {}  # co-present agents and their faces
    tasks: list[TaskView] = []
    blocked: list[BlockedTask] = []
    resources: dict[NonEmptyText, int] = {}  # free units per shared resource
    inbox: list[Message] = []
    unanswered: list[Unanswered] = []
    rejected: Rejected | None = None  # my previous tick's Action, if the environment refused it
    stress: Probability
    mood: Valence


class Received(ValidatedModel):
    speaker: NonEmptyText
    valence: Valence
    arousal: Probability


class Outcome(ValidatedModel):
    """Session facts about one agent. `Agent.apply_outcome` turns them into numbers."""

    session_id: NonEmptyText
    public: bool
    received: list[Received] = []  # utterances aimed at me
    refused: list[NonEmptyText] = []  # who refused my request
    ignored: list[NonEmptyText] = []  # who left my request unanswered
    rebutted: list[NonEmptyText] = []  # who contradicted me in front of others
    opposed: list[NonEmptyText] = []  # who sided against me


class Event(ValidatedModel):
    """One `events.jsonl` row. Decisions, actions, task changes, outcomes, shocks: all kinds."""

    tick: Tick
    day: Tick
    kind: Literal["decision", "action", "rejected", "task", "outcome", "session", "shock"]
    actor: NonEmptyText
    target: NonEmptyText | None = None
    location: NonEmptyText | None = None
    session: NonEmptyText | None = None
    payload: dict[str, Any] = {}


@dataclass
class Thread:
    utterances: list[Utterance] = field(default_factory=list)

    def __post_init__(self):
        # Rebuild through add() so every thread, however constructed, is validated.
        pending, self.utterances = self.utterances, []
        for utterance in pending:
            self.add(utterance)

    def get(self, utterance_id: str) -> Utterance:
        for utterance in self.utterances:
            if utterance.id == utterance_id:
                return utterance
        raise ValueError(f"Unknown utterance ID: {utterance_id}")

    def add(self, utterance: Utterance) -> None:
        if any(u.id == utterance.id for u in self.utterances):
            raise ValueError(f"Duplicate utterance ID: {utterance.id}")
        if self.utterances:
            if utterance.reply_to is None:
                raise ValueError("Only the first utterance may be a root")
            self.get(utterance.reply_to)
            if utterance.timestamp < self.utterances[-1].timestamp:
                raise ValueError("Utterances must be added in timestamp order")
        elif utterance.reply_to is not None:
            raise ValueError("The first utterance must be the root")
        self.utterances.append(utterance)

    def after(self, tick: int) -> list[Utterance]:
        return [u for u in self.utterances if u.timestamp > tick]
