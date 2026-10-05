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
    familiarity: float = 0.2
    task_trust: float = 0.5
    grievances: list[str] = field(default_factory=list)  # unresolved, as memory record ids
    summary: str | None = None  # LLM text, written only by a relation reflection
    last_interaction_tick: int | None = None


@dataclass
class AgentState:
    stress: float = 0.0  # 0..1
    mood: float = 0.0  # -1..1
    expression: Expression = "neutral"
    relations: dict[str, Relationship] = field(default_factory=dict)
    workload: int = 0
    overtime_ticks: int = 0

    def relation(self, other: str) -> Relationship:
        return self.relations.setdefault(other, Relationship())

    def apply_outcome(self, outcome: Outcome, cfg: Config, tick: int) -> dict[str, float]:
        """Fold one session's facts into relations and stress; returns the relation delta per other.

        relation(me→b) += (w_valence · mean valence(b→me) − w_structural · [b refused/ignored me])
        × public_mult in front of others; stress rises by w_arousal · Σ arousal + w_structural ·
        [refused], saturating (see `_press`)
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
        self._press(cfg.w_arousal * arousal + cfg.w_structural * len(outcome.refused))
        return deltas

    def apply_evaluation(self, rating: float, cfg: Config) -> None:
        """A rating of my work presses once, by p_evaluated · (1 − rating)."""
        self._press(cfg.p_evaluated * (1 - rating))

    def stress_band(self) -> str | None:
        """How much stress shows when I talk: None while it does not (the expression bands' cut)."""
        if self.stress >= 0.7:
            return "high"
        return "medium" if self.stress >= 0.4 else None

    def work_rate(self, cfg: Config) -> float:
        """The share of a tick's effort my work does: stress slows it, never stops it."""
        return 1 - cfg.stress_work_penalty * self.stress

    def end_tick(
        self,
        recent_valences: list[float],
        cfg: Config,
        *,
        pressure: float = 0,
        workload: int = 0,
        overtime: bool = False,
        on_break: bool = False,
        evaluation_season: bool = False,
    ) -> None:
        """Apply observable work and evaluation pressure, otherwise recover, then update mood.

        The pressure coefficients come from the locked company-world plan. Overtime is recorded
        even when its intentionally undecided coefficient is left as ``None``.
        """
        self.workload = workload
        if evaluation_season:
            pressure += cfg.p_evaluation_season
        if overtime:
            self.overtime_ticks += 1
            if cfg.p_overtime is not None:
                pressure += cfg.p_overtime
        if pressure > 0:  # many late tasks at once press no harder than p_max
            self._press(min(pressure, cfg.p_max))
        else:
            self.stress = _clamp(self.stress - cfg.stress_decay, 0, 1)
        if on_break:  # a rest in the pantry, cafeteria or lobby recovers on top of the decay
            self.stress = _clamp(self.stress - cfg.break_recovery, 0, 1)
        self.mood = fmean(recent_valences) if recent_valences else 0.0

    def _press(self, amount: float) -> None:
        """Raise stress by `amount` scaled by the headroom left, so it nears 1 but never bursts."""
        self.stress = _clamp(self.stress + amount * (1 - self.stress), 0, 1)

    def snapshot(self) -> dict:
        relations = {}
        for other, relation in self.relations.items():
            row = asdict(relation)
            if relation.familiarity == 0.2:
                row.pop("familiarity")
            if relation.task_trust == 0.5:
                row.pop("task_trust")
            relations[other] = row
        result = {
            "stress": self.stress,
            "mood": self.mood,
            "expression": self.expression,
            "relations": relations,
        }
        if self.workload:
            result["workload"] = self.workload
        if self.overtime_ticks:
            result["overtime_ticks"] = self.overtime_ticks
        return result

    def restore(self, data: dict) -> None:
        self.stress, self.mood, self.expression = data["stress"], data["mood"], data["expression"]
        self.workload = data.get("workload", 0)
        self.overtime_ticks = data.get("overtime_ticks", 0)
        self.relations = {other: Relationship(**r) for other, r in data["relations"].items()}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
