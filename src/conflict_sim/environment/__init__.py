"""The world the loop applies Actions to. Whether an Action is valid is judged here and nowhere
else; agents only see the read-only `View` the loop assembles from `env_view`.
"""

from dataclasses import dataclass

from ..models import (
    WORK_PLACES,
    Action,
    AgentSpec,
    BlockedTask,
    EnvironmentConfig,
    HelpWanted,
    PlaceKind,
    Rejected,
    TaskView,
)
from .office import EAT_PLACES, Office
from .org import Org, Task


@dataclass(frozen=True)
class EnvView:
    """The environment's share of a `View`; the loop adds faces, inbox and internal state."""

    place: str
    places: dict[str, PlaceKind]
    present: tuple[str, ...]
    tasks: tuple[TaskView, ...]
    blocked: tuple[BlockedTask, ...]
    help_wanted: tuple[HelpWanted, ...]
    resources: dict[str, int]


class Environment:
    def __init__(self, config: EnvironmentConfig, agents: list[AgentSpec]):
        self.office = Office(config.office, [agent.name for agent in agents])
        self.org = Org(config.org, agents)
        self.chase_cooldown = config.chase_cooldown_ticks
        self.chased: dict[str, int] = {}  # "asker>owner": tick the asker last chased the owner

    def advance(self, tick: int) -> list[tuple[str, str]]:
        return self.org.advance(tick)

    def apply(self, actor: str, action: Action, tick: int) -> Rejected | None:
        """Apply a valid Action and return None, or return why it was refused, changing nothing.

        Conversation actions are validated only; sessions and threads are the loop's.
        """
        if actor not in self.office.location:
            raise KeyError(actor)
        reason = self._refusal(actor, action, tick)
        if reason is not None:
            return Rejected(action=action, reason=reason)
        self._perform(actor, action, tick)
        for target in self._chase_targets(actor, action):
            self.chased[f"{actor}>{target}"] = tick
        return None

    def _blocker_owners(self, actor: str) -> set[str]:
        return {
            waiting.owner
            for task, role in self.org.participating(actor)
            if role in ("owner", "contributor") and not task.done
            for waiting in self.org.unfinished_prerequisites(task)
            if waiting.owner not in (None, actor)
        }

    def _chase_targets(self, actor: str, action: Action) -> list[str]:
        """The owners of my blockers this talk or message addresses."""
        if not self.chase_cooldown or action.kind not in ("talk", "message"):
            return []
        targets = action.targets if action.kind == "talk" else [action.target]
        blockers = self._blocker_owners(actor)
        return [target for target in targets if target in blockers]

    def _refusal(self, actor: str, action: Action, tick: int) -> str | None:
        office, org = self.office, self.org
        # A place on any kind means "go there first"; moving costs no tick (plan §1-1).
        if action.place is not None:
            if action.place not in office.places:
                return f"unknown place {action.place}"
            if office.location[actor] != action.place and office.free(action.place) == 0:
                return f"{action.place} is full"
        here = office.places[action.place].kind if action.place else office.kind(actor)
        match action.kind:
            case "work":
                task = org.tasks.get(action.task)
                if task is None:
                    return f"unknown task {action.task}"
                if actor not in task.workers:
                    return f"{task.id} belongs to {task.owner or 'nobody'}"
                if task.done:
                    return f"{task.id} is already done"
                if task.lifecycle == "review":
                    return f"{task.id} is awaiting review"
                if waiting := org.unfinished_prerequisites(task):
                    return f"{task.id} is blocked by {', '.join(t.id for t in waiting)}"
                if task.forced_block_until is not None and tick < task.forced_block_until:
                    return f"{task.id} is unavailable until tick {task.forced_block_until}"
                if here not in WORK_PLACES:
                    return f"cannot work in {action.place or office.location[actor]}"
            case "leave":
                # Home early only with nothing left: no open task of mine, nothing to approve.
                for task, role in org.participating(actor):
                    if role in ("owner", "contributor", "helper") and not task.done:
                        return f"{task.id} is not done yet"
                    if task.lifecycle == "review" and org.can(
                        actor, "approve", task.spec.authority_scope
                    ):
                        return f"{task.id} waits for your review"
            case "help" | "ask_help":
                task = org.tasks.get(action.task)
                if task is None:
                    return f"unknown task {action.task}"
                if not org.max_workers:
                    return "nobody can join a task in this organisation"
                if task.done or task.lifecycle == "review":
                    return f"{task.id} needs no more work"
                if action.kind == "ask_help" and actor not in task.workers:
                    return f"{actor} does not work on {task.id}"
                if action.kind == "help" and actor in task.workers:
                    return f"{actor} already works on {task.id}"
                if org.free_slots(task) == 0:
                    return f"{task.id} already has {org.max_workers} people on it"
                if waiting := org.unfinished_prerequisites(task):
                    return f"{task.id} is blocked by {', '.join(t.id for t in waiting)}"
            case "eat":
                if here not in EAT_PLACES:
                    return f"no food in {action.place or office.location[actor]}"
            case "talk":
                where = action.place or office.location[actor]
                present = [other for other in office.occupants(where) if other != actor]
                if missing := [name for name in action.targets if name not in present]:
                    return f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} not here"
            case "message" | "chat" | "gossip":
                if action.target not in office.location or action.target == actor:
                    return f"no other agent named {action.target}"
                if action.kind == "gossip" and action.subject not in office.location:
                    return f"no agent named {action.subject}"
            case "report":
                manager = org.manager[actor]
                if manager is None:
                    return f"{actor} has no manager to report to"
                if action.target != manager:
                    return f"reports go to {manager}, not {action.target}"
            case "assign":
                task = org.tasks.get(action.task)
                if task is None:
                    return f"unknown task {action.task}"
                if not org.can(actor, "assign", task.spec.authority_scope):
                    return f"{actor} may not assign {task.spec.authority_scope or task.id}"
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
                task = org.tasks.get(action.task)
                if task is None:
                    return f"unknown task {action.task}"
                if not org.can(actor, action.kind, task.spec.authority_scope):
                    return f"{actor} may not {action.kind} {task.spec.authority_scope or task.id}"
                if task.lifecycle == "review":
                    return None
                if task.request is None:
                    return f"nothing to {action.kind} on {task.id}"
            case "evaluate":
                if not org.evaluation_season:
                    return "evaluation season is not active"
                if not org.can(actor, "evaluate", "all_agents"):
                    return f"{actor} may not evaluate"
                if action.target not in office.location or action.target == actor:
                    return f"no other agent named {action.target}"
        if chased := self._chase_targets(actor, action):
            targets = action.targets if action.kind == "talk" else [action.target]
            asked = {name: self.chased.get(f"{actor}>{name}") for name in chased}
            cooling = {name: at for name, at in asked.items()
                       if at is not None and tick - at < self.chase_cooldown}  # fmt: skip
            if len(cooling) == len(targets):  # someone else in the talk lets it through
                last = max(cooling.values())
                return (
                    f"already asked {', '.join(cooling)} about the blocked work at tick {last}; "
                    f"wait for an answer until tick {last + self.chase_cooldown}"
                )
        return None

    def _perform(self, actor: str, action: Action, tick: int) -> None:
        if action.place is not None:
            self.office.location[actor] = action.place
        match action.kind:
            case "work":
                self.org.work(self.org.tasks[action.task], tick)
            case "assign":
                task = self.org.tasks[action.task]
                task.owner = action.target
                task.lifecycle = "ready"
                self.org._changes.append((task.id, "assigned"))
            case "request":
                self.org.tasks[action.task].request = actor
            case "help":
                self.org.tasks[action.task].helpers.append(actor)
            case "leave":
                self.office.location[actor] = self.office.lobby
            case "ask_help":
                self.org.tasks[action.task].help_wanted = True
            case "approve":
                task = self.org.tasks[action.task]
                if task.lifecycle == "review":
                    self.org.approve(task, tick)
                else:
                    # Grant exactly the time still needed, counted from now if deadline passed.
                    task.due = max(task.due, tick) + task.remaining
                    task.request = None
            case "reject":
                task = self.org.tasks[action.task]
                if task.lifecycle == "review":
                    self.org.reject(task)
                else:
                    task.request = None
            case "evaluate":
                self.org.evaluate(actor, action.target, action.rating, action.text, tick)

    def env_view(self, name: str) -> EnvView:
        tasks = self.org.participating(name)
        return EnvView(
            place=self.office.location[name],
            places={p.id: p.kind for p in self.office.places.values()},
            present=self.office.present(name),
            tasks=tuple(self._task_view(name, task, role) for task, role in tasks),
            blocked=tuple(
                BlockedTask(
                    task=task.id,
                    waiting_on=waiting.id,
                    owner=waiting.owner or "nobody",
                    since_tick=task.blocked_since,
                    due=task.due,
                    asked_tick=self.chased.get(f"{name}>{waiting.owner}"),
                )
                for task, role in tasks
                if role in ("owner", "contributor")
                if task.blocked_since is not None and not task.done
                for waiting in self.org.unfinished_prerequisites(task)
            ),
            help_wanted=tuple(
                HelpWanted(
                    task=task.id,
                    description=task.spec.description,
                    owner=task.owner,
                    free_slots=self.org.free_slots(task),
                    due=task.due,
                )
                for task in self.org.tasks.values()
                if task.help_wanted and name not in task.workers and self.org.free_slots(task)
                if not task.done and task.lifecycle != "review"
                if not self.org.unfinished_prerequisites(task)
            ),
            resources=self.office.resources(),
        )

    def _task_view(self, name: str, task: Task, role: str) -> TaskView:
        return TaskView(
            id=task.id,
            description=task.spec.description,
            owner=task.owner,
            progress=task.progress,
            due=task.due,
            remaining_ticks=task.remaining,
            depends_on=list(task.spec.depends_on),
            status=task.status,
            lifecycle=task.lifecycle,
            overdue=task.overdue,
            role=role,
            can_approve=self.org.can(name, "approve", task.spec.authority_scope),
            can_reject=self.org.can(name, "reject", task.spec.authority_scope),
            helpers=list(task.helpers),
            help_wanted=task.help_wanted,
        )

    def snapshot(self) -> dict:
        """The whole mutable state, JSON-friendly; `restore` takes it back."""
        tasks = {task.id: task.legacy_snapshot() for task in self.org.tasks.values()}
        return {
            "places": dict(self.office.location),
            "capacities": dict(self.office.capacity),
            "org": self.org.snapshot(),
            "chased": dict(self.chased),
            "tasks": tasks,  # legacy checkpoint/readers
        }

    def restore(self, data: dict) -> None:
        self.office.location.update(data["places"])
        self.office.capacity.update(data.get("capacities", {}))
        self.org.restore(data.get("org", data.get("tasks", {})))
        self.chased = dict(data.get("chased", {}))

    def apply_shock(
        self,
        kind: str,
        *,
        tick: int,
        task: str | None,
        resource: str | None,
        amount: int,
        until_tick: int | None,
    ) -> dict:
        """Apply one scheduled structural change and return its observable state delta."""
        if kind == "deadline_compression":
            target = self.org.tasks[task]
            before = target.due
            target.due = max(tick, target.due - abs(amount))
            return {"task": task, "due_before": before, "due_after": target.due}
        if kind in {"dependency_failure", "information_delay"}:
            target = self.org.tasks[task]
            target.forced_block_until = until_tick if until_tick is not None else tick + abs(amount)
            return {"task": task, "blocked_until": target.forced_block_until}
        if kind == "resource_loss":
            before = self.office.capacity[resource]
            self.office.adjust_capacity(resource, -abs(amount))
            return {
                "resource": resource,
                "capacity_before": before,
                "capacity_after": self.office.capacity[resource],
            }
        if kind == "evaluation_announcement":
            self.org.evaluation_season = True
            return {"evaluation_season": True}
        if kind == "requirement_change":
            target = self.org.tasks[task]
            target.worked = max(0, target.worked - abs(amount))
            target.done_tick = None
            target.lifecycle = "in_progress"
            return {"task": task, "worked_after": target.worked}
        raise ValueError(f"unknown shock kind {kind}")
