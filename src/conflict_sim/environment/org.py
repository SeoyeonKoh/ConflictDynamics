"""Organisation state: scoped authority, task lifecycle, workload, and evaluation facts."""

from dataclasses import dataclass, field

from ..models import AgentSpec, Authority, OrgConfig, TaskSpec

MAX_RETURNS = 2  # after this many rejections a task can only be approved (p0_kickoff: 14 in a row)


@dataclass
class Task:
    """Mutable state for one task in the deterministic dependency graph."""

    spec: TaskSpec
    owner: str | None
    due: int
    worked: int = 0
    done_tick: int | None = None
    blocked_since: int | None = None
    overdue: bool = False
    request: str | None = None
    lifecycle: str = "ready"
    forced_block_until: int | None = None
    review_round: int = 0
    helpers: list[str] = field(default_factory=list)  # joined with `help`; they work it too
    assigned: list[str] = field(default_factory=list)  # team members an `assign` added
    help_wanted: bool = False  # its owner or a contributor asked for helpers
    # The completion record, the evidence agents can cite (C-16: finished work was questioned
    # hundreds of times because nothing showed who did it, who signed it off, or what it delivered).
    worked_by: dict[str, int] = field(default_factory=dict)  # ticks of work per person
    started_tick: int | None = None
    review_tick: int | None = None
    approved_by: str | None = None
    approval_note: str | None = None
    rejections: list[dict] = field(default_factory=list)  # {"by", "tick", "note"}
    summary: str | None = None  # the owner's account of what was delivered
    document: str | None = None  # the deliverable, for a task that produces one

    @property
    def id(self) -> str:
        return self.spec.id

    @property
    def workers(self) -> list[str]:
        team = (self.owner, *self.spec.contributors, *self.assigned, *self.helpers)
        return [name for name in team if name]

    @property
    def progress(self) -> float:
        return min(self.worked / self.spec.effort_ticks, 1.0)

    @property
    def remaining(self) -> int:
        return max(self.spec.effort_ticks - self.worked, 0)

    @property
    def done(self) -> bool:
        return self.done_tick is not None

    @property
    def status(self) -> str:
        if self.done:
            return "done"
        if self.overdue:
            return "overdue"
        if self.blocked_since is not None:
            return "blocked"
        if self.owner is None:
            return "unassigned"
        return self.lifecycle

    STATE = (
        "owner",
        "due",
        "worked",
        "done_tick",
        "blocked_since",
        "overdue",
        "request",
        "lifecycle",
        "forced_block_until",
        "review_round",
        "helpers",
        "assigned",
        "help_wanted",
        "worked_by",
        "started_tick",
        "review_tick",
        "approved_by",
        "approval_note",
        "rejections",
        "summary",
        "document",
    )

    def snapshot(self) -> dict:
        fields = {name: getattr(self, name) for name in self.STATE} | {
            "helpers": list(self.helpers),
            "assigned": list(self.assigned),
            "worked_by": dict(self.worked_by),
            "rejections": list(self.rejections),
        }
        return fields | {"progress": self.progress, "status": self.status}

    def legacy_snapshot(self) -> dict:
        """Stable reader view retained for the original six-agent demo."""
        status = self.status
        if status in {"ready", "in_progress", "review", "unassigned"}:
            status = "open"
        return {
            "owner": self.owner,
            "due": self.due,
            "worked": self.worked,
            "done_tick": self.done_tick,
            "blocked_since": self.blocked_since,
            "overdue": self.overdue,
            "request": self.request,
            "progress": self.progress,
            "status": status,
        }

    def restore(self, data: dict) -> None:
        for name in self.STATE:
            if name in data:
                setattr(self, name, data[name])


@dataclass(frozen=True)
class Evaluation:
    evaluator: str
    target: str
    rating: float
    note: str
    tick: int


