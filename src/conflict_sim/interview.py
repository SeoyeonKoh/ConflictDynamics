"""Post-run interviews: ask one agent, at any tick of a run, what it knew then.

The agent is rebuilt from the run's files, not by replaying the engine: memories up to the tick
(memory.sqlite), state and relationships (inspect.jsonl), place and action (frames.jsonl), the
day's plan (events.jsonl), persona (resolved_config.json). Nothing in the run changes; the
conversation is kept in `interviews/`.
Spec: docs/superpowers/specs/2026-11-03-agent-interview-design.md.
"""

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .agent import human
from .agent.memory import MemoryStore
from .llm import DemoBackend, OpenAIBackend, create_openai_client
from .models import Config, MemoryRecord
from .storage import read_memory

Embed = Callable[[list[str]], list[list[float]]]


@dataclass
class Moment:
    agent: str
    tick: int
    name: str
    title: str | None
    persona: str
    language: str
    stress: float
    mood: float
    relationships: list[dict]
    reflections: list[str]
    place: str | None
    action: str | None
    plan: list[str]
    memory: MemoryStore
    clock: str


def _config(run_dir: Path) -> Config:
    try:
        return Config.model_validate_json((run_dir / "resolved_config.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"run config cannot be read: {exc}") from exc


def _lines(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def clock_of(cfg: Config, tick: int) -> str:
    span = cfg.environment.day_span
    day, minutes = divmod(max(tick, 0), span)
    minutes = 9 * 60 + 15 * minutes
    return f"{day + 1}일차 {minutes // 60:02d}:{minutes % 60:02d}"


def _last_access(run_dir: Path, agent: str, tick: int, records: list[MemoryRecord]) -> dict:
    """When each memory was last recalled by `tick` (the engine's recency), else written."""
    seen = {r.id: r.created_tick for r in records}
    path = run_dir / "memory.sqlite"
    if path.is_file():
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
            rows = db.execute(
                "select tick, ids from retrievals where agent_id = ? and tick <= ? order by tick",
                (agent, tick),
            )
            for at, ids in rows:
                for rid in json.loads(ids):
                    if rid in seen:
                        seen[rid] = max(seen[rid], at)
    return seen


def moment(run_dir: Path, agent: str, tick: int) -> Moment:
    """The agent as it was at the end of `tick`."""
    cfg = _config(run_dir)
    d = human.Directory(cfg)
    if agent not in d.spec:
        raise KeyError(agent)
    spec = d.spec[agent]
    records, vectors = read_memory(run_dir).get(agent, ([], {})) if (
        run_dir / "memory.sqlite").is_file() else ([], {})  # fmt: skip
    records = [r for r in records if r.created_tick <= tick]
    store = MemoryStore(agent, cfg.memory, DemoBackend(), "demo", cfg.temperature, cfg.language)
    store.records = records
    store.set_embeddings({r.id: vectors[r.id] for r in records if vectors.get(r.id) is not None})
    store.last_access = _last_access(run_dir, agent, tick, records)
    inspect = [r for r in _lines(run_dir / "inspect.jsonl")
               if r.get("agent") == agent and r.get("tick", 0) <= tick]  # fmt: skip
    seen = inspect[-1] if inspect else {}
    place = action = None
    for f in _lines(run_dir / "frames.jsonl"):
        if f.get("type") == "frame" and f["tick"] <= tick:
            me = next((a for a in f.get("agents", []) if a.get("id") == agent), None)
            if me:
                place, action = me.get("place"), me.get("action")
    plan: list[str] = []
    for e in _lines(run_dir / "events.jsonl"):
        p = e.get("payload") or {}
        if e.get("tick", 0) <= tick and e.get("kind") == "action" and e.get("actor") == agent \
                and p.get("kind") == "plan":  # fmt: skip
            plan = list(p.get("items") or [])
    return Moment(
        agent=agent, tick=tick, name=d.name[agent], title=spec.role or spec.title,
        persona=human.persona_card(d, agent), language=cfg.language,
        stress=(seen.get("state") or {}).get("stress", 0.0),
        mood=(seen.get("state") or {}).get("mood", 0.0),
        relationships=[r | {"name": d.name.get(r["to"], r["to"])}
                       for r in seen.get("relationships", [])],  # fmt: skip
        reflections=list(seen.get("reflection", [])), place=place, action=action, plan=plan,
        memory=store, clock=clock_of(cfg, tick),
    )  # fmt: skip


def run_embedder(run_dir: Path, env_file: Path) -> Embed | None:
    """The run's own embedding model: its stored vectors only compare with that model's."""
    cfg = _config(run_dir)
    if cfg.backend == "demo":
        return DemoBackend().embed
    has_key = env_file.is_file() and any(
        line.split("=", 1)[0].strip() == "OPENAI_API_KEY" and line.split("=", 1)[1].strip()
        for line in env_file.read_text("utf-8").splitlines() if "=" in line
    )  # fmt: skip
    if not has_key:
        return None
    backend = OpenAIBackend(create_openai_client(env_file), model_embed=cfg.model_embed,
                            max_total_tokens=None)  # fmt: skip
    return backend.embed


def recall(m: Moment, question: str, embed: Embed | None, k: int = 10) -> list[MemoryRecord]:
    """The engine's retrieval over what the agent had by then. A question vector of another
    size than the stored ones (another model) is dropped: recency and importance still rank."""
    vector = None
    if embed is not None and m.memory.vectors:
        got = np.asarray(embed([question])[0], dtype=np.float64)
        size = next(iter(m.memory.vectors.values())).shape
        vector = got if got.shape == size else None
    return m.memory.retrieve(question, vector, m.tick, m.mood, k)
