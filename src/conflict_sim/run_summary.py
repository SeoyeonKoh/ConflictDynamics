"""One run's results at a glance, for the viewer's summary page (`GET /api/runs/<run>/summary`).

Read from the run's journals only, so a live run works on what it has written so far and a
paused or finished run works the same way:

- tasks: the board as the last frame shows it (frames.jsonl carries every task once, then
  only the ones that changed), its completion and whether finished work met its due tick;
  summary.json fills in for runs without frames.
- idle: each work-hour rest (lunch and overtime left out) is put in one of three causes,
  the rule from probes/naturalness/reststats.py with the review bottleneck split out:
    other_idle        the agent had an own task ready or in progress and rested anyway;
    waiting_approval  nothing workable, but an own task sat in review, or so did a task an
                      unfinished own task waits on, directly or through other unfinished ones;
    no_workable       nothing workable and nothing waiting on a review.
  A rest counts only when the engine took it as a break: not refused (a `rejected` event at
  that tick), not preparation (reflection "[preparation]", operations.preparation), and, in
  weekly operations, not marked by the `accepted_activity` event as anything but "break"
  (an agent held by a calendar block or a conversation is "interrupted").
  "Own" is the task's team, `Task.workers`: owner, contributors, assigned and helpers.
  Known limits, shared with reststats: the team is the final one, applied back to the tick
  the task was last assigned (a helper who joined late counts from then; an owner replaced
  by an `assign` loses the earlier ticks), and only the waiting side of a review is seen,
  not the reviewer who rests while work waits on them. Unlike reststats, a task counts only
  from its `arrives` tick, and the engine's own changes at a tick (blocked, ready, unblocked,
  logged by `Org.advance` before anyone decides) are seen by those deciding at that tick,
  so the counts can differ from reststats by a few rests a run.
  A live run's newest tick is still being written, so it is left out until the next one.
- stress and relations: each agent's state from inspect.jsonl, which records only changes,
  carried forward tick by tick; summary.json fills in for runs written before it existed.
"""

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from .loop import phase_of

OPEN = {"ready", "in_progress"}  # a task an agent could work on now
LIFECYCLE_OF_CHANGE = {  # task event -> the lifecycle it sets (Org.work/approve/reject, assign)
    "in_progress": "in_progress",
    "revision": "in_progress",
    "review": "review",
    "approved": "done",
    "done": "done",
    "assigned": "ready",
}
BLOCKING = {"blocked": True, "ready": False, "unblocked": False}  # Org.advance's dependency gate
ADVANCE = {*BLOCKING, "arrived", "overdue"}  # logged before the agents decide at that tick
IDLE_KINDS = ("no_workable", "waiting_approval", "other_idle")
CONFLICT = -0.2  # a relation at or below this reads as conflict, not just coolness
RELATION_BINS = (-1.0, -0.5, -0.2, 0.0, 0.2, 0.5, 1.0)


def read_jsonl(path: Path) -> list[dict]:
    """The lines written so far; a live run's last line may be half written, so a line that
    does not parse is skipped rather than failing the whole read."""
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _events(rows: list[dict]) -> list[dict]:
    """Rows shaped like events: a kind, an integer tick and a payload dict."""
    out = []
    for e in rows:
        if isinstance(e, dict) and isinstance(e.get("tick"), int) and e.get("kind"):
            out.append(e | {"payload": e["payload"] if isinstance(e.get("payload"), dict) else {}})
    return sorted(out, key=lambda e: e["tick"])  # stable: event order within a tick


def _inspect(rows: list[dict]) -> list[dict]:
    """Inspect rows with an agent, a tick and a numeric stress."""
    out = []
    for row in rows:
        if not isinstance(row, dict) or row.get("type", "inspect") != "inspect":
            continue
        stress = (row.get("state") or {}).get("stress")
        if (
            row.get("agent")
            and isinstance(row.get("tick", 0), int)
            and isinstance(stress, (int, float))
        ):
            out.append(row)
    return out


def stats(values) -> dict:
    """Mean, population standard deviation, min and max; all None for no values."""
    values = [float(v) for v in values]
    if not values:
        return {"n": 0, "mean": None, "std": None, "min": None, "max": None}
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "std": statistics.pstdev(values),
        "min": min(values),
        "max": max(values),
    }


# ---- tasks ----


def board(frames: list[dict]) -> dict[str, dict]:
    """task id -> the task as the newest frame shows it."""
    tasks: dict[str, dict] = {}
    for frame in frames:
        if isinstance(frame, dict) and frame.get("type") in ("hello", "frame"):
            for task in frame.get("tasks") or []:
                if isinstance(task, dict) and task.get("id"):
                    tasks[task["id"]] = task
    return tasks


