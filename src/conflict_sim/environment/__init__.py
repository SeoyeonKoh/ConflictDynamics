"""The world the loop applies Actions to. Whether an Action is valid is judged here and nowhere
else; agents only see the read-only `View` the loop assembles from `env_view`.
"""

from dataclasses import dataclass

from ..models import (
    Action,
    AgentSpec,
    BlockedTask,
    EnvironmentConfig,
    PlaceKind,
    Rejected,
    TaskView,
)
from .office import EAT_PLACES, WORK_PLACES, Office
from .org import Org, Task


@dataclass(frozen=True)
class EnvView:
    """The environment's share of a `View`; the loop adds faces, inbox and internal state."""

    place: str
    places: dict[str, PlaceKind]
    present: tuple[str, ...]
    tasks: tuple[TaskView, ...]
    blocked: tuple[BlockedTask, ...]
    resources: dict[str, int]


class Environment:
    def __init__(self, config: EnvironmentConfig, agents: list[AgentSpec]):
        self.office = Office(config.office, [agent.name for agent in agents])
        self.org = Org(config.org, agents)

    def advance(self, tick: int) -> list[tuple[str, str]]:
        return self.org.advance(tick)

    def apply(self, actor: str, action: Action, tick: int) -> Rejected | None:
        """Apply a valid Action and return None, or return why it was refused, changing nothing.

        `talk · message · chat · report` are validated only; sessions and threads are the loop's.
        """
        if actor not in self.office.location:
            raise KeyError(actor)
        reason = self._refusal(actor, action)
        if reason is not None:
            return Rejected(action=action, reason=reason)
        self._perform(actor, action, tick)
        return None

    def _refusal(self, actor: str, action: Action) -> str | None:
        office, org = self.office, self.org
        match action.kind:
            case "move":
                if action.place not in office.places:
                    return f"unknown place {action.place}"
                if office.location[actor] != action.place and office.free(action.place) == 0:
                    return f"{action.place} is full"
            case "work":
                task = org.tasks.get(action.task)
                if task is None:
                    return f"unknown task {action.task}"
                if task.owner != actor:
                    return f"{task.id} belongs to {task.owner or 'nobody'}"
                if task.done:
                    return f"{task.id} is already done"
                if waiting := org.unfinished_prerequisites(task):
                    return f"{task.id} is blocked by {', '.join(t.id for t in waiting)}"
                if office.kind(actor) not in WORK_PLACES:
                    return f"cannot work in {office.location[actor]}"
            case "eat":
                if office.kind(actor) not in EAT_PLACES:
                    return f"no food in {office.location[actor]}"
            case "talk":
                present = office.present(actor)
                if action.target is not None and action.target not in present:
                    return f"{action.target} is not here"
                if not present:
                    return f"alone in {office.location[actor]}"
            case "message" | "chat":
                if action.target not in office.location or action.target == actor:
                    return f"no other agent named {action.target}"
            case "report":
                manager = org.manager[actor]
                if manager is None:
                    return f"{actor} has no manager to report to"
                if action.target != manager:
                    return f"reports go to {manager}, not {action.target}"
            case "assign":
                if not org.can(actor, "assign"):
                    return f"{actor} may not assign"
                if action.task not in org.tasks:
                    return f"unknown task {action.task}"
                if action.target not in office.location:
                    return f"no agent named {action.target}"
            case "request":
                task = org.tasks.get(action.task)
                if task is None:
                    return f"unknown task {action.task}"
                if task.owner != actor:
                    return f"{task.id} belongs to {task.owner or 'nobody'}"
                if task.done:
                    return f"{task.id} is already done"
                if task.request is not None:
                    return f"{task.id} already has a pending request"
            case "approve" | "reject":
                if not org.can(actor, action.kind):
                    return f"{actor} may not {action.kind}"
                task = org.tasks.get(action.task)
                if task is None:
                    return f"unknown task {action.task}"
                if task.request is None:
                    return f"nothing to {action.kind} on {task.id}"
        return None

    def _perform(self, actor: str, action: Action, tick: int) -> None:
        match action.kind:
            case "move":
                self.office.location[actor] = action.place
            case "work":
                task = self.org.tasks[action.task]
                task.worked += 1
                if task.worked >= task.spec.effort_ticks:
                    task.done_tick = tick
            case "assign":
                self.org.tasks[action.task].owner = action.target
            case "request":
                self.org.tasks[action.task].request = actor
            case "approve":
                task = self.org.tasks[action.task]
                # Grant exactly the time still needed, counted from now if the deadline passed.
                task.due = max(task.due, tick) + task.remaining
                task.request = None
            case "reject":
                self.org.tasks[action.task].request = None

    def env_view(self, name: str) -> EnvView:
        tasks = self.org.owned(name)
        return EnvView(
            place=self.office.location[name],
            places={p.id: p.kind for p in self.office.places.values()},
            present=self.office.present(name),
            tasks=tuple(self._task_view(task) for task in tasks),
            blocked=tuple(
                BlockedTask(
                    task=task.id,
                    waiting_on=waiting.id,
                    owner=waiting.owner or "nobody",
                    since_tick=task.blocked_since,
                    due=task.due,
                )
                for task in tasks
                if task.blocked_since is not None and not task.done
                for waiting in self.org.unfinished_prerequisites(task)
            ),
            resources=self.office.resources(),
        )

    @staticmethod
    def _task_view(task: Task) -> TaskView:
        return TaskView(
            id=task.id,
            description=task.spec.description,
            owner=task.owner,
            progress=task.progress,
            due=task.due,
            depends_on=list(task.spec.depends_on),
        )

    def snapshot(self) -> dict:
        return {
            "places": dict(self.office.location),
            "tasks": {
                task.id: {
                    "owner": task.owner,
                    "progress": task.progress,
                    "due": task.due,
                    "status": task.status,
                }
                for task in self.org.tasks.values()
            },
        }
