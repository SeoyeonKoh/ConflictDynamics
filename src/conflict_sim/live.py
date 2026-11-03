"""Live runs the server starts: one `conflict_sim.experiment` process each, detached so a run
outlives the browser and the server. `server-run.json` in the run directory says where it streams
(not `live.json`: older wiki runs already use that name for their transcript).

Spec: docs/superpowers/specs/2026-11-03-viz-main-menu-design.md, sections 5.1-5.2.
"""

import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from .runs import discover_company_runs

PORT_LINE = re.compile(r"Viewer WebSocket: ws://127\.0\.0\.1:(\d+)")
PORT_WAIT_SECONDS = 30
RECORD = "server-run.json"
_children: dict[int, subprocess.Popen] = {}  # ours, so exited ones are reaped, not zombies


def _alive(pid: int) -> bool:
    if pid in _children:
        return _children[pid].poll() is None
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _launch(output_root: Path, run_dir: Path, argv: list[str], backend: str,
            paid_confirmed: bool, meta: dict) -> dict:  # fmt: skip
    if backend == "openai" and not paid_confirmed:
        raise PermissionError("an OpenAI run needs the cost confirmation")
    env = dict(os.environ)
    if backend == "openai":
        env["ALLOW_PAID_API_EXPERIMENTS"] = "1"  # the child only: the user confirmed the cost
    output_root.mkdir(parents=True, exist_ok=True)
    log = output_root / "live.log"
    offset = len(log.read_text(encoding="utf-8")) if log.is_file() else 0  # a resume appends
    with log.open("a", encoding="utf-8") as out:
        process = subprocess.Popen(
            [sys.executable, "-m", "conflict_sim.experiment", *argv],
            stdout=out, stderr=subprocess.STDOUT, env=env, start_new_session=True,
        )  # fmt: skip
    _children[process.pid] = process
    end = time.monotonic() + PORT_WAIT_SECONDS
    while time.monotonic() < end:
        if match := PORT_LINE.search(log.read_text(encoding="utf-8")[offset:]):
            port = int(match[1])
            break
        if process.poll() is not None:
            raise RuntimeError(f"run exited before streaming: {log.read_text()[-2000:]}")
        time.sleep(0.05)
    else:
        process.terminate()
        raise RuntimeError("run did not start streaming in time")
    record = meta | {"id": output_root.name, "pid": process.pid, "port": port,
                     "started": datetime.now().isoformat(timespec="seconds")}  # fmt: skip
    (run_dir / RECORD).write_text(json.dumps(record), encoding="utf-8")
    return {"id": record["id"], "run": str(run_dir.relative_to(output_root.parent)), "port": port}


def start(runs_root: Path, *, scenario: str, days: int, max_total_tokens: int | None,
          backend: str, models: dict, paid_confirmed: bool,
          tick_delay: float | None = None) -> dict:  # fmt: skip
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = f"ui-{stamp}-{scenario}"
    output_root, n = runs_root / base, 1
    while output_root.exists():
        n += 1
        output_root = runs_root / f"{base}-{n}"
    output_root.mkdir(parents=True)  # claim the name before another start can
    argv = [scenario, "--backend", backend, "--pilot", "--days", str(days),
            "--max-total-tokens", str(max_total_tokens or 0), "--live-port", "0",
            "--output-root", str(output_root)]  # fmt: skip
    for key in ("model_decide", "model_speak", "model_embed"):
        if models.get(key):
            argv += [f"--{key.replace('_', '-')}", models[key]]
    if tick_delay is not None:
        argv += ["--tick-delay", str(tick_delay)]
    run_dir = output_root / scenario / "replicate-1"
    meta = {"scenario": scenario, "days": days, "backend": backend}
    return _launch(output_root, run_dir, argv, backend, paid_confirmed, meta)


def resume(runs_root: Path, run: str, *, max_total_tokens: int | None, paid_confirmed: bool,
           tick_delay: float | None = None) -> dict:  # fmt: skip
    run_dir = (runs_root / run).resolve()
    rows, _ = discover_company_runs(runs_root)
    row = next((r for r in rows if r["run"] == run), None)
    if row is None or row["status"] != "paused" or not row["resumable"]:
        raise ValueError(f"{run} cannot be resumed")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    scenario, backend = manifest["scenario"], manifest.get("backend", "demo")
    output_root = run_dir.parent.parent
    argv = [scenario, "--backend", backend, "--pilot", "--resume",
            "--max-total-tokens", str(max_total_tokens or 0), "--live-port", "0",
            "--output-root", str(output_root)]  # fmt: skip
    if tick_delay is not None:
        argv += ["--tick-delay", str(tick_delay)]
    meta = {"scenario": scenario, "backend": backend}
    return _launch(output_root, run_dir, argv, backend, paid_confirmed, meta)


def _records(runs_root: Path):
    if not runs_root.is_dir():
        return
    for path in runs_root.rglob(RECORD):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and {"id", "pid", "port"} <= set(record):
            yield path.parent, record


def _settle(run_dir: Path) -> None:
    """A run whose process ended without saying so (killed, crashed) is paused at its last
    finished tick, so its tape can carry it on."""
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "running" or (run_dir / "paused.json").exists():
        return
    frames = [json.loads(line) for line in _lines(run_dir / "frames.jsonl")]
    ticks = [f["tick"] for f in frames if f.get("type") == "frame"]
    paused = {"status": "paused", "reason": "the run's process ended",
              "tick": (max(ticks) + 1) if ticks else 0, "checkpoint": None}  # fmt: skip
    (run_dir / "paused.json").write_text(json.dumps(paused), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest | {"status": "paused"}), encoding="utf-8")


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.is_file() else []


def active(runs_root: Path) -> list[dict]:
    """Runs whose process is still alive, with where they are."""
    out = []
    for run_dir, record in _records(runs_root):
        if not _alive(record.get("pid", -1)):
            _settle(run_dir)
            continue
        frames = [json.loads(line) for line in _lines(run_dir / "frames.jsonl")[-400:]]
        last = next((f for f in reversed(frames) if f.get("type") == "frame"), {})
        state = next((f["state"] for f in reversed(frames) if f.get("type") == "status"),
                     "running")  # fmt: skip
        out.append({"id": record["id"], "run": str(run_dir.relative_to(runs_root)),
                    "port": record["port"], "scenario": record.get("scenario"),
                    "tick": last.get("tick"), "day": last.get("day"), "status": state})  # fmt: skip
    return out


def mark(runs_root: Path, rows: list[dict]) -> None:
    """Give each listed run its live connection, or None; settle runs whose process died."""
    running = {a["run"]: a for a in active(runs_root)}
    settled, _ = discover_company_runs(runs_root)
    status = {r["run"]: r for r in settled}
    for row in rows:
        now = running.get(row["run"])
        row["live"] = {"id": now["id"], "port": now["port"]} if now else None
        if not now and row["run"] in status:
            row["status"] = status[row["run"]]["status"]
            row["resumable"] = status[row["run"]]["resumable"]
            row["paused_tick"] = status[row["run"]]["paused_tick"]


def stop(runs_root: Path, run_id: str) -> None:
    for _, record in _records(runs_root):
        if record.get("id") == run_id and _alive(record["pid"]):
            os.kill(record["pid"], signal.SIGTERM)
            return
    raise ValueError(f"no live run {run_id}")
