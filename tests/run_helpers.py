"""Shared tools for tests that stop, resume and compare experiment runs."""

import json
from pathlib import Path

import conflict_sim.experiment as experiment
from conflict_sim.llm import ENGINE_PAYLOAD, DemoBackend


def tick_of(request: dict) -> int | None:
    """The tick a completion is asked at, from the engine payload or a JSON prompt."""
    payload = ENGINE_PAYLOAD.get()
    if payload is None:
        try:
            payload = json.loads(request["prompt"])
        except ValueError:
            return None
    return payload.get("view", {}).get("tick") or payload.get("tick")


def stop_when_tick(monkeypatch, stop, tick: int, base=DemoBackend) -> None:
    """Swap the experiment's demo backend for one that asks to stop once `tick` is reached."""

    class Stops(base):
        def complete(self, **request):
            seen = tick_of(request)
            if seen is not None and seen >= tick:
                stop.set()
            return super().complete(**request)

    monkeypatch.setattr(experiment, "DemoBackend", Stops)


def restore_demo(monkeypatch, base=DemoBackend) -> None:
    monkeypatch.setattr(experiment, "DemoBackend", base)


def rows(run_dir: Path, name: str) -> list[dict]:
    return [json.loads(line) for line in (run_dir / name).read_text().splitlines()]


def frames(run_dir: Path) -> list[dict]:
    """The viewer journal without its status rows."""
    return [row for row in rows(run_dir, "frames.jsonl") if row["type"] != "status"]
