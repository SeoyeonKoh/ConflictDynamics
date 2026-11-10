"""Post-run interviews: ask one agent, at any tick of a run, what it knew then.

The agent is rebuilt from the run's files, not by replaying the engine: memories up to the tick
(memory.sqlite), state and relationships (inspect.jsonl), place and action (frames.jsonl), the
day's plan (events.jsonl), persona (resolved_config.json). Nothing in the run changes; the
conversation is kept in `interviews/`.
Spec: docs/superpowers/specs/2026-11-03-agent-interview-design.md.
"""

import json
import os
import re
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from .agent import human
from .agent.memory import MemoryStore
from .llm import DemoBackend, OpenAIBackend, create_openai_client, make_embedder
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
    span: int  # ticks in a day


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
    records, vectors = read_memory(run_dir, readonly=True).get(agent, ([], {})) if (
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
        memory=store, clock=clock_of(cfg, tick), span=cfg.environment.day_span,
    )  # fmt: skip


def run_backend(run_dir: Path) -> str:
    return _config(run_dir).backend


def run_reasoning_effort(run_dir: Path) -> str:
    """The reasoning setting the run's own calls used. The interview sends a temperature, which
    gpt-6 models take only with reasoning off; a run without the setting gets "none"."""
    return _config(run_dir).reasoning_effort or "none"


def run_embedder(run_dir: Path, env_file: Path) -> Embed | None:
    """The run's own embedding model: its stored vectors only compare with that model's."""
    cfg = _config(run_dir)
    if cfg.backend == "demo":
        return DemoBackend().embed
    if cfg.backend == "claude" and cfg.embed_backend == "local":
        return make_embedder("local", cfg.model_embed, env_file)
    has_key = env_file.is_file() and any(
        line.split("=", 1)[0].strip() == "OPENAI_API_KEY" and line.split("=", 1)[1].strip()
        for line in env_file.read_text("utf-8").splitlines() if "=" in line
    )  # fmt: skip
    if not has_key:
        return None
    if cfg.backend == "claude":
        return make_embedder("openai", cfg.model_embed, env_file)
    backend = OpenAIBackend(create_openai_client(env_file), model_embed=cfg.model_embed,
                            max_total_tokens=None)  # fmt: skip
    return backend.embed


def question_embedder(run_backend: str, provider: str, env_file: Path, run_dir: Path | None = None
                      ) -> Embed | None:  # fmt: skip
    """How a question is embedded: with the run's own model, but never a paid call when the
    chosen provider is the free demo (a demo-provider question about an OpenAI run ranks by
    recency and importance alone). A Claude run's local embeddings cost nothing: always used."""
    if run_backend == "demo":
        return DemoBackend().embed
    if run_dir is None:
        return None
    if run_backend == "claude" and _config(run_dir).embed_backend == "local":
        return run_embedder(run_dir, env_file)
    if provider not in ("openai", "claude"):
        return None
    return run_embedder(run_dir, env_file)


def recall(m: Moment, question: str, embed: Embed | None, k: int = 10) -> list[MemoryRecord]:
    """The engine's retrieval over what the agent had by then. A question vector of another
    size than the stored ones (another model) is dropped: recency and importance still rank."""
    vector = None
    if embed is not None and m.memory.vectors:
        got = np.asarray(embed([question])[0], dtype=np.float64)
        size = next(iter(m.memory.vectors.values())).shape
        vector = got if got.shape == size else None
    return m.memory.retrieve(question, vector, m.tick, m.mood, k)


# --- answering ---

INSTRUCTIONS = {
    "Korean": (
        "너는 {name}이다. 지금은 {clock}이다. 너는 이 시점까지 겪은 일만 안다. 연구자가 너를 "
        "인터뷰하고 있다. 1인칭으로, 평소 네 말투로 짧고 솔직하게 답하라. 기억에 없는 것은 "
        "모른다고 하라. 이 인터뷰는 네 일과 행동에 아무 영향을 주지 않는다."
    ),
    "English": (
        "You are {name}. It is now {clock}. You know only what happened to you until now. A "
        "researcher is interviewing you. Answer in the first person, in your own voice, briefly "
        "and honestly. Say you do not know what you do not remember. This interview changes "
        "nothing about your work or what you do."
    ),
}
MAX_QUESTION = 2000
RECENT_TURNS = 8


def prompt(m: Moment, memories: list[MemoryRecord], turns: list[dict], question: str
           ) -> tuple[str, str]:  # fmt: skip
    """(system, prompt): who I am and what I remember now, the talk so far, the question."""
    ko = m.language == "Korean"
    system = INSTRUCTIONS["Korean" if ko else "English"].format(name=m.name, clock=m.clock)
    system += "\n\n" + m.persona
    label = (lambda k, e: k) if ko else (lambda k, e: e)
    lines = [
        f"{label('지금', 'Now')}: {m.clock}"
        + (f" · {label('장소', 'place')} {m.place}" if m.place else "")
        + (f" · {label('하던 일', 'doing')} {m.action}" if m.action else ""),
        f"{label('스트레스', 'stress')} {m.stress:.2f} · {label('기분', 'mood')} {m.mood:+.2f}",
    ]
    if m.plan:
        lines += [label("오늘 계획:", "Today's plan:")] + [f"- {p}" for p in m.plan]
    if m.reflections:
        lines.append(label("최근 돌아본 것:", "Recent reflections:"))
        lines += [f"- {r}" for r in m.reflections[-3:]]
    if m.relationships:
        lines.append(label("관계: ", "Relationships: ") + ", ".join(
            f"{r['name']} {r['relation']:+.2f}" for r in m.relationships))
    lines.append(label("떠오르는 기억:", "What comes to mind:"))
    lines += [f"- ({clock_of_tick(m, r.created_tick)}) {r.description}" for r in memories]
    for turn in turns[-RECENT_TURNS:]:
        lines += [f"{label('질문', 'Q')}: {turn['q']}", f"{label('나', 'Me')}: {turn['a']}"]
    lines.append(f"{label('질문', 'Q')}: {question}")
    return system, "\n".join(lines)


