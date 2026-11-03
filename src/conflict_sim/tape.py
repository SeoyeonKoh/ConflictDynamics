"""Every LLM reply and vector a run received, so the run can be replayed to any tick.

The engine is deterministic given its seed and its replies, so this tape stands in for a state
saved at every tick: resuming re-runs the run from tick 0 with the tape answering, then goes on
with the real backend (docs/superpowers/specs/2026-11-03-viz-main-menu-design.md, 5.3).
"""

import hashlib
import json
import sqlite3
import threading
from collections import defaultdict, deque
from pathlib import Path

import numpy as np

from .llm import LLMError

SCHEMA = """
create table if not exists completions (
  seq integer primary key, tick integer not null, key text not null, reply text not null);
create index if not exists completions_key on completions (key, seq);
create table if not exists embeddings (
  text text primary key, tick integer not null, vector blob not null);
create table if not exists meta (key text primary key, value text not null);
"""


class ReplayMismatch(LLMError):
    """The engine asked for something the tape never recorded before the cut."""


def request_key(request: dict) -> str:
    return hashlib.sha256(json.dumps(request, sort_keys=True, default=str).encode()).hexdigest()


class Tape:
    """Wraps the run's outermost backend: records every completion and embedding. A text keeps
    the vector it was first given, so parallel judgements embedding one text agree."""

    def __init__(self, inner, path: Path, *, replay_until: int | None = None, fresh: bool = False):
        self.inner = inner
        self.tick = -1  # set by the run at the start of every tick; -1 before tick 0
        self.replay_until = replay_until
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript(SCHEMA)
        if fresh:  # recorded from the run's first call: only such a tape can replay the run
            self.db.execute("insert or replace into meta values ('from_start', '1')")
            self.db.commit()
        self.recorded: dict[str, deque[str]] = defaultdict(deque)  # replies to replay, by key
        if replay_until is not None:
            for key, reply in self.db.execute("select key, reply from completions order by seq"):
                self.recorded[key].append(reply)

    @property
    def replaying(self) -> bool:
        return self.replay_until is not None and self.tick < self.replay_until

    def complete(self, **request) -> str:
        key = request_key(request)
        if self.replaying:
            with self.lock:
                if self.recorded[key]:
                    return self.recorded[key].popleft()
            raise ReplayMismatch(f"replay: no recorded reply for a call at tick {self.tick}")
        reply = self.inner.complete(**request)
        with self.lock:
            self.db.execute(
                "insert into completions (tick, key, reply) values (?, ?, ?)",
                (self.tick, key, reply),
            )
            self.db.commit()
        return reply

    def embed(self, texts: list[str]) -> list[list[float]]:
        with self.lock:
            known = {text: self._vector(text) for text in texts}
        missing = list(dict.fromkeys(t for t, v in known.items() if v is None))
        if missing and self.replaying:
            raise ReplayMismatch(f"replay: no recorded vector for a text at tick {self.tick}")
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


def truncate_tape(path: Path, *, keep_below_tick: int) -> None:
    """Drop what a stopped tick received: that tick runs again from its start."""
    with sqlite3.connect(path) as db:
        db.execute("delete from completions where tick >= ?", (keep_below_tick,))
        db.execute("delete from embeddings where tick >= ?", (keep_below_tick,))


def full_tape(path: Path) -> bool:
    """A tape that holds the run from its first call, so replaying it rebuilds the run."""
    if not path.is_file():
        return False
    with sqlite3.connect(path) as db:
        try:
            row = db.execute("select value from meta where key = 'from_start'").fetchone()
        except sqlite3.OperationalError:
            return False
    return row is not None
