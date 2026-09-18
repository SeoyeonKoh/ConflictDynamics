"""The tick loop (plan §1-17): phases, views, actions, sessions, embeddings, end-of-tick writes.

The loop is the only place that touches both `environment/` and `agent/`, the only thing that
creates or ends sessions, and the only writer of events and memory rows — it streams them to the
`TickWriter` once per tick and keeps nothing but the conversations themselves.
"""

import random
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

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
T = TypeVar("T")


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

    def write_checkpoint(self, day: int, data: dict) -> None: ...


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
    writer: TickWriter
    threads: dict[str, Thread] = field(default_factory=dict)  # every conversation, by id
    sessions: dict[str, dict] = field(default_factory=dict)  # conversation meta, by id
    live: dict[str, Session] = field(default_factory=dict)
    busy: dict[str, str] = field(default_factory=dict)  # agent → live session id
    inbox: dict[str, list[Message]] = field(default_factory=dict)  # readable this tick
    outbox: dict[str, list[Message]] = field(default_factory=dict)  # sent this tick
    outstanding: dict[tuple[str, str], int] = field(default_factory=dict)  # (from, to) → tick
    rejected: dict[str, Rejected] = field(default_factory=dict)
    tick_now: int = 0
    _events: list[Event] = field(default_factory=list, init=False)  # this tick's, until flushed

    def __post_init__(self):
        self.by_name = {agent.name: agent for agent in self.agents}
        # Judgements are independent per agent and run in parallel; applying them is sequential,
        # in config order, so a run is reproducible whatever the thread timing (plan §1-10).
        self.pool = ThreadPoolExecutor(self.cfg.workers) if self.cfg.workers > 1 else None

    def _judge(self, jobs: list[Callable[[], T]]) -> list[T]:
        if self.pool is None:
            return [job() for job in jobs]
        return [future.result() for future in [self.pool.submit(job) for job in jobs]]

    def agent(self, name: str) -> Agent:
        return self.by_name[name]

    # --- driving ---

    @property
    def last_tick(self) -> int:
        return self.cfg.max_days * self.cfg.ticks_per_day - 1

    def run(self) -> LoopResult:
        self.run_until(self.last_tick)
        return LoopResult(days=self.cfg.max_days, ticks=self.last_tick + 1)

    def run_until(self, last_tick: int) -> None:
        while self.tick_now <= last_tick:
            self.tick(self.tick_now)
            self.tick_now += 1

    def tick(self, tick: int) -> None:
        day, phase = tick // self.cfg.ticks_per_day, phase_of(tick, self.cfg.ticks_per_day)
        if tick > 0 and phase != phase_of(tick - 1, self.cfg.ticks_per_day):
            self._close_all(tick, f"phase:{phase}")
        for name, messages in self.outbox.items():  # last tick's messages are readable now
            self.inbox.setdefault(name, []).extend(messages)
        self.outbox = {}
        for task_id, change in self.env.advance(tick):
            self._log(tick, "task", actor=task_id, payload={"change": change})
        if phase == "arrival":
            self.outstanding = {}  # a new day; yesterday's silences are not today's
            views = [self._view(agent, tick, day, phase) for agent in self.agents]
            plans = self._judge(
                [lambda a=a, v=v: a.plan_day(v, tick) for a, v in zip(self.agents, views)]
            )
            for agent, items in zip(self.agents, plans):
                plan = {"kind": "plan", "items": [i.text for i in items]}
                self._log(tick, "action", actor=agent.name, payload=plan)
        free = [agent for agent in self.agents if agent.name not in self.busy]
        views = {a.name: self._view(a, tick, day, phase, with_inbox=a in free) for a in self.agents}
        for agent in self.agents:
            agent.perceive(views[agent.name], tick)
        # Everyone free judges the same tick-start view; an agent in a session waits, its messages
        # stay in the inbox until the session ends.
        actions = self._judge([lambda a=a: a.act(views[a.name], tick) for a in free])
        for agent, action in zip(free, actions):
            if agent.name in self.busy:
                continue  # pulled into a session opened earlier this tick; one session per agent
            self.inbox[agent.name] = []
            self.rejected.pop(agent.name, None)
            self._apply(agent, action, tick, day)
        for sid in list(self.live):
            self._step(sid, tick)
        day_end = (tick + 1) % self.cfg.ticks_per_day == 0
        if day_end:
            self._close_all(tick, "day_end")
        self._judge([lambda a=a: a.end_tick(tick) for a in self.agents])
        self._embed()  # after reflections, so every record is written with its vector
        self._flush()
        if day_end:
            self.writer.write_checkpoint(day, self.checkpoint())

    # --- checkpoints ---

    def checkpoint(self) -> dict:
        """Everything needed to continue from the next tick; taken at a day end, so no session is
        live. Memory records and vectors are already in `memory.sqlite`."""
        return {
            "tick": self.tick_now + 1,
            "rng": _rng_state(self.rng),
            "env": self.env.snapshot(),
            "agents": {agent.name: agent.snapshot() for agent in self.agents},
            "threads": {
                sid: [u.model_dump() for u in t.utterances] for sid, t in self.threads.items()
            },
            "sessions": self.sessions,
            "live": {},
            "busy": {},
            "inbox": {n: [m.model_dump() for m in ms] for n, ms in self.inbox.items()},
            "outbox": {n: [m.model_dump() for m in ms] for n, ms in self.outbox.items()},
            "outstanding": [[a, b, t] for (a, b), t in self.outstanding.items()],
            "rejected": {n: r.model_dump() for n, r in self.rejected.items()},
        }

    def restore(self, data: dict, memory: dict[str, tuple[list[MemoryRecord], dict]]) -> None:
        """Continue from a checkpoint; `memory` is `storage.read_memory`'s per-agent records."""
        self.tick_now = data["tick"]
        self.rng.setstate(_rng_state_from(data["rng"]))
        self.env.restore(data["env"])
        for agent in self.agents:
            records, vectors = memory.get(agent.name, ([], {}))
            agent.restore(data["agents"][agent.name], records, vectors)
        self.threads = {
            sid: Thread([Utterance.model_validate(u) for u in rows])
            for sid, rows in data["threads"].items()
        }
        self.sessions = data["sessions"]
        self.inbox = {n: [Message.model_validate(m) for m in ms] for n, ms in data["inbox"].items()}
        self.outbox = {
            n: [Message.model_validate(m) for m in ms] for n, ms in data["outbox"].items()
        }
        self.outstanding = {(a, b): t for a, b, t in data["outstanding"]}
        self.rejected = {n: Rejected.model_validate(r) for n, r in data["rejected"].items()}

    def close(self) -> None:
        """Stop the judgement threads; in-flight jobs are abandoned, queued ones cancelled."""
        if self.pool is not None:
            self.pool.shutdown(wait=False, cancel_futures=True)

    # --- views and actions ---

    def _view(
        self, agent: Agent, tick: int, day: int, phase: Phase, with_inbox: bool = True
    ) -> View:
        env = self.env.env_view(agent.name)
        # Shown once, the tick the silence reaches `no_reply_ticks`, like the demo's blocked rule.
        unanswered = [
            Unanswered(to=to, since_tick=since)
            for (sender, to), since in self.outstanding.items()
            if sender == agent.name and tick - since == self.cfg.no_reply_ticks
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
            inbox=list(self.inbox.get(agent.name, [])) if with_inbox else [],
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
        """Append one message to the pair's thread for the day; the receiver reads it next tick."""
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
        self.outbox.setdefault(target, []).append(
            Message(sender=name, text=action.text, tick=tick, session_id=sid)
        )
        self.outstanding[(name, target)] = tick
        self.outstanding.pop((target, name), None)
        self._record_post(agent, action, sid, tick)

    # --- sessions ---

    def _open_session(self, agent: Agent, action: Action, tick: int, day: int) -> Rejected | None:
        name = agent.name
        if action.kind == "chat":
            # Plan §1-7 would answer a busy partner asynchronously; a `chat` carries no text, so
            # the loop refuses it and the agent can `message` next tick instead.
            target = action.target
            sid = self._dm_id(name, target, day)
            if target in self.busy or sid not in self.threads:
                why = "is in a session" if target in self.busy else "has no thread with you today"
                return Rejected(action=action, reason=f"{target} {why}")
            self._start(sid, "message", [name, target], None, tick)
            return None
        here = self.env.env_view(name)
        present = [o for o in here.present if o not in self.busy]
        if not present:
            return Rejected(action=action, reason="everyone here is in a session")
        sid = f"talk:{tick}:{name}"
        root = Utterance(id=sid, speaker=name, text=action.text, reply_to=None, timestamp=tick)
        self.threads[sid] = Thread([root])
        self.sessions[sid] = _meta(sid, "talk", [name, *present], here.place, tick, public=True)
        self._start(sid, "talk", [name, *present], here.place, tick)
        self.live[sid].participants[0].last_seen = 1  # the opener wrote the root
        self._record_post(agent, action, sid, tick)
        return None

    def _start(self, sid: str, kind: str, names: list[str], place: str | None, tick: int) -> None:
        self.live[sid] = Session(
            id=sid,
            kind=kind,
            participants=[Participant(self.agent(n)) for n in names],
            thread=self.threads[sid],
            rng=self.rng,
            instructions=TALK if kind == "talk" else MESSAGE,
            rule="event_driven" if kind == "talk" else "bidding",
            turns_per_tick=self.cfg.turns_per_tick[kind],
            silence_limit=self.cfg.silence_limit,
            pool=self.pool,
        )
        for name in names:
            self.busy[name] = sid
        payload = {"kind": kind, "participants": names, "start": True}
        self._log(tick, "session", actor=names[0], session=sid, location=place, payload=payload)

    def _step(self, sid: str, tick: int) -> None:
        session = self.live[sid]
        before = len(session.thread.utterances)
        events = session.step(tick)
        for event in events:
            self._log(tick, "decision", actor=event["agent"], session=sid, payload=event)
        posted_at = {e["utterance_id"]: i for i, e in enumerate(events) if e.get("posted")}
        for utterance in session.thread.utterances[before:]:
            at = posted_at[utterance.id]
            for participant in session.participants:
                agent = participant.agent
                if utterance.speaker == agent.name:
                    event = events[at]
                    agent.observe(
                        f"I said: {utterance.text}",
                        tick=tick,
                        importance=event["importance"],
                        valence=event["valence"],
                        arousal=event["arousal"],
                        session_id=sid,
                    )
                else:
                    # The listener's own appraisal: the first judgement it made after hearing it.
                    later = (e for e in events[at + 1 :] if e["agent"] == agent.name)
                    verdict = next((e for e in later if "valence" in e), None)
                    agent.observe(
                        f"{utterance.speaker} said: {utterance.text}",
                        tick=tick,
                        valence=verdict["valence"] if verdict else 0,
                        subjects=[utterance.speaker],
                        session_id=sid,
                    )
        if session.finished is not None:
            self._close(sid, tick)

    def _close_all(self, tick: int, reason: str) -> None:
        for sid in list(self.live):
            self.live[sid].finish(reason)
            self._close(sid, tick)

    def _close(self, sid: str, tick: int) -> None:
        session = self.live.pop(sid)
        for name, outcome in session.outcomes().items():
            self.busy.pop(name, None)
            for row in self.agent(name).apply_outcome(outcome, tick):
                self._log(tick, "outcome", actor=name, target=row["b"], session=sid, payload=row)
        if session.kind == "talk":
            self.sessions[sid]["end"] = tick  # a DM thread stays open for async messages
        payload = {"kind": session.kind, "end": session.finished}
        opener = session.participants[0].agent.name
        self._log(tick, "session", actor=opener, session=sid, payload=payload)

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
        self.writer.write_tick(self._events, memory_rows, retrieval_rows)
        self._events = []

    def _log(self, tick: int, kind: str, *, actor: str, **fields) -> None:
        day = tick // self.cfg.ticks_per_day
        self._events.append(Event(tick=tick, day=day, kind=kind, actor=actor, **fields))


def _meta(
    sid: str, kind: str, names: list[str], place: str | None, tick: int, *, public: bool
) -> dict:
    return {"id": sid, "kind": kind, "participants": names, "place": place, "start": tick,
            "end": None, "public": public}  # fmt: skip


def _rng_state(rng: random.Random) -> list:
    version, internal, gauss = rng.getstate()
    return [version, list(internal), gauss]


def _rng_state_from(state: list) -> tuple:
    version, internal, gauss = state
    return version, tuple(internal), gauss