def board_from_summary(snapshots: dict, specs: dict[str, dict]) -> dict[str, dict]:
    """The board from summary.json's task snapshots (Task.snapshot), for runs without frames."""
    tasks = {}
    for tid, snap in (snapshots or {}).items():
        if not isinstance(snap, dict):
            continue
        spec = specs.get(tid, {})
        done_tick, due = snap.get("done_tick"), snap.get("due", spec.get("due"))
        status = snap.get("status") or (
            "done"
            if done_tick is not None
            else "overdue"
            if snap.get("overdue")
            else "blocked"
            if snap.get("blocked_since") is not None
            else snap.get("lifecycle") or "ready"
        )
        effort = spec.get("effort_ticks") or 0
        progress = snap.get("progress")
        if progress is None:
            progress = min((snap.get("worked") or 0) / effort, 1.0) if effort else 0.0
        team = [snap.get("owner"), *spec.get("contributors", []), *snap.get("assigned", []),
                *snap.get("helpers", [])]  # fmt: skip
        tasks[tid] = {
            "id": tid,
            "owner": snap.get("owner"),
            "status": status,
            "lifecycle": snap.get("lifecycle") or ("done" if done_tick is not None else "ready"),
            "progress": progress,
            "due": due,
            "depends_on": list(spec.get("depends_on", [])),
            "record": {
                "team": [n for n in team if n],
                "done_tick": done_tick,
                "on_time": None if done_tick is None or due is None else done_tick <= due,
            },
        }
    return tasks


def _finished_at(events: list[dict]) -> dict[str, int]:
    return {
        e.get("actor"): e["tick"]
        for e in events
        if e["kind"] == "task" and e["payload"].get("change") in ("done", "approved")
    }


def task_summary(tasks: dict[str, dict], events: list[dict]) -> dict:
    finished = _finished_at(events)
    by_status = Counter(t.get("status") or "unknown" for t in tasks.values())
    done = [t for t in tasks.values() if t.get("status") == "done"]
    started = [
        t
        for t in tasks.values()
        if t.get("status") == "done"
        or (t.get("lifecycle") or "ready") != "ready"
        or (t.get("progress") or 0) > 0
    ]
    on_time = late = before_start = 0
    for t in done:
        record = t.get("record") or {}
        if record.get("on_time") is not None:
            punctual = bool(record["on_time"])
        else:  # older journals: no record, so judge by the task event
            tick, due = finished.get(t["id"]), t.get("due")
            punctual = tick is not None and (not isinstance(due, (int, float)) or tick <= due)
        on_time += punctual
        late += not punctual
        if isinstance(record.get("done_tick"), int) and record["done_tick"] < 0:
            before_start += 1  # the scenario opened with it finished
    total = len(tasks)
    return {
        "total": total,
        "done": len(done),
        "started": len(started),
        "done_before_start": before_start,
        "completion_pct": 100 * len(done) / total if total else 0.0,
        "mean_progress_pct": (
            100 * statistics.fmean(min(float(t.get("progress") or 0), 1.0) for t in tasks.values())
            if total
            else 0.0
        ),
        "by_status": dict(sorted(by_status.items())),
        "on_time": on_time,
        "late": late,
        "overdue_open": by_status.get("overdue", 0),
    }


# ---- idle ----


def task_states(events: list[dict], initial: dict) -> dict[str, list[tuple[int, bool, str]]]:
    """task -> [(tick, from the engine's advance, state)] in event order (events are sorted by
    tick, stably). The lifecycle and the dependency gate are followed apart, as Task.status
    folds them: unblocked returns a task to its lifecycle (in review stays in review), and the
    scenario's `initial` state comes first."""
    history: dict[str, list[tuple[int, bool, str]]] = defaultdict(list)
    lifecycle: dict[str, str] = {}
    blocked: dict[str, bool] = {}
    for tid, start in (initial or {}).items():
        if isinstance(start, dict) and start.get("state"):
            lifecycle[tid] = start["state"]
            history[tid].append((-1, False, start["state"]))
    for e in events:
        change, tid = e["payload"].get("change"), e.get("actor")
        if e["kind"] != "task" or not tid:
            continue
        if change in LIFECYCLE_OF_CHANGE:
            lifecycle[tid] = LIFECYCLE_OF_CHANGE[change]
        elif change in BLOCKING:
            blocked[tid] = BLOCKING[change]
        else:
            continue
        life = lifecycle.get(tid, "ready")
        state = "done" if life == "done" else "blocked" if blocked.get(tid) else life
        history[tid].append((e["tick"], change in ADVANCE, state))
    return history


