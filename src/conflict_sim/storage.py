"""Seed input, ConvoKit corpus output, and the per-tick run files. No scoring happens here.

`memory.sqlite`'s schema lives here and nowhere else; `agent/memory.py` never opens the file.
"""

import json
import sqlite3
import struct
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from .agent import PROMPT_VERSION
from .conversation import RunResult
from .models import Config, Event, MemoryRecord, Thread, Utterance

MEMORY_SCHEMA = """
create table if not exists records (
    id text primary key, agent_id text not null, type text not null, description text not null,
    created_tick integer not null, importance real not null, valence real not null,
    arousal real not null, self_relevance real not null, subjects text not null,
    session_id text, evidence text not null, embedding blob
);
create table if not exists retrievals (
    agent_id text not null, tick integer not null, query text not null, ids text not null
);
"""


def load_seed(path: Path) -> tuple[Thread, dict]:
    """Return the validated thread and the raw seed document, read once."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return parse_seed(data), data


def parse_seed(data: dict) -> Thread:
    """Validate the same seed shape for files and the settings editor.

    A session starts from its first utterance, so one is enough; timestamps are the ticks the
    seed posts were made at and the session continues from the last of them.
    """
    if not isinstance(data, dict) or not isinstance(data.get("utterances"), list):
        raise ValueError("Seed must be a JSON object with an utterances list")
    if not data["utterances"]:
        raise ValueError("Seed must contain at least the first utterance")
    try:
        return Thread([Utterance.model_validate(row) for row in data["utterances"]])
    except TypeError as exc:
        raise ValueError(f"Invalid seed fields: {exc}") from exc


def write_json(path: Path, data) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def write_jsonl(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


class RunWriter:
    """The loop's single writer: `events.jsonl` and `memory.sqlite`, committed once per tick."""

    def __init__(self, run_dir: Path):
        run_dir.mkdir(parents=True, exist_ok=True)
        self.events = (run_dir / "events.jsonl").open("a", encoding="utf-8")
        self.db = sqlite3.connect(run_dir / "memory.sqlite", timeout=5.0)
        self.db.execute("pragma journal_mode=wal")  # insurance only; there is one writer
        self.db.executescript(MEMORY_SCHEMA)

    def write_tick(
        self,
        events: list[Event],
        memory_rows: list[tuple[MemoryRecord, list[float] | None]],
        retrieval_rows: list[dict],
    ) -> None:
        for event in events:
            self.events.write(json.dumps(event.model_dump(), ensure_ascii=False) + "\n")
        self.events.flush()
        self.db.executemany(
            "insert into records values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    r.id, r.agent_id, r.type, r.description, r.created_tick, r.importance,
                    r.valence, r.arousal, r.self_relevance, json.dumps(r.subjects), r.session_id,
                    json.dumps(r.evidence), _pack(vector),
                )
                for r, vector in memory_rows
            ],
        )  # fmt: skip
        self.db.executemany(
            "insert into retrievals values (?,?,?,?)",
            [
                (row["agent_id"], row["tick"], row["query"], json.dumps(row["ids"]))
                for row in retrieval_rows
            ],
        )
        self.db.commit()

    def close(self) -> None:
        self.events.close()
        self.db.close()


def _pack(vector: list[float] | None) -> bytes | None:
    return None if vector is None else struct.pack(f"{len(vector)}d", *vector)


def save_run(
    output: Path, result: RunResult, cfg: Config, seed_data: dict, usage: dict | None = None
) -> None:
    """Publish the wiki demo corpus: one conversation stepped from the seed."""
    root = result.thread.utterances[0].id
    conversations = [(root, result.thread, {})]
    meta = {
        "ticks": result.ticks,
        "stop_reason": result.stop_reason,
        "generated_utterances": len(result.thread.utterances) - result.seed_count,
    }
    _publish(output, cfg, conversations, result.decisions, seed_data, meta, usage)


def save_company_run(
    output: Path,
    cfg: Config,
    threads: dict[str, Thread],
    sessions: dict[str, dict],
    *,
    decisions: list[dict],
    ticks: int,
    days: int,
    usage: dict | None = None,
) -> None:
    """Publish a company run: every session is one conversation, ordered by id."""
    conversations = [(sid, threads[sid], sessions[sid]) for sid in sorted(threads)]
    meta = {
        "ticks": ticks,
        "days": days,
        "stop_reason": "max_days",
        "generated_utterances": sum(len(t.utterances) for t in threads.values()),
    }
    _publish(output, cfg, conversations, decisions, {}, meta, usage)


def _publish(output, cfg, conversations, decisions, seed_data, meta, usage) -> None:
    """Publish the corpus only after every file has been written successfully."""
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".corpus-", dir=output.parent) as temporary:
        staging = Path(temporary)
        _write_corpus(staging, cfg, conversations, decisions, seed_data, meta, usage)
        if output.exists():
            raise FileExistsError(f"Output already exists: {output}")
        staging.rename(output)


def _write_corpus(
    output: Path,
    cfg: Config,
    conversations: list[tuple[str, Thread, dict]],
    decisions: list[dict],
    seed_data: dict,
    meta: dict,
    usage,
) -> None:
    rows = []
    for conversation_id, thread, _ in conversations:
        for utterance in thread.utterances:
            row = utterance.model_dump()
            # ConvoKit's Python API uses reply_to; its on-disk loader uses reply-to.
            row["reply-to"] = row.pop("reply_to")
            row.update(conversation_id=conversation_id, meta={}, vectors=[])
            rows.append(row)
    write_jsonl(output / "utterances.jsonl", rows)
    speakers = {agent.name for agent in cfg.agents} | {row["speaker"] for row in rows}
    write_json(
        output / "speakers.json", {name: {"meta": {}, "vectors": []} for name in sorted(speakers)}
    )
    write_json(
        output / "conversations.json",
        {cid: {"meta": info, "vectors": []} for cid, _, info in conversations},
    )
    write_json(output / "corpus.json", {})
    write_json(
        output / "index.json",
        {
            "utterances-index": {},
            "speakers-index": {},
            "conversations-index": {},
            "overall-index": {},
            "version": 1,
            "vectors": [],
        },
    )
    write_jsonl(output / "decisions.jsonl", decisions)
    write_json(output / "seed.json", seed_data)
    write_json(
        output / "run.json",
        {
            "schema_version": 2,
            "status": "completed",
            "simulator_version": "0.1.0",
            "prompt_version": PROMPT_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "config": cfg.model_dump(),
            "llm_usage": usage,
        }
        | meta,
    )
