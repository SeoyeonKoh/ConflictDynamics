"""The tick loop (plan §1-17): phases, views, actions, sessions, embeddings, end-of-tick writes.

The loop is the only place that touches both `environment/` and `agent/`, the only thing that
creates or ends sessions, and the only writer of events and memory rows.
"""

import random
from dataclasses import dataclass, field
from typing import Protocol

from .agent import Agent
from .conversation import MESSAGE, TALK, Participant, Session
from .environment import Environment
from .llm import LanguageModel
from .models import (
    Action,
    Config,
    Event,
    MemoryRecord,
    Message,
    Phase,
    Rejected,
    Thread,
    Unanswered,
    Utterance,
    View,
)

LUNCH_TICKS = 4  # one hour


def phase_of(tick: int, ticks_per_day: int) -> Phase:
    t = tick % ticks_per_day
    half = ticks_per_day // 2
    if t == 0:
        return "arrival"
    if t < half:
        return "morning"
    if t < half + LUNCH_TICKS:
        return "lunch"
    if t < ticks_per_day - 1:
        return "afternoon"
    return "closing"


class TickWriter(Protocol):
    def write_tick(
        self,
        events: list[Event],
        memory_rows: list[tuple[MemoryRecord, list[float] | None]],
        retrieval_rows: list[dict],
    ) -> None: ...


@dataclass
class LoopResult:
    days: int
    ticks: int
    stop_reason: str = "max_days"


