"""Organisation state: who holds which authority, and the mutable task list."""

from dataclasses import dataclass

from ..models import AgentSpec, Authority, OrgConfig, TaskSpec


@dataclass
class Task:
    """Runtime state of one `TaskSpec`. `blocked_since` and `overdue` are set by `Org.advance`."""

    spec: TaskSpec
    owner: str | None
    due: int  # copied from the spec so an approved extension can move it
    worked: int = 0
    done_tick: int | None = None
    blocked_since: int | None = None
    overdue: bool = False
    request: str | None = None  # who asked for an extension and awaits a ruling

    @property
    def id(self) -> str:
        return self.spec.id

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
        return "open"

    STATE = ("owner", "due", "worked", "done_tick", "blocked_since", "overdue", "request")

    def snapshot(self) -> dict:
        fields = {name: getattr(self, name) for name in self.STATE}
        return fields | {"progress": self.progress, "status": self.status}  # derived, for readers

    def restore(self, data: dict) -> None:
        for name in self.STATE:
            setattr(self, name, data[name])


class Org:
    def __init__(self, config: OrgConfig, agents: list[AgentSpec]):
        self.titles = config.titles
        self.title = {agent.name: agent.title for agent in agents}
        self.manager = {agent.name: agent.reports_to for agent in agents}
        self.tasks = {task.id: Task(task, task.owner, task.due) for task in config.tasks}

    def can(self, name: str, authority: Authority) -> bool:
        return authority in self.titles.get(self.title[name] or "", [])

    def owned(self, name: str) -> list[Task]:
        return [task for task in self.tasks.values() if task.owner == name]

    def unfinished_prerequisites(self, task: Task) -> list[Task]:
        return [self.tasks[dep] for dep in task.spec.depends_on if not self.tasks[dep].done]

    def advance(self, tick: int) -> list[tuple[str, str]]:
        """Judge deadlines and dependencies once per tick; returns (task id, change) pairs."""
        changes = []
        for task in self.tasks.values():
            if task.done:
                continue
            blocked = bool(self.unfinished_prerequisites(task))
            if blocked and task.blocked_since is None:
                task.blocked_since = tick
                changes.append((task.id, "blocked"))
            elif not blocked and task.blocked_since is not None:
                task.blocked_since = None
                changes.append((task.id, "unblocked"))
            if tick > task.due and not task.overdue:
                task.overdue = True
                changes.append((task.id, "overdue"))
        return changes