def state_before(history: list[tuple[int, bool, str]], tick: int) -> str:
    """A task's state as an agent deciding at `tick` saw it: changes from earlier ticks, and the
    engine's own changes logged at this tick before anyone decided."""
    state = "ready"
    for at, advance, value in history:
        if at > tick or (at == tick and not advance):
            break
        state = value
    return state


def teams(tasks: dict[str, dict], specs: dict[str, dict], events: list[dict]) -> dict:
    """task -> (tick it was last assigned, tick it arrives, who works it); see the module
    docstring for what the final team misses."""
    assigned_at = {
        e.get("actor"): e["tick"]
        for e in events
        if e["kind"] == "task" and e["payload"].get("change") == "assigned"
    }
    out = {}
    for tid in tasks.keys() | specs.keys():
        task, spec = tasks.get(tid, {}), specs.get(tid, {})
        record = task.get("record") or {}
        team = {
            task.get("owner"),
            spec.get("owner"),
            *spec.get("contributors", []),
            *record.get("team", []),
        } - {None}
        out[tid] = (assigned_at.get(tid, 0), spec.get("arrives") or 0, team)
    return out


def classify_rest(agent: str, tick: int, team, history, depends) -> str:
    """Why a work-hour rest happened: one of IDLE_KINDS."""
    mine = [
        tid
        for tid, (since, arrives, workers) in team.items()
        if agent in workers and tick >= since and tick >= arrives
    ]
    now = {tid: state_before(history.get(tid, []), tick) for tid in mine}
    if any(state in OPEN for state in now.values()):
        return "other_idle"

    def waits_on_review(tid: str, seen: set) -> bool:
        for dep in depends.get(tid, []):
            if dep in seen:
                continue
            seen.add(dep)
            state = state_before(history.get(dep, []), tick)
            if state == "review" or (state != "done" and waits_on_review(dep, seen)):
                return True
        return False

    for tid, state in now.items():
        if state == "review" or (state != "done" and waits_on_review(tid, {tid})):
            return "waiting_approval"
    return "no_workable"


def acts(events: list[dict]) -> dict[tuple[str, int], dict]:
    """(agent, tick) -> the act the engine settled on: the last one logged (a refused act is
    followed by its `rejected` event and maybe a retry), with whether it was refused and the
    activity weekly operations recorded for it."""
    out: dict[tuple[str, int], dict] = {}
    for e in events:
        key = (e.get("actor"), e["tick"])
        kind = e["payload"].get("kind")
        if e["kind"] == "action" and kind == "accepted_activity":
            if key in out:
                out[key]["activity"] = e["payload"].get("activity")
        elif e["kind"] == "action" and kind != "plan":
            out[key] = {"payload": e["payload"], "refused": False, "activity": None}
        elif e["kind"] == "rejected" and key in out:
            out[key]["refused"] = True
    return out


def is_break(act: dict) -> bool:
    """A rest the engine took as a break (see the module docstring)."""
    payload = act["payload"]
    return (
        payload.get("kind") == "rest"
        and not act["refused"]
        and not str(payload.get("reflection") or "").startswith("[preparation]")
        and act["activity"] in (None, "break")
    )


def idle_summary(events, config, tasks, agents, last_tick) -> dict:
    """Idle rests over `0..last_tick`, the ticks every agent has finished."""
    tpd = int(config.get("ticks_per_day") or 34)
    overtime = int(config.get("overtime_ticks_per_day") or 0)
    lunch = (config.get("weekly_operations") or {}).get("lunch_start_tick")

    def work_hour(tick: int) -> bool:
        return phase_of(tick, tpd, overtime, lunch) not in ("lunch", "overtime")

    org = (config.get("environment") or {}).get("org") or {}
    specs = {s["id"]: s for s in org.get("tasks", []) if isinstance(s, dict) and s.get("id")}
    team = teams(tasks, specs, events)
    history = task_states(events, org.get("initial") or {})
    depends = {
        tid: (tasks.get(tid, {}).get("depends_on") or specs.get(tid, {}).get("depends_on") or [])
        for tid in team
    }
    counts = Counter()
    per_agent: dict[str, Counter] = {a: Counter() for a in agents}
    for (agent, tick), act in sorted(acts(events).items(), key=lambda kv: kv[0][1]):
        if tick > last_tick or not agent or not work_hour(tick) or not is_break(act):
            continue
        kind = classify_rest(agent, tick, team, history, depends)
        counts[kind] += 1
        per_agent.setdefault(agent, Counter())[kind] += 1
    ticks = sum(1 for t in range(last_tick + 1) if work_hour(t)) if last_tick >= 0 else 0
    work_ticks = ticks * len(per_agent)
    idle = sum(counts.values())

    def pct(n: int, of: int) -> float:
        return 100 * n / of if of else 0.0

    return {
        "work_ticks": work_ticks,
        "idle_ticks": idle,
        "idle_pct": pct(idle, work_ticks),
        "counts": {k: counts[k] for k in IDLE_KINDS},
        "pct_of_work": {k: pct(counts[k], work_ticks) for k in IDLE_KINDS},
        "share_of_idle": {k: pct(counts[k], idle) for k in IDLE_KINDS},
        "per_agent": {
            a: {k: c[k] for k in IDLE_KINDS} | {"work_ticks": ticks}
            for a, c in sorted(per_agent.items())
        },
    }