@dataclass
class Loop:
    cfg: Config
    agents: list[Agent]
    env: Environment
    llm: LanguageModel
    rng: random.Random
    writer: TickWriter | None = None
    events: list[Event] = field(default_factory=list)
    threads: dict[str, Thread] = field(default_factory=dict)  # every conversation, by id
    sessions: dict[str, dict] = field(default_factory=dict)  # conversation meta, by id
    live: dict[str, Session] = field(default_factory=dict)
    busy: dict[str, str] = field(default_factory=dict)  # agent → live session id
    inbox: dict[str, list[Message]] = field(default_factory=dict)
    outstanding: dict[tuple[str, str], int] = field(default_factory=dict)  # (from, to) → tick
    rejected: dict[str, Rejected] = field(default_factory=dict)
    last_views: dict[str, View] = field(default_factory=dict)
    tick_now: int = 0
    _tick_events: list[Event] = field(default_factory=list, init=False)

    def __post_init__(self):
        self.by_name = {agent.name: agent for agent in self.agents}

    def agent(self, name: str) -> Agent:
        return self.by_name[name]

    # --- driving ---

    def run(self) -> LoopResult:
        total = self.cfg.max_days * self.cfg.ticks_per_day
        self.run_until(total - 1)
        return LoopResult(days=self.cfg.max_days, ticks=total)

    def run_until(self, last_tick: int) -> None:
        while self.tick_now <= last_tick:
            self.tick(self.tick_now)
            self.tick_now += 1

    def tick(self, tick: int) -> None:
        day, phase = divmod(tick, self.cfg.ticks_per_day)[0], phase_of(tick, self.cfg.ticks_per_day)
        if tick > 0 and phase != phase_of(tick - 1, self.cfg.ticks_per_day):
            for sid in list(self.live):
                self.live[sid].finish(f"phase:{phase}")
                self._close(sid, tick)
        for task_id, change in self.env.advance(tick):
            self._log(tick, "task", actor=task_id, payload={"change": change})
        if phase == "arrival":
            for agent in self.agents:
                view = self._view(agent, tick, day, phase)
                items = agent.plan_day(view, tick)
                self._log(
                    tick, "action", actor=agent.name, payload={"plan": [i.text for i in items]}
                )
        for agent in self.agents:
            view = self._view(agent, tick, day, phase)
            self.last_views[agent.name] = view
            agent.perceive(view, tick)
            if agent.name in self.busy:
                continue
            self.inbox[agent.name] = []
            self.rejected.pop(agent.name, None)
            action = agent.act(view, tick)
            self._apply(agent, action, tick, day)
        for sid in list(self.live):
            self._step(sid, tick)
        for agent in self.agents:
            agent.end_tick(tick)
        self._embed()  # after reflections, so every record is written with its vector
        self._flush()

    # --- views and actions ---

    def _view(self, agent: Agent, tick: int, day: int, phase: Phase) -> View:
        env = self.env.env_view(agent.name)
        unanswered = [
            Unanswered(to=to, since_tick=since)
            for (sender, to), since in self.outstanding.items()
            if sender == agent.name and tick - since >= self.cfg.no_reply_ticks
        ]
        return View(
            agent=agent.name,
            day=day,
            tick=tick,
            phase=phase,
            place=env.place,
            places=env.places,
            present={other: self.agent(other).state.expression for other in env.present},
            tasks=list(env.tasks),
            blocked=list(env.blocked),
            resources=env.resources,
            inbox=list(self.inbox.get(agent.name, [])),
            unanswered=unanswered,
            rejected=self.rejected.get(agent.name),
            stress=agent.state.stress,
            mood=agent.state.mood,
        )

    def _apply(self, agent: Agent, action: Action, tick: int, day: int) -> None:
        name = agent.name
        self._log(tick, "action", actor=name, target=action.target, payload=action.model_dump())
        refused = self.env.apply(name, action, tick)
        if refused is None and action.kind in ("talk", "chat"):
            refused = self._open_session(agent, action, tick, day)
        if refused is not None:
            self.rejected[name] = refused
            self._log(tick, "rejected", actor=name, payload={"reason": refused.reason})
            return
        if action.kind in ("message", "report"):
            self._send(agent, action, tick, day)

    def _record_post(self, agent: Agent, action: Action, sid: str, tick: int) -> None:
        agent.observe(
            f"I said to {action.target or 'the room'}: {action.text}",
            tick=tick,
            importance=action.importance,
            valence=action.valence,
            arousal=action.arousal,
            subjects=[action.target] if action.target else [],
            session_id=sid,
        )

    # --- messages ---

    def _dm_id(self, a: str, b: str, day: int) -> str:
        first, second = sorted((a, b))
        return f"dm:{first}:{second}:{day}"

    def _send(self, agent: Agent, action: Action, tick: int, day: int) -> None:
        """Append one message to the pair's thread for the day; it is read next tick."""
        name, target = agent.name, action.target
        sid = self._dm_id(name, target, day)
        thread = self.threads.get(sid)
        if thread is None:
            thread = self.threads[sid] = Thread()
            self.sessions[sid] = _meta(sid, "message", [name, target], None, tick, public=False)
        # ConvoKit wants the root utterance to carry the conversation's own id.
        thread.add(
            Utterance(
                id=sid if not thread.utterances else f"{sid}:{len(thread.utterances)}",
                speaker=name,
                text=action.text,
                reply_to=None if not thread.utterances else thread.utterances[-1].id,
                timestamp=tick,
            )
        )
        self.inbox.setdefault(target, []).append(
            Message(sender=name, text=action.text, tick=tick, session_id=sid)
        )
        self.outstanding[(name, target)] = tick
        self.outstanding.pop((target, name), None)
        self._record_post(agent, action, sid, tick)

    # --- sessions ---

    def _open_session(self, agent: Agent, action: Action, tick: int, day: int) -> Rejected | None:
        name = agent.name
        if action.kind == "chat":
            target = action.target
            sid = self._dm_id(name, target, day)
            if target in self.busy or sid not in self.threads:
                why = "is in a session" if target in self.busy else "has no thread with you today"
                return Rejected(action=action, reason=f"{target} {why}")
            self._start(sid, "message", [name, target], None, tick, action=None)
            return None
        present = [o for o in self.env.env_view(name).present if o not in self.busy]
        if not present:
            return Rejected(action=action, reason="everyone here is in a session")
        place = self.env.env_view(name).place
        sid = f"talk:{tick}:{name}"
        root = Utterance(id=sid, speaker=name, text=action.text, reply_to=None, timestamp=tick)
        self.threads[sid] = Thread([root])
        self.sessions[sid] = _meta(sid, "talk", [name, *present], place, tick, public=True)
        self._start(sid, "talk", [name, *present], place, tick, action=action)
        self._record_post(agent, action, sid, tick)
        return None

    def _start(
        self, sid: str, kind: str, names: list[str], place: str | None, tick: int, action
    ) -> None:
        participants = [Participant(self.agent(n)) for n in names]
        if action is not None:
            participants[0].last_seen = 1  # the opener wrote the root
        self.live[sid] = Session(
            id=sid,
            kind=kind,
            participants=participants,
            thread=self.threads[sid],
            rng=self.rng,
            instructions=TALK if kind == "talk" else MESSAGE,
            rule="event_driven" if kind == "talk" else "bidding",
            turns_per_tick=self.cfg.turns_per_tick[kind],
            silence_limit=self.cfg.silence_limit,
        )
        for name in names:
            self.busy[name] = sid
        self._log(tick, "session", actor=names[0], session=sid, location=place,
                  payload={"kind": kind, "participants": names, "start": True})  # fmt: skip

    def _step(self, sid: str, tick: int) -> None:
        session = self.live[sid]
        before = len(session.thread.utterances)
        events = session.step(tick)
        for event in events:
            self._log(tick, "decision", actor=event["agent"], session=sid, payload=event)
        posted = {e.get("utterance_id"): e for e in events if e.get("posted")}
        for utterance in session.thread.utterances[before:]:
            for participant in session.participants:
                agent = participant.agent
                if utterance.speaker == agent.name:
                    event = posted[utterance.id]
                    agent.observe(
                        f"I said: {utterance.text}",
                        tick=tick,
                        importance=event["importance"],
                        valence=event["valence"],
                        arousal=event["arousal"],
                        session_id=sid,
                    )
                else:
                    mine = [e for e in events if e["agent"] == agent.name and "valence" in e]
                    agent.observe(
                        f"{utterance.speaker} said: {utterance.text}",
                        tick=tick,
                        valence=mine[-1]["valence"] if mine else 0,
                        subjects=[utterance.speaker],
                        session_id=sid,
                    )
        if session.finished is not None:
            self._close(sid, tick)

    def _close(self, sid: str, tick: int) -> None:
        session = self.live.pop(sid)
        for name, outcome in session.outcomes().items():
            self.busy.pop(name, None)
            for row in self.agent(name).apply_outcome(outcome, tick):
                self._log(tick, "outcome", actor=name, target=row["b"], session=sid, payload=row)
        self.sessions[sid]["end"] = tick
        self._log(tick, "session", actor=session.participants[0].agent.name, session=sid,
                  payload={"kind": session.kind, "end": session.finished})  # fmt: skip

    # --- end of tick ---

    def _embed(self) -> None:
        """One embed call per tick for every agent's new records."""
        pending = [
            (agent, id_, text)
            for agent in self.agents
            for id_, text in agent.memory.pending_texts()
        ]
        if not pending:
            return
        vectors = self.llm.embed([text for _, _, text in pending])
        for (agent, id_, _), vector in zip(pending, vectors):
            agent.memory.set_embeddings({id_: vector})

    def _flush(self) -> None:
        memory_rows, retrieval_rows = [], []
        for agent in self.agents:
            rows, log = agent.memory.drain()
            memory_rows += rows
            retrieval_rows += [{"agent_id": agent.name} | row for row in log]
        if self.writer is not None:
            self.writer.write_tick(self._tick_events, memory_rows, retrieval_rows)
        self._tick_events = []

    def _log(self, tick: int, kind: str, *, actor: str, **fields) -> None:
        event = Event(
            tick=tick, day=tick // self.cfg.ticks_per_day, kind=kind, actor=actor, **fields
        )
        self.events.append(event)
        self._tick_events.append(event)


def _meta(
    sid: str, kind: str, names: list[str], place: str | None, tick: int, *, public: bool
) -> dict:
    return {"id": sid, "kind": kind, "participants": names, "place": place, "start": tick,
            "end": None, "public": public}  # fmt: skip
