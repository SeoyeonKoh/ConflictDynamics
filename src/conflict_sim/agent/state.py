"""Mutable internal state: stress, mood, the face shown, and one Relationship per other agent.

The numeric rules of plan §1-7 live here; sessions only report facts (`Outcome`) and the loop
calls `end_tick`. Nothing outside `agent/` writes these fields.
"""

from dataclasses import asdict, dataclass, field
from statistics import fmean

from ..models import Config, Expression, Outcome


@dataclass
class Relationship:
    relation: float = 0.0  # -1..1, directed: how I see them
    grievances: list[str] = field(default_factory=list)  # unresolved, as memory record ids
    summary: str | None = None  # LLM text, written only by a relation reflection
    last_interaction_tick: int | None = None


@dataclass
class AgentState:
    stress: float = 0.0  # 0..1
    mood: float = 0.0  # -1..1
    expression: Expression = "neutral"
    relations: dict[str, Relationship] = field(default_factory=dict)

    def relation(self, other: str) -> Relationship:
        return self.relations.setdefault(other, Relationship())

    def apply_outcome(self, outcome: Outcome, cfg: Config, tick: int) -> dict[str, float]:
        """Fold one session's facts into relations and stress; returns the relation delta per other.

        relation(me→b) += (w_valence · mean valence(b→me) − w_structural · [b refused/ignored me])
        × public_mult in front of others; stress += w_arousal · Σ arousal + w_structural · [refused]
        """
        received: dict[str, list[float]] = {}
        arousal = 0.0
        for row in outcome.received:
            received.setdefault(row.speaker, []).append(row.valence)
            arousal += row.arousal
        costly = set(outcome.refused) | set(outcome.ignored)
        mult = cfg.public_mult if outcome.public else 1.0
        deltas = {}
        others = received.keys() | costly | set(outcome.rebutted) | set(outcome.opposed)
        for other in sorted(others):  # a fixed order keeps the outcome events reproducible
            delta = cfg.w_valence * fmean(received[other]) if other in received else 0.0
            if other in costly:
                delta -= cfg.w_structural
            delta *= mult
            link = self.relation(other)
            link.relation = _clamp(link.relation + delta, -1, 1)
            link.last_interaction_tick = tick
            deltas[other] = delta
        self.stress = _clamp(
            self.stress + cfg.w_arousal * arousal + cfg.w_structural * len(outcome.refused), 0, 1
        )
        return deltas

    def end_tick(self, recent_valences: list[float], cfg: Config) -> None:
        """Recover a little stress; mood is the mean valence of the last `mood_window` ticks."""
        self.stress = _clamp(self.stress - cfg.stress_decay, 0, 1)
        self.mood = fmean(recent_valences) if recent_valences else 0.0

    def snapshot(self) -> dict:
        return {
            "stress": self.stress,
            "mood": self.mood,
            "expression": self.expression,
            "relations": {other: asdict(r) for other, r in self.relations.items()},
        }

    def restore(self, data: dict) -> None:
        self.stress, self.mood, self.expression = data["stress"], data["mood"], data["expression"]
        self.relations = {other: Relationship(**r) for other, r in data["relations"].items()}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