# ---- stress and relations ----


def agent_states(inspect: list[dict]) -> tuple[dict, dict, dict]:
    """(first, last, by tick): each agent's earliest and newest inspect row, and every row
    per tick for the timeline."""
    first: dict[str, dict] = {}
    last: dict[str, dict] = {}
    by_tick: dict[int, list[dict]] = defaultdict(list)
    for row in inspect:
        if row.get("type", "inspect") != "inspect" or "agent" not in row:
            continue
        first.setdefault(row["agent"], row)
        last[row["agent"]] = row
        by_tick[int(row.get("tick", 0))].append(row)
    return first, last, by_tick


def stress_summary(inspect_rows, fallback: dict, agents, day_span, last_tick) -> dict:
    first, last, by_tick = agent_states(inspect_rows)
    final = {a: row["state"]["stress"] for a, row in last.items()} or {
        a: v for a, v in (fallback or {}).items() if isinstance(v, (int, float))
    }
    timeline = []
    if by_tick:
        current: dict[str, float] = {}
        for tick in range(max(last_tick, max(by_tick)) + 1):
            for row in by_tick.get(tick, []):
                current[row["agent"]] = row["state"]["stress"]
            if current:
                values = list(current.values())
                timeline.append(
                    {
                        "tick": tick,
                        "day": tick // day_span,
                        "mean": statistics.fmean(values),
                        "min": min(values),
                        "max": max(values),
                    }
                )
    days: dict[int, list[float]] = defaultdict(list)
    for point in timeline:
        days[point["day"]].append(point["mean"])
    order = [a for a in agents if a in final] + sorted(set(final) - set(agents))
    return {
        **stats(final.values()),
        "agents": [{"agent": a, "stress": final[a]} for a in order],
        "timeline": timeline,
        "daily": [{"day": d, "mean": statistics.fmean(v)} for d, v in sorted(days.items())],
    }


def _relationships(row: dict) -> list[dict]:
    return [
        r
        for r in row.get("relationships") or []
        if isinstance(r, dict) and r.get("to") and isinstance(r.get("relation"), (int, float))
    ]


def relation_summary(inspect_rows, fallback: dict, events) -> dict:
    first, last, _ = agent_states(inspect_rows)
    edges: dict[tuple[str, str], float] = {}
    start: dict[tuple[str, str], float] = {}
    if last:
        for agent, row in last.items():
            for r in _relationships(row):
                edges[(agent, r["to"])] = float(r["relation"])
        for agent, row in first.items():
            for r in _relationships(row):
                start[(agent, r["to"])] = float(r["relation"])
    else:
        for agent, row in (fallback or {}).items():
            for other, value in (row if isinstance(row, dict) else {}).items():
                if isinstance(value, (int, float)):
                    edges[(agent, other)] = float(value)
    pairs: dict[frozenset, list[float]] = defaultdict(list)
    for (a, b), value in edges.items():
        pairs[frozenset((a, b))].append(value)
    histogram = []
    for lo, hi in zip(RELATION_BINS, RELATION_BINS[1:]):
        top = hi == RELATION_BINS[-1]
        n = sum(1 for v in edges.values() if lo <= v < hi or (top and v == hi))
        histogram.append({"from": lo, "to": hi, "n": n})
    changes = sorted(
        (
            {
                "from": a,
                "to": b,
                "start": start.get((a, b), 0.0),
                "now": v,
                "delta": v - start.get((a, b), 0.0),
            }
            for (a, b), v in edges.items()
        ),
        key=lambda c: abs(c["delta"]),
        reverse=True,
    )
    return {
        **stats(edges.values()),
        "edges": len(edges),
        "pairs": len(pairs),
        "negative_edges": sum(1 for v in edges.values() if v < 0),
        "negative_pairs": sum(1 for vs in pairs.values() if min(vs) < 0),
        "conflict_threshold": CONFLICT,
        "conflict_pairs": sum(1 for vs in pairs.values() if min(vs) <= CONFLICT),
        "mutual_negative_pairs": sum(1 for vs in pairs.values() if len(vs) == 2 and max(vs) < 0),
        "grievances": sum(
            1 for e in events if e["kind"] == "outcome" and e["payload"].get("grievance")
        ),
        "histogram": histogram,
        "changes": [c for c in changes if c["delta"] != 0][:8],
    }