def clock_of_tick(m: Moment, tick: int) -> str:
    """A memory's time in the moment's words: just the time on the same day."""
    day, minutes = divmod(max(tick, 0), m.span)
    minutes = 9 * 60 + 15 * minutes
    hhmm = f"{minutes // 60:02d}:{minutes % 60:02d}"
    return hhmm if day == max(m.tick, 0) // m.span else f"{day + 1}일차 {hhmm}"


class DemoInterviewer:
    """Scripted answers for the demo provider: quotes the first memories the question recalled."""

    def complete(self, *, system: str, prompt: str, **_) -> str:
        recalled = [line[2:] for line in prompt.splitlines() if line.startswith("- (")][:2]
        if not recalled:
            return "글쎄요, 지금은 딱히 떠오르는 게 없어요."
        return "제가 기억하기로는 " + " / ".join(r.split(") ", 1)[-1] for r in recalled) + "."


# --- keeping interviews ---

_ID = re.compile(r"^[\w.-]+$")
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_LOCK = threading.Lock()


def _lock(path: Path) -> threading.Lock:
    """One ask at a time per interview file: two at once would each keep only their own turn."""
    with _LOCKS_LOCK:
        return _LOCKS.setdefault(str(path), threading.Lock())


def _write(path: Path, record: dict) -> None:
    """Whole or not at all: a reader never sees half a file."""
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(record, ensure_ascii=False, indent=1), "utf-8")
    os.replace(temp, path)


def _segments(run_dir: Path) -> int:
    manifest = run_dir / "manifest.json"
    if not manifest.is_file():
        return 0
    return len(json.loads(manifest.read_text("utf-8")).get("token_usage_segments") or [])


def _path(run_dir: Path, interview_id: str) -> Path:
    path = run_dir / "interviews" / f"{interview_id}.json"
    if not _ID.match(interview_id) or not path.is_file():
        raise KeyError(interview_id)
    return path


def start(run_dir: Path, agent: str, tick: int, provider: str, model: str) -> dict:
    m = moment(run_dir, agent, tick)
    folder = run_dir / "interviews"
    folder.mkdir(exist_ok=True)
    base = f"{datetime.now():%Y%m%d-%H%M%S}-{agent}-t{tick}"
    name, n = base, 1
    while (folder / f"{name}.json").exists():
        n += 1
        name = f"{base}-{n}"
    record = {"id": name, "agent": agent, "tick": tick, "clock": m.clock, "provider": provider,
              "model": model, "started": datetime.now().isoformat(timespec="seconds"),
              "segments": _segments(run_dir), "turns": []}  # fmt: skip
    _write(folder / f"{name}.json", record)
    return record | {"summary": _summary(m), "stale": False}


def _summary(m: Moment) -> dict:
    return {"name": m.name, "title": m.title, "stress": m.stress, "mood": m.mood, "clock": m.clock}


def ask(run_dir: Path, interview_id: str, question: str, llm, model: str, embed: Embed | None
        ) -> dict:  # fmt: skip
    question = question.strip()[:MAX_QUESTION]
    if not question:
        raise ValueError("the question is empty")
    path = _path(run_dir, interview_id)
    with _lock(path):  # the conversation so far is part of the prompt: asks take turns
        record = json.loads(path.read_text("utf-8"))
        m = moment(run_dir, record["agent"], record["tick"])
        memories = recall(m, question, embed)
        system, text = prompt(m, memories, record["turns"], question)
        answer = llm.complete(system=system, prompt=text, model=model, temperature=0.7,
                              json_mode=False).strip()  # fmt: skip
        turn = {"q": question, "a": answer, "at": datetime.now().isoformat(timespec="seconds"),
                "model": model, "relevance": embed is not None,
                "retrieved": [{"id": r.id, "tick": r.created_tick, "text": r.description}
                              for r in memories]}  # fmt: skip
        record["turns"].append(turn)
        _write(path, record)
    return turn


def load(run_dir: Path, interview_id: str) -> dict:
    record = json.loads(_path(run_dir, interview_id).read_text("utf-8"))
    try:
        summary = _summary(moment(run_dir, record["agent"], record["tick"]))
    except (KeyError, ValueError):
        summary = None
    return record | {"stale": record.get("segments", 0) != _segments(run_dir), "summary": summary}


def listing(run_dir: Path, agent: str | None = None) -> list[dict]:
    folder = run_dir / "interviews"
    if not folder.is_dir():
        return []
    rows = []
    now = _segments(run_dir)
    for path in folder.glob("*.json"):
        try:
            r = json.loads(path.read_text("utf-8"))
        except ValueError:
            continue  # unreadable: one bad file must not hide the rest
        if agent is None or r["agent"] == agent:
            rows.append({"id": r["id"], "agent": r["agent"], "tick": r["tick"], "clock": r["clock"],
                         "questions": len(r["turns"]), "started": r["started"],
                         "stale": r.get("segments", 0) != now})  # fmt: skip
    return sorted(rows, key=lambda r: r["started"], reverse=True)
