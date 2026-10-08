"""The tick loop (plan §1-17): phases, views, actions, sessions, embeddings, end-of-tick writes.

The loop is the only place that touches both `environment/` and `agent/`, the only thing that
creates or ends sessions, and the only writer of events and memory rows — it streams them to the
`TickWriter` once per tick and keeps nothing but the conversations themselves.
"""

import random
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from .agent import Agent
from .conversation import (
    HUMAN_MEETING,
    HUMAN_MESSAGE,
    HUMAN_PRIVATE,
    HUMAN_TALK,
    MEETING,
    MESSAGE,
    PRIVATE,
    TALK,
    Participant,
    Session,
)
from .environment import Environment
from .llm import LanguageModel
from .models import (
    LUNCH_TICKS,
    Action,
    Config,
    Event,
    MemoryRecord,
    Message,
    Outcome,
    Phase,
    Rejected,
    Thread,
    Unanswered,
    Utterance,
    View,
)
from .usage_audit import audit_context, traced

T = TypeVar("T")


DAY_START_MINUTES, TICK_MINUTES = 9 * 60, 15  # the office day: 09:00, in 15-minute ticks


def _clock(tick_of_day: int) -> str:
    minutes = DAY_START_MINUTES + TICK_MINUTES * tick_of_day
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def phase_of(tick: int, ticks_per_day: int, overtime_ticks: int = 0) -> Phase:
    day_span = ticks_per_day + overtime_ticks
    t = tick % day_span
    if t >= ticks_per_day:
        return "overtime"
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
    before_tick: Callable[[], None] | None = None
    on_tick: Callable | None = None  # (loop, events, retrievals), on the engine thread
    _events: list[Event] = field(default_factory=list, init=False)  # this tick's, until flushed
    _to_summarize: list[str] = field(default_factory=list, init=False)  # reached review/done
    meeting_notes: dict[str, list[str]] = field(default_factory=dict, init=False)  # last meeting
    scheduled_end: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        self.by_name = {agent.name: agent for agent in self.agents}
        self.env.org.evaluation_season = self.cfg.scenario.evaluation_season
        self.env.org.promotion_slots = self.cfg.scenario.promotion_slots
        # Judgements are independent per agent and run in parallel; applying them is sequential,
        # in config order, so a run is reproducible whatever the thread timing (plan §1-10).
        self.pool = ThreadPoolExecutor(self.cfg.workers) if self.cfg.workers > 1 else None

    def _judge(self, jobs: list[Callable[[], T]]) -> list[T]:
        if self.pool is None:
            return [job() for job in jobs]
        return [
            future.result()
            for future in [self.pool.submit(copy_context().run, job) for job in jobs]
        ]

    def agent(self, name: str) -> Agent:
        return self.by_name[name]

    # --- driving ---

    @property
    def last_tick(self) -> int:
        return self.cfg.max_days * self.day_span - 1

    @property
    def day_span(self) -> int:
        return self.cfg.ticks_per_day + self.cfg.overtime_ticks_per_day

    def _phase(self, tick: int) -> Phase:
        return phase_of(tick, self.cfg.ticks_per_day, self.cfg.overtime_ticks_per_day)

    def run(self) -> LoopResult:
        self.run_until(self.last_tick)
        return LoopResult(days=self.cfg.max_days, ticks=self.last_tick + 1)

    def run_until(self, last_tick: int) -> None:
        while self.tick_now <= last_tick:
            if self.before_tick is not None:
                self.before_tick()
            self.tick(self.tick_now)
            self.tick_now += 1

    @traced(None)
    def tick(self, tick: int) -> None:
        day, phase = tick // self.day_span, self._phase(tick)
        if tick > 0 and phase != self._phase(tick - 1):
            self._close_all(tick, f"phase:{phase}")
        for name, messages in self.outbox.items():  # last tick's messages are readable now
            self.inbox.setdefault(name, []).extend(messages)
        self.outbox = {}
        self._apply_schedule(tick, day)
        for task_id, change in self.env.advance(tick):
            self._log(tick, "task", actor=task_id, payload={"change": change})
            self._notice(task_id, change, tick)
        self._record_ignored(tick)
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
        # The rest of the day is re-planned after lunch and when someone's work changed.
        replans = [(a, r) for a in free if (r := a.replan_reason(views[a.name], tick))]
        plans = self._judge(
            [lambda a=a, r=r: a.plan_day(views[a.name], tick, r) for a, r in replans]
        )
        for (agent, reason), items in zip(replans, plans):
            plan = {"kind": "plan", "reason": reason, "items": [i.text for i in items]}
            self._log(tick, "action", actor=agent.name, payload=plan)
        for agent in self.agents:
            agent.perceive(views[agent.name], tick)
        # Everyone's first action uses the same tick-start view. A refused action gets up to two
        # replacements against the updated view; an agent in a session waits, with its inbox kept.
        actions = self._judge([lambda a=a: a.act(views[a.name], tick) for a in free])
        for agent, action in zip(free, actions):
            if agent.name in self.busy:
                continue  # pulled into a session opened earlier this tick; one session per agent
            self.inbox[agent.name] = []
            self.rejected.pop(agent.name, None)
            refused = self._apply(agent, action, tick, day)
            for _ in range(2):
                if refused is None:
                    break
                retry_view = self._view(agent, tick, day, phase, with_inbox=False)
                with audit_context(action_retry=True, rejection_attempt=_ + 1):
                    action = agent.act(retry_view, tick)
                self.rejected.pop(agent.name, None)
                refused = self._apply(agent, action, tick, day)
        self._summarize(tick)
        for sid in list(self.live):
            self._step(sid, tick)
        day_end = (tick + 1) % self.day_span == 0
        if day_end:
            self._close_all(tick, "day_end")
            self.env.office.leave()
        season = self.env.org.evaluation_season
        self._judge(
            [lambda a=a: a.end_tick(tick, views[a.name], phase, season) for a in self.agents]
        )
        if phase == "overtime":
            for agent in self.agents:
                workload = sum(
                    task.remaining_ticks
                    for task in views[agent.name].tasks
                    if task.status != "done"
                )
                if workload:
                    self._log(
                        tick,
                        "overtime",
                        actor=agent.name,
                        payload={
                            "workload": workload,
                            "overtime_ticks": agent.state.overtime_ticks,
                        },
                    )
        if day_end:  # leaving work: each looks back on the day (one call each, in parallel)
            self._judge([lambda a=a: a.end_day(tick, views[a.name]) for a in self.agents])
        self._embed()  # after reflections, so every record is written with its vector
        events = list(self._events)
        retrievals = self._flush()
        if day_end:
            self.writer.write_checkpoint(day, self.checkpoint())
        if self.on_tick is not None:
            self.on_tick(self, events, retrievals)

    # --- checkpoints ---

    def viewer_snapshot(self) -> dict:
        """Detached viewer input, assembled on the engine thread at a tick boundary."""
        bubbles = {}  # `session` is membership in a live session; a bubble may outlive one
        lines = []  # every utterance this tick, thread by thread in the order they ran
        for sid, thread in self.threads.items():
            said = [u for u in thread.utterances if u.timestamp == self.tick_now]
            lines += [{"speaker": u.speaker, "text": u.text, "session": sid} for u in said]
            for u in said:
                bubbles[u.speaker] = {"bubble": u.text}
        return {
            "lines": lines,
            "tick": self.tick_now,
            "day": self.tick_now // self.day_span,
            "phase": self._phase(self.tick_now),
            "agents": [
                {
                    "id": a.name,
                    "dept": a.spec.department,
                    "place": self.env.office.location[a.name],
                    "state": a.state.snapshot(),
                    "reflection": a.memory.reflections(5),
                    "session": self.busy.get(a.name),
                    **bubbles.get(a.name, {}),
                }
                for a in self.agents
            ],
            "sessions": [
                {
                    "id": sid,
                    "kind": s.kind,
                    "place": self.sessions[sid]["place"],
                    "participants": [p.agent.name for p in s.participants],
                }
                for sid, s in self.live.items()
            ],
            "tasks": [
                {
                    "id": t.id,
                    "title": t.spec.description,
                    "owner": t.owner,
                    "progress": t.progress,
                    "due": t.due,
                    "status": t.status,
                    "blocked_by": [d.id for d in self.env.org.unfinished_prerequisites(t)],
                    "group": t.spec.group,
                    "depends_on": list(t.spec.depends_on),
                    "cross": t.spec.cross,
                    "lifecycle": t.lifecycle,
                    "deliverable": t.spec.deliverable,  # the document's expected form, if any
                    "criteria": t.spec.criteria,
                    "record": self.env.org.record(t),  # the evidence, for the viewer's Tasks tab
                }
                for t in self.env.org.tasks.values()
            ],
            "resources": [
                {
                    "id": p.id,
                    "holders": self.env.office.occupants(p.id),
                    "capacity": self.env.office.capacity[p.id],
                }
                for p in self.cfg.environment.office.places
                if p.capacity is not None
            ],
        }

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
            "scheduled_end": dict(self.scheduled_end),
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
        self.scheduled_end = dict(data.get("scheduled_end", {}))

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
            help_wanted=list(env.help_wanted),
            workable=list(env.workable),
            task_board=list(env.task_board),
            # Only someone with work to hand out gets the transcript (it is long).
            last_meeting=(
                self.meeting_notes.get(agent.name, [])
                if any(t.role == "assigner" for t in env.tasks)
                else []
            ),
            resources=env.resources,
            inbox=list(self.inbox.get(agent.name, [])) if with_inbox else [],
            unanswered=unanswered,
            rejected=self.rejected.get(agent.name),
            clock=_clock(tick % self.day_span),
            stress=agent.state.stress,
            mood=agent.state.mood,
        )

    def _apply(self, agent: Agent, action: Action, tick: int, day: int) -> Rejected | None:
        name = agent.name
        self._log(tick, "action", actor=name, target=action.target, payload=action.model_dump())
        refused_agent = None
        if action.kind == "reject" and action.task in self.env.org.tasks:
            task = self.env.org.tasks[action.task]
            refused_agent = task.request or (task.owner if task.lifecycle == "review" else None)
        refused = self.env.apply(name, action, tick, agent.work_rate())
        if refused is None and action.kind in ("talk", "chat"):
            refused = self._open_session(agent, action, tick, day)
        if refused is not None:
            self.rejected[name] = refused
            self._log(tick, "rejected", actor=name, payload={"reason": refused.reason})
            return refused
        if action.kind in ("message", "gossip", "report"):
            self._send(agent, action, tick, day)
        for task_id, change in self.env.org.drain_changes():
            self._log(tick, "task", actor=task_id, payload={"change": change})
            self._notice(task_id, change, tick)
            if change in ("review", "done"):
                self._to_summarize.append(task_id)
        if action.kind == "evaluate":
            self._log(
                tick,
                "evaluation",
                actor=name,
                target=action.target,
                payload={"rating": action.rating, "note": action.text},
            )
            self.agent(action.target).receive_evaluation(name, action.rating, action.text, tick)
        if refused_agent is not None and refused_agent != name:
            outcome = Outcome(
                session_id=f"action:{tick}:{name}",
                public=False,
                refused=[name],
            )
            for row in self.agent(refused_agent).apply_outcome(outcome, tick):
                self._log(
                    tick,
                    "outcome",
                    actor=refused_agent,
                    target=row["b"],
                    session=outcome.session_id,
                    payload=row | {"refused": True},
                )
        return None

    def _notice(self, task_id: str, change: str, tick: int) -> None:
        """A finished task's team lets those working on the tasks after it know."""
        if change not in ("done", "approved"):
            return
        for task in self.env.org.tasks.values():
            if task_id in task.spec.depends_on:
                for name in task.workers:
                    self.agent(name).notice_done(task.id, task_id, tick)

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

    def _record_ignored(self, tick: int) -> None:
        """Turn an expired unanswered request into an observable structural outcome once."""
        for (sender, target), since in sorted(self.outstanding.items()):
            if tick - since != self.cfg.no_reply_ticks:
                continue
            outcome = Outcome(
                session_id=f"ignored:{sender}:{target}:{since}",
                public=False,
                ignored=[target],
            )
            for row in self.agent(sender).apply_outcome(outcome, tick):
                self._log(
                    tick,
                    "outcome",
                    actor=sender,
                    target=target,
                    session=outcome.session_id,
                    payload=row | {"ignored": True},
                )

    def _apply_schedule(self, tick: int, day: int) -> None:
        """Apply deterministic scenario shocks, interventions, and meeting starts."""
        within_day = tick % self.day_span
        scenario = self.cfg.scenario
        for shock in scenario.shocks:
            if (shock.day, shock.tick) != (day, within_day):
                continue
            changed = self.env.apply_shock(
                shock.kind,
                tick=tick,
                task=shock.task,
                resource=shock.resource,
                amount=shock.amount,
                until_tick=shock.until_tick,
            )
            if shock.kind == "evaluation_announcement":
                self.env.org.promotion_slots = scenario.promotion_slots
            self._log(
                tick,
                "shock",
                actor=shock.agent or "scenario",
                target=shock.task or shock.resource,
                payload={
                    "id": shock.id,
                    "event_id": shock.event_id,
                    "kind": shock.kind,
                    "changed_state": changed,
                },
            )
        for intervention in scenario.interventions:
            if (intervention.day, intervention.tick) != (day, within_day):
                continue
            changed = self._apply_intervention(intervention, tick)
            self._log(
                tick,
                "intervention",
                actor=intervention.actor,
                target=intervention.target or intervention.task,
                payload={"id": intervention.id, "kind": intervention.kind} | changed,
            )
        for meeting in scenario.meetings:
            if (meeting.day, meeting.tick) == (day, within_day):
                self._open_scheduled_meeting(meeting, tick)

    def _apply_intervention(self, intervention, tick: int) -> dict:
        if intervention.kind == "workload_redistribution":
            task = self.env.org.tasks[intervention.task]
            before = task.owner
            task.owner = intervention.target
            task.lifecycle = "ready"
            return {"task": task.id, "owner_before": before, "owner_after": task.owner}
        if intervention.kind == "deadline_adjustment":
            task = self.env.org.tasks[intervention.task]
            before = task.due
            task.due += intervention.amount
            return {"task": task.id, "due_before": before, "due_after": task.due}
        if intervention.kind == "resource_adjustment":
            before = self.env.office.capacity[intervention.target]
            self.env.office.adjust_capacity(intervention.target, intervention.amount)
            return {
                "resource": intervention.target,
                "capacity_before": before,
                "capacity_after": self.env.office.capacity[intervention.target],
            }
        if intervention.kind == "private_mediation":
            if intervention.target is None:
                raise ValueError(f"Intervention {intervention.id} needs a mediation target")
            self._open_private_intervention(
                intervention.id, intervention.actor, intervention.target, tick
            )
            return {"private_session": True, "mediator": intervention.actor}
        return {"clarification": True, "tick": tick}

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
        provenance = "hearsay" if action.kind == "gossip" else "direct"
        self.outbox.setdefault(target, []).append(
            Message(
                sender=name,
                text=action.text,
                tick=tick,
                session_id=sid,
                provenance=provenance,
                subject=action.subject,
            )
        )
        self.outstanding[(name, target)] = tick
        self.outstanding.pop((target, name), None)
        self._record_post(agent, action, sid, tick)

    # --- sessions ---

    def _open_private_intervention(
        self, intervention_id: str, actor: str, target: str, tick: int
    ) -> None:
        names = [actor, target]
        if any(name in self.busy for name in names):
            return
        place = "focus_room" if "focus_room" in self.env.office.places else None
        if place is not None:
            free = self.env.office.free(place)
            if free is not None and free < 2:
                return
            for name in names:
                self.env.office.location[name] = place
        sid = f"private:{intervention_id}:{tick}"
        root = Utterance(
            id=sid,
            speaker=actor,
            text="Clarify the work issue privately and agree on the next observable action.",
            reply_to=None,
            timestamp=tick,
        )
        self.threads[sid] = Thread([root])
        self.sessions[sid] = _meta(sid, "private", names, place, tick, public=False)
        self._start(
            sid,
            "private",
            names,
            place,
            tick,
            public=False,
            keep_open=True,
            rule="turn_taking",
            turns=1,
        )
        self.live[sid].participants[0].last_seen = 1
        self.scheduled_end[sid] = tick

    def _summarize(self, tick: int) -> None:
        """Owners write the summary of work that reached review or done this tick, in parallel;
        it goes on the task's record, where reviewers and dependants read it."""
        tasks = [self.env.org.tasks[t] for t in dict.fromkeys(self._to_summarize)]
        self._to_summarize = []
        # Whoever did most of the work writes it (p0_kickoff: an owner who never touched T02
        # wrote that it was still blocked).
        writers = [max(t.worked_by, key=t.worked_by.get) if t.worked_by else t.owner for t in tasks]
        jobs = [(t, w) for t, w in zip(tasks, writers) if w is not None]
        written = self._judge(
            [
                lambda t=t, w=w: self.agent(w).summarize(self.env.task_view(w, t.id), tick)
                for t, w in jobs
            ]
        )
        for (task, writer), (summary, document) in zip(jobs, written):
            task.summary = summary
            payload = {"change": "summary", "summary": summary}
            if document is not None:  # a deliverable: the document goes on file with it
                task.document = document
                payload["document"] = document
            self._log(tick, "task", actor=task.id, target=writer, payload=payload)

    def _open_scheduled_meeting(self, meeting, tick: int) -> None:
        names = [meeting.organizer, *[n for n in meeting.participants if n != meeting.organizer]]
        if meeting.rule == "everyone":
            names = [name for name in names if name not in self.busy]
        if len(names) < 2 or any(name in self.busy for name in names):
            self._log(
                tick,
                "rejected",
                actor=meeting.organizer,
                payload={"reason": f"meeting {meeting.id} has a busy participant"},
            )
            return
        free = self.env.office.free(meeting.place)
        outsiders = [name for name in names if self.env.office.location[name] != meeting.place]
        if free is not None and free < len(outsiders):
            self._log(
                tick,
                "rejected",
                actor=meeting.organizer,
                payload={"reason": f"meeting place {meeting.place} is full"},
            )
            return
        for name in names:
            self.env.office.location[name] = meeting.place
        kind = "meeting" if meeting.public else "private"
        sid = f"{kind}:{meeting.id}:{meeting.day}"
        root = Utterance(
            id=sid,
            speaker=meeting.organizer,
            text=meeting.agenda,
            reply_to=None,
            timestamp=tick,
        )
        self.threads[sid] = Thread([root])
        self.sessions[sid] = _meta(sid, kind, names, meeting.place, tick, public=meeting.public) | {
            "agenda": meeting.agenda,
            "scheduled_end": tick + meeting.duration_ticks - 1,
        }
        self._start(
            sid,
            kind,
            names,
            meeting.place,
            tick,
            public=meeting.public,
            keep_open=True,
            rule=meeting.rule,
            # `everyone` fits every participant's turn into the meeting's duration.
            turns=-(-len(names) // meeting.duration_ticks) if meeting.rule == "everyone" else 1,
        )
        self.live[sid].participants[0].last_seen = 1
        self.scheduled_end[sid] = tick + meeting.duration_ticks - 1

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
        # A talk is with the people it names (the environment has checked they are here); those
        # already in a session are left out, and with nobody free there is no talk to open.
        free = [other for other in action.targets if other not in self.busy]
        if not free:
            busy = ", ".join(action.targets)
            return Rejected(
                action=action,
                reason=f"{busy} {'is' if len(action.targets) == 1 else 'are'} in a session",
            )
        place = self.env.env_view(name).place
        sid = f"talk:{tick}:{name}"
        root = Utterance(id=sid, speaker=name, text=action.text, reply_to=None, timestamp=tick)
        self.threads[sid] = Thread([root])
        self.sessions[sid] = _meta(sid, "talk", [name, *free], place, tick, public=True)
        self._start(sid, "talk", [name, *free], place, tick)
        self.live[sid].participants[0].last_seen = 1  # the opener wrote the root
        self._record_post(agent, action, sid, tick)
        return None

    def _start(
        self,
        sid: str,
        kind: str,
        names: list[str],
        place: str | None,
        tick: int,
        *,
        public: bool | None = None,
        keep_open: bool = False,
        rule: str | None = None,
        turns: int | None = None,
    ) -> None:
        instructions = (
            {"talk": TALK, "message": MESSAGE, "meeting": MEETING, "private": PRIVATE}
            if self.cfg.prompt_style == "engine"
            else {
                "talk": HUMAN_TALK,
                "message": HUMAN_MESSAGE,
                "meeting": HUMAN_MEETING,
                "private": HUMAN_PRIVATE,
            }  # fmt: skip
        )[kind]
        self.live[sid] = Session(
            id=sid,
            kind=kind,
            participants=[Participant(self.agent(n)) for n in names],
            thread=self.threads[sid],
            rng=self.rng,
            instructions=instructions,
            rule=rule or ("event_driven" if kind == "talk" else "bidding"),
            turns_per_tick=turns or self.cfg.turns_per_tick.get(kind, 1),
            pool=self.pool,
            keep_open=keep_open,
            public_override=public,
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
        if sid in self.scheduled_end and tick >= self.scheduled_end[sid]:
            session.finish("scheduled_end")
        if session.finished is not None:
            self._close(sid, tick)

    def _close_all(self, tick: int, reason: str) -> None:
        for sid in list(self.live):
            self.live[sid].finish(reason)
            self._close(sid, tick)

    def _close(self, sid: str, tick: int) -> None:
        session = self.live.pop(sid)
        self.scheduled_end.pop(sid, None)
        outcomes = session.outcomes()
        if self.cfg.relation_appraisal == "llm":  # each looks back on the others, in parallel
            thread, names = session.thread, list(outcomes)
            judged = self._judge(
                [lambda n=n: self.agent(n).appraise(thread, outcomes[n], tick) for n in names]
            )
            outcomes = dict(zip(names, judged))
        for name, outcome in outcomes.items():
            self.busy.pop(name, None)
            for row in self.agent(name).apply_outcome(outcome, tick):
                self._log(tick, "outcome", actor=name, target=row["b"], session=sid, payload=row)
        if session.kind == "meeting":  # what was said, for whoever acts on it (an assigner)
            notes = [f"{u.speaker}: {u.text[:400]}" for u in session.thread.utterances]
            for participant in session.participants:
                self.meeting_notes[participant.agent.name] = notes
        if session.kind != "message":
            self.sessions[sid]["end"] = tick  # a DM thread stays open for async messages
        payload = {"kind": session.kind, "end": session.finished}
        opener = session.participants[0].agent.name
        self._log(tick, "session", actor=opener, session=sid, payload=payload)

    # --- end of tick ---

    @traced("memory_write_embedding")
    def _embed(self) -> None:
        """One embed call per tick for every agent's new records."""
        pending = [
            (agent, id_, text)
            for agent in self.agents
            for id_, text in agent.memory.pending_texts()
        ]
        if not pending:
            return
        with audit_context(
            agent=None,
            agents=sorted({a.name for a, _, _ in pending}),
            texts_by_agent=dict(Counter(a.name for a, _, _ in pending)),
        ):
            vectors = self.llm.embed([text for _, _, text in pending])
        for (agent, id_, _), vector in zip(pending, vectors):
            agent.memory.set_embeddings({id_: vector})

    def _flush(self) -> list[dict]:
        memory_rows, retrieval_rows = [], []
        for agent in self.agents:
            rows, log = agent.memory.drain()
            memory_rows += rows
            retrieval_rows += [{"agent_id": agent.name} | row for row in log]
        self.writer.write_tick(self._events, memory_rows, retrieval_rows)
        self._events = []
        return retrieval_rows

    def _log(self, tick: int, kind: str, *, actor: str, **fields) -> None:
        day = tick // self.day_span
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
