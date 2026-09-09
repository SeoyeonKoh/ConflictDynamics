"""Small, ordered reply trees. Timestamps are simulation ticks."""

import json
from dataclasses import dataclass, field
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

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


@dataclass
class Thread:
    utterances: list[Utterance] = field(default_factory=list)

    def __post_init__(self):
        initial = self.utterances
        self.utterances = []
        for utterance in initial:
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

    def context(self, n: int = 10) -> str:
        return json.dumps([u.model_dump() for u in self.utterances[-n:]], ensure_ascii=False)
