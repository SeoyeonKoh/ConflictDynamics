"""Every LLM reply and vector a run received, so the run can be replayed to any tick.

The engine is deterministic given its seed and its replies, so this tape stands in for a state
saved at every tick: resuming re-runs the run from tick 0 with the tape answering, then goes on
with the real backend (docs/superpowers/specs/2026-11-03-viz-main-menu-design.md, 5.3).
"""

import hashlib
import json
import sqlite3
import threading
from pathlib import Path

import numpy as np

from .llm import LLMError

SCHEMA = """
create table if not exists completions (
  seq integer primary key, tick integer not null, key text not null, reply text not null);
create index if not exists completions_key on completions (key, seq);
create table if not exists embeddings (
  text text primary key, tick integer not null, vector blob not null);
"""


class ReplayMismatch(LLMError):
    """The engine asked for something the tape never recorded before the cut."""


def request_key(request: dict) -> str:
    return hashlib.sha256(json.dumps(request, sort_keys=True, default=str).encode()).hexdigest()


class Tape:
    """Wraps the run's outermost backend: records every completion and embedding. A text keeps
    the vector it was first given, so parallel judgements embedding one text agree."""

    def __init__(self, inner, path: Path, *, replay_until: int | None = None):
        self.inner = inner
        self.tick = -1  # set by the run at the start of every tick; -1 before tick 0
        self.replay_until = replay_until
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript(SCHEMA)

    def complete(self, **request) -> str:
        reply = self.inner.complete(**request)
        with self.lock:
            self.db.execute(
                "insert into completions (tick, key, reply) values (?, ?, ?)",
                (self.tick, request_key(request), reply),
            )
            self.db.commit()
        return reply

    def embed(self, texts: list[str]) -> list[list[float]]:
        with self.lock:
            known = {text: self._vector(text) for text in texts}
        missing = list(dict.fromkeys(t for t, v in known.items() if v is None))
        if missing:
            for text, vector in zip(missing, self.inner.embed(missing)):
                known[text] = list(vector)
            with self.lock:
                self.db.executemany(
                    "insert or ignore into embeddings values (?, ?, ?)",
                    [(t, self.tick, np.asarray(known[t], dtype=np.float64).tobytes())
                     for t in missing],
                )  # fmt: skip
                self.db.commit()
                known |= {t: self._vector(t) for t in missing}  # first write wins
        return [known[text] for text in texts]

    def _vector(self, text: str) -> list[float] | None:
        row = self.db.execute("select vector from embeddings where text = ?", (text,)).fetchone()
        return None if row is None else np.frombuffer(row[0], dtype=np.float64).tolist()

    def close(self) -> None:
        with self.lock:
            self.db.close()
        if hasattr(self.inner, "close"):
            self.inner.close()
