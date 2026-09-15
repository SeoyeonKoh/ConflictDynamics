"""Validated shapes: run configuration, LLM exchanges, and ordered reply trees.

Timestamps are simulation ticks, not wall-clock times.
"""

from dataclasses import dataclass, field
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonEmptyText = Annotated[str, StringConstraints(pattern=r"\S")]
Probability = Annotated[float, Field(ge=0, le=1)]


class ValidatedModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class Utterance(ValidatedModel):
    id: NonEmptyText
    speaker: NonEmptyText
    text: NonEmptyText
    reply_to: str | None
    timestamp: int = Field(ge=0)


class Decision(ValidatedModel):
    urge: Probability
    reply_to: str | None
    reflection: NonEmptyText


class AgentSpec(ValidatedModel):
    name: NonEmptyText
    persona: NonEmptyText
    stance: NonEmptyText | None = None  # Short observer label; never passed to the LLM.
    availability: Probability = 0.7


class Config(ValidatedModel):
    """The whole resolved run. Hydra composes it; Pydantic validates it."""

    rule: Literal["round_robin", "random", "bidding", "event_driven"] = "bidding"
    max_ticks: int = Field(default=12, ge=1)
    max_utterances: int | None = Field(default=None, ge=1)
    silence_limit: int = Field(default=2, ge=1)
    random_seed: int = 7
    n_agents: int = Field(default=4, ge=3, le=6)
    # None uses the seed shipped in conf/; a path is absolute or relative to the launch dir.
    seed_file: NonEmptyText | None = None
    agents: list[AgentSpec]
    backend: Literal["demo", "openai"] = "demo"
    live: bool = False
    model_decide: NonEmptyText | None = None
    model_speak: NonEmptyText | None = None
    reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] | None = None
    max_tokens_decide: int = Field(default=512, ge=1)
    max_tokens_speak: int = Field(default=384, ge=1)
    max_total_tokens: int = Field(default=100_000, ge=1)
    max_input_chars: int = Field(default=64_000, ge=1)
    temperature: float = Field(default=0.8, ge=0, le=2)
    context_size: int = Field(default=10, ge=1)
    memory_mode: Literal["none", "summary", "full"] = "summary"
    persona_placement: Literal["payload", "system"] = "payload"
    language: NonEmptyText = "English"

    @model_validator(mode="after")
    def check_relationships(self) -> Self:
        if self.n_agents != len(self.agents):
            raise ValueError("n_agents must match the number of configured agents")
        if len({agent.name.casefold() for agent in self.agents}) != self.n_agents:
            raise ValueError("Agent names must be unique (case insensitive)")
        if self.backend == "openai" and (self.model_decide is None or self.model_speak is None):
            raise ValueError("Set model_decide and model_speak before using the openai backend")
        return self


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
