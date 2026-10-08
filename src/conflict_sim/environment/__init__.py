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
from .org import MAX_RETURNS, Org, Task


@dataclass(frozen=True)
class EnvView:
    """The environment's share of a `View`; the loop adds faces, inbox and internal state."""

    place: str
    places: dict[str, PlaceKind]
    present: tuple[str, ...]
    tasks: tuple[TaskView, ...]
    blocked: tuple[BlockedTask, ...]
    help_wanted: tuple[HelpWanted, ...]
    task_board: tuple[str, ...]
    resources: dict[str, int]
    workable: tuple[str, ...]  # my tasks `work` would not be refused on now, soonest due first


class Environment:
    def __init__(self, config: EnvironmentConfig, agents: list[AgentSpec]):
        self.office = Office(config.office, [agent.name for agent in agents])
        self.org = Org(config.org, agents)
        self.chase_cooldown = config.chase_cooldown_ticks
        self.chased: dict[str, int] = {}  # "asker>owner": tick the asker last chased the owner
        self.tick = 0  # the tick last advanced to, for views

    def advance(self, tick: int) -> list[tuple[str, str]]:
        self.tick = tick
        return self.org.advance(tick)

    def apply(self, actor: str, action: Action, tick: int, work_rate: float = 1) -> Rejected | None:
        """Apply a valid Action and return None, or return why it was refused, changing nothing.

        Conversation actions are validated only; sessions and threads are the loop's.
        """
        if actor not in self.office.location:
            raise KeyError(actor)
        reason = self._refusal(actor, action, tick)
        if reason is not None:
            return Rejected(action=action, reason=reason)
        self._perform(actor, action, tick, work_rate)
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
        if action.task in org.tasks and not org.arrived(org.tasks[action.task]):
            return f"unknown task {action.task}"  # work nobody knows of yet
        # A place on any kind means "go there first"; moving costs no tick (plan §1-1).
        if action.place is not None:
            if action.place not in office.places:
                return f"unknown place {action.place}"
            if office.location[actor] != action.place and office.free(action.place) == 0:
                return f"{action.place} is full"
        here = office.places[action.place].kind if action.place else office.kind(actor)
        match action.kind:
            case "work":
                if reason := self._work_refusal(actor, action.task, tick):
                    return reason
                if here not in WORK_PLACES:
                    return f"cannot work in {action.place or office.location[actor]}"
            case "leave":
                # Home early only with nothing left: no open task of mine, nothing to approve.
                for task, role in org.participating(actor):
                    if role in ("owner", "contributor", "helper") and not task.done:
                        return f"{task.id} is not done yet"
                    if task.lifecycle == "review" and actor in org.signers(task):
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
                if task.owner is not None:  # handed out already, maybe this very tick by another
                    return f"{task.id} belongs to {task.owner}"
                if action.target not in office.location:
                    return f"no agent named {action.target}"
                # Team members besides the owner: real people, each once, within the task's cap.
                team = [action.target, *action.targets]
                if missing := [name for name in action.targets if name not in office.location]:
                    return f"no agent named {', '.join(missing)}"
                if len(set(team)) != len(team):
                    return "name each person once"
                staff = {*task.spec.contributors, *task.helpers, *team}
                if org.max_workers and len(staff) > org.max_workers:
                    return f"{task.id} takes at most {org.max_workers} people"
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
                if task.lifecycle == "review":
                    if actor not in org.signers(task):
                        if actor in task.workers or actor in task.worked_by:
                            return f"{task.id} is {actor}'s own work; someone else signs it off"
                        scope = task.spec.authority_scope or task.id
                        return f"{actor} may not {action.kind} {scope}"
                    if action.kind == "reject" and len(task.rejections) >= MAX_RETURNS:
                        times = len(task.rejections)
                        return f"{task.id} was returned {times} times; it can only be approved now"
                    return None
                if not org.can(actor, action.kind, task.spec.authority_scope):
                    return f"{actor} may not {action.kind} {task.spec.authority_scope or task.id}"
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

    def _work_refusal(self, actor: str, task_id: str | None, tick: int) -> str | None:
        """Why `actor` may not work on the task at `tick`, wherever they stand; None if they may."""
        task = self.org.tasks.get(task_id)
        if task is None:
            return f"unknown task {task_id}"
        if actor not in task.workers:
            return f"{task.id} belongs to {task.owner or 'nobody'}"
        if task.done:
            return f"{task.id} is already done"
        if task.lifecycle == "review":
            return f"{task.id} is awaiting review"
        if waiting := self.org.unfinished_prerequisites(task):
            return f"{task.id} is blocked by {', '.join(t.id for t in waiting)}"
        if task.forced_block_until is not None and tick < task.forced_block_until:
            return f"{task.id} is unavailable until tick {task.forced_block_until}"
        return None

    def _perform(self, actor: str, action: Action, tick: int, work_rate: float = 1) -> None:
        if action.place is not None:
            self.office.location[actor] = action.place
        match action.kind:
            case "work":
                self.org.work(self.org.tasks[action.task], tick, actor, work_rate)
            case "assign":
                task = self.org.tasks[action.task]
                task.owner = action.target
                task.assigned = list(action.targets)
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
                    self.org.approve(task, tick, actor, action.text)
                else:
                    # Grant exactly the time still needed, counted from now if deadline passed.
                    task.due = max(task.due, tick) + task.remaining
                    task.request = None
            case "reject":
                task = self.org.tasks[action.task]
                if task.lifecycle == "review":
                    self.org.reject(task, actor, action.text, tick)
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
            task_board=tuple(self.org.board()),
            resources=self.office.resources(),
            workable=tuple(
                task.id
                for task, _ in sorted(tasks, key=lambda row: row[0].due)
                if self._work_refusal(name, task.id, self.tick) is None
            ),
        )

    def task_view(self, name: str, task_id: str) -> TaskView:
        """One task as `name` sees it, whatever their part in it (the owner's summary call)."""
        task = self.org.tasks[task_id]
        role = next((r for t, r in self.org.participating(name) if t is task), "owner")
        return self._task_view(name, task, role, full=True)

    def _task_view(self, name: str, task: Task, role: str, full: bool = False) -> TaskView:
        brief = task.done and not full  # see below
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
            can_approve=(
                name in self.org.signers(task)
                if task.lifecycle == "review"
                else self.org.can(name, "approve", task.spec.authority_scope)
            ),
            can_reject=(
                name in self.org.signers(task) and len(task.rejections) < MAX_RETURNS
                if task.lifecycle == "review"
                else self.org.can(name, "reject", task.spec.authority_scope)
            ),
            helpers=list(task.helpers),
            help_wanted=task.help_wanted,
            # In a view a finished task shows only its record, without the document: the document
            # reaches whoever builds on it through their open task's "inputs". Repeating summary
            # and document beside the record made them a third of every act prompt
            # (p0_documents). The summary call (`full`) still sees what the task produces.
            summary=None if brief else task.summary,
            record=(_without_document(self.org.record(task)) if brief else self.org.record(task))
            if task.done
            else None,
            deliverable=None if brief else task.spec.deliverable,
            criteria=None if brief else task.spec.criteria,
            document=None if brief else task.document,
            materials=None if brief else task.spec.materials,
            # What the work builds on, for whoever does or reviews it while it is open.
            inputs=(
                [
                    # Written work may still wait for approval: say so, or it reads as done.
                    {"id": p.id, "lifecycle": p.lifecycle, "document": p.document,
                     "summary": p.summary}  # fmt: skip
                    for p in (self.org.tasks[d] for d in task.spec.depends_on)
                ]
                if not task.done and role in ("owner", "contributor", "helper", "reviewer")
                else []
            ),
            rejections=list(task.rejections),
            project=task.spec.group,
            cross=task.spec.cross,
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


def _without_document(record: dict) -> dict:
    return {k: v for k, v in record.items() if k != "document"}