# ---- the run ----

JOURNALS = ("events.jsonl", "frames.jsonl", "inspect.jsonl", "resolved_config.json",
            "manifest.json", "summary.json")  # fmt: skip
_CACHE: dict[Path, tuple[tuple, dict]] = {}


def _stamp(run_dir: Path) -> tuple:
    out = []
    for name in JOURNALS:
        try:
            stat = (run_dir / name).stat()
            out.append((stat.st_mtime_ns, stat.st_size))
        except OSError:
            out.append(None)
    return tuple(out)


def summarize(run_dir: Path) -> dict:
    """The run's summary; the result is kept until one of its journals changes, so a page
    polling a live run does not parse unchanged files again."""
    run_dir = Path(run_dir)
    stamp = _stamp(run_dir)
    cached = _CACHE.get(run_dir)
    if cached and cached[0] == stamp:
        return cached[1]
    result = _summarize(run_dir)
    _CACHE[run_dir] = (stamp, result)
    return result


def _summarize(run_dir: Path) -> dict:
    events = _events(read_jsonl(run_dir / "events.jsonl"))
    frames = [f for f in read_jsonl(run_dir / "frames.jsonl") if isinstance(f, dict)]
    inspect_rows = _inspect(read_jsonl(run_dir / "inspect.jsonl"))
    config = _read(run_dir / "resolved_config.json")
    manifest = _read(run_dir / "manifest.json")
    summary = _read(run_dir / "summary.json")
    summary = (
        summary.get("summary", summary) if isinstance(summary.get("summary"), dict) else summary
    )
    hello = next((f for f in frames if f.get("type") == "hello"), {})
    people = [p for p in hello.get("agents") or [] if isinstance(p, dict) and p.get("id")] or [
        {"id": a["name"], "display_name": a.get("display_name")}
        for a in config.get("agents", [])
        if isinstance(a, dict) and a.get("name")
    ]
    agents = [p["id"] for p in people]
    tpd, overtime = config.get("ticks_per_day") or 34, config.get("overtime_ticks_per_day") or 0
    day_span = int(tpd) + int(overtime)
    ticks = [e["tick"] for e in events] + [
        f["tick"] for f in frames if f.get("type") == "frame" and isinstance(f.get("tick"), int)
    ]
    last_tick = max(ticks, default=-1)
    # The stream's newest status is the run's state now (a run paused in the viewer, or resumed);
    # the manifest's is what the runner last wrote, for runs streamed without one.
    stream = next((f.get("state") for f in reversed(frames) if f.get("type") == "status"), None)
    status = stream or manifest.get("status") or "unknown"
    tasks = board(frames)
    if not tasks:
        org = (config.get("environment") or {}).get("org") or {}
        specs = {s["id"]: s for s in org.get("tasks", []) if isinstance(s, dict) and s.get("id")}
        tasks = board_from_summary(summary.get("tasks") or {}, specs)
    finished = last_tick - 1 if status == "running" else last_tick  # the newest tick is partial
    return {
        "scenario": manifest.get("scenario"),
        "status": status,
        "tick": last_tick,
        "day": last_tick // day_span if last_tick >= 0 else 0,
        "day_span": day_span,
        "agents": [
            {"id": p["id"], "name": p.get("display_name") or p.get("name") or p["id"]}
            for p in people
        ],
        "tasks": task_summary(tasks, events),
        "idle": idle_summary(events, config, tasks, agents, finished),
        "stress": stress_summary(
            inspect_rows, summary.get("stress") or {}, agents, day_span, last_tick
        ),
        "relations": relation_summary(inspect_rows, summary.get("relations") or {}, events),
    }