class Org:
    def __init__(self, config: OrgConfig, agents: list[AgentSpec]):
        self.titles = config.titles
        self.agents = {agent.name: agent for agent in agents}
        self.title = {agent.name: agent.title for agent in agents}
        self.manager = {agent.name: agent.reports_to for agent in agents}
        self.tasks = {task.id: Task(task, task.owner, task.due) for task in config.tasks}
        self.max_workers = config.max_task_workers
        self.show_unowned = config.show_unowned
        self.evaluation_season = False
        self.promotion_slots = 0
        self.evaluations: list[Evaluation] = []
        self._changes: list[tuple[str, str]] = []

    def can(self, name: str, authority: Authority, scope: str | None = None) -> bool:
        grants = self.agents[name].authorities
        if grants:
            for grant in grants:
                if grant.kind != authority:
                    continue
                if scope is None or grant.scope in {scope, "cross_function", "all_agents"}:
                    return True
            return False
        return authority in self.titles.get(self.title[name] or "", [])

    def owned(self, name: str) -> list[Task]:
        return [task for task in self.tasks.values() if task.owner == name]

    def participating(self, name: str) -> list[tuple[Task, str]]:
        rows: list[tuple[Task, str]] = []
        for task in self.tasks.values():
            if task.spec.group is not None and task.done:
                continue  # a finished project step only crowds the view; the board counts it
            if task.owner == name:
                rows.append((task, "owner"))
            elif name in task.spec.contributors or name in task.assigned:
                rows.append((task, "contributor"))
            elif name in task.helpers:
                rows.append((task, "helper"))
            elif name in task.spec.reviewers:
                rows.append((task, "reviewer"))
            elif name in task.spec.handoff_to:
                rows.append((task, "handoff"))
            elif task.lifecycle == "review" and name in self.signers(task):
                rows.append((task, "reviewer"))  # waiting for my sign-off though I am not listed
            elif (
                self.show_unowned
                and task.owner is None
                and self.can(name, "assign", task.spec.authority_scope)
            ):
                rows.append((task, "assigner"))  # nobody owns it yet and I may hand it out
        return rows

    def signers(self, task: Task) -> set[str]:
        """Who may approve or reject a task in review: holders of its approval scope who did not
        work on it. If nobody else holds it, or the work was already returned MAX_RETURNS times,
        the owner's manager signs too (p0_kickoff: an owner-approver rejected its own work 14x)."""
        workers = set(task.workers) | set(task.worked_by)
        holders = {n for n in self.agents if self.can(n, "approve", task.spec.authority_scope)}
        signers = holders - workers
        if not holders:  # a scope nobody holds (a department project): its named reviewers sign
            signers = {name for name in task.spec.reviewers if name not in workers}
        lead = task.owner or next(iter(task.worked_by), None)
        manager = self.manager.get(lead) if lead else None
        if manager is not None and manager not in workers:
            if not signers or len(task.rejections) >= MAX_RETURNS:
                signers.add(manager)
        if not signers and lead is not None:
            signers.add(lead)  # nobody beside or above (the top manager's own release tasks)
        return signers

    def free_slots(self, task: Task) -> int:
        return max(self.max_workers - len(task.workers), 0)

    def unfinished_prerequisites(self, task: Task, tick: int | None = None) -> list[Task]:
        waiting = [self.tasks[dep] for dep in task.spec.depends_on if not self.tasks[dep].done]
        if (
            tick is not None
            and task.forced_block_until is not None
            and tick < task.forced_block_until
        ):
            waiting.append(task)
        return waiting

    def advance(self, tick: int) -> list[tuple[str, str]]:
        """Judge deadlines and dependencies once per tick."""
        changes = self.drain_changes()
        for task in self.tasks.values():
            if task.done:
                continue
            blocked = bool(self.unfinished_prerequisites(task, tick))
            if blocked and task.blocked_since is None:
                task.blocked_since = tick
                changes.append((task.id, "blocked"))
            elif not blocked and task.blocked_since is not None:
                task.blocked_since = None
                change = "ready" if task.lifecycle == "ready" else "unblocked"
                changes.append((task.id, change))
            if tick > task.due and not task.overdue:
                task.overdue = True
                changes.append((task.id, "overdue"))
        return changes

    def work(self, task: Task, tick: int, actor: str | None = None) -> None:
        if task.lifecycle == "ready":
            task.lifecycle = "in_progress"
            self._changes.append((task.id, "in_progress"))
        if task.started_tick is None:
            task.started_tick = tick
        if actor is not None:
            task.worked_by[actor] = task.worked_by.get(actor, 0) + 1
        task.worked += 1
        if task.worked < task.spec.effort_ticks:
            return
        if task.spec.reviewers and task.spec.authority_scope is not None:
            task.lifecycle = "review"
            task.review_round += 1
            task.review_tick = tick
            self._changes.append((task.id, "review"))
        else:
            task.done_tick = tick
            task.lifecycle = "done"
            self._changes.append((task.id, "done"))

    def approve(self, task: Task, tick: int, actor: str | None = None, note: str | None = None):
        task.approved_by, task.approval_note = actor, note
        task.done_tick = tick
        task.lifecycle = "done"
        task.overdue = False
        self._changes.append((task.id, "approved"))

    def reject(self, task: Task, actor: str | None = None, note: str | None = None, tick=None):
        task.rejections.append({"by": actor, "tick": tick, "note": note})
        task.lifecycle = "in_progress"
        task.worked = max(task.spec.effort_ticks - 1, 0)
        self._changes.append((task.id, "revision"))

    def record(self, task: Task) -> dict:
        """What is on file for a finished task: facts the engine saw, plus the owner's summary
        and the approver's note."""
        prerequisites = [self.tasks[d] for d in task.spec.depends_on]
        return {
            "owner": task.owner,
            "team": task.workers,
            "worked_by": dict(task.worked_by),
            "started_tick": task.started_tick,
            "review_tick": task.review_tick,
            "done_tick": task.done_tick,
            "due": task.due,
            "on_time": task.done_tick is not None and task.done_tick <= task.due,
            "approved_by": task.approved_by,
            "approval_note": task.approval_note,
            "rejections": list(task.rejections),
            "summary": task.summary,
            "document": task.document,
            "prerequisites": [
                {"id": p.id, "done_tick": p.done_tick, "approved_by": p.approved_by}
                for p in prerequisites
            ],
            "handoff_to": list(task.spec.handoff_to),
        }

    def board(self) -> list[str]:
        """One line per finished task, for everyone: the company's record of what is done. A
        department project is one line of progress (its step lines would bury the rest)."""
        lines, groups = [], {}
        for task in self.tasks.values():
            if task.spec.group is not None:
                done, total = groups.get(task.spec.group, (0, 0))
                groups[task.spec.group] = (done + task.done, total + 1)
                continue
            if not task.done:
                continue
            signed = f", approved by {task.approved_by}" if task.approved_by else ""
            late = "" if task.done_tick <= task.due else ", late"
            lines.append(
                f"{task.id} {task.spec.description}: done at t{task.done_tick} (due t{task.due}"
                f"{late}), owner {task.owner}{signed}"
            )
        lines += [f"{group}: {done}/{total} steps done" for group, (done, total) in groups.items()]
        return lines

    def evaluate(self, actor: str, target: str, rating: float, note: str, tick: int) -> None:
        self.evaluations.append(Evaluation(actor, target, rating, note, tick))

    def drain_changes(self) -> list[tuple[str, str]]:
        changes, self._changes = self._changes, []
        return changes

    def snapshot(self) -> dict:
        return {
            "tasks": {task.id: task.snapshot() for task in self.tasks.values()},
            "evaluation_season": self.evaluation_season,
            "promotion_slots": self.promotion_slots,
            "evaluations": [row.__dict__ for row in self.evaluations],
        }

    def restore(self, data: dict) -> None:
        tasks = data.get("tasks", data)
        for task_id, fields in tasks.items():
            self.tasks[task_id].restore(fields)
        self.evaluation_season = data.get("evaluation_season", False)
        self.promotion_slots = data.get("promotion_slots", 0)
        self.evaluations = [Evaluation(**row) for row in data.get("evaluations", [])]
