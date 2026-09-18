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
        self.run_dir = run_dir
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

    def write_checkpoint(self, day: int, data: dict) -> None:
        directory = self.run_dir / "checkpoints"
        directory.mkdir(exist_ok=True)
        write_json(directory / f"day-{day}.json", data)

    def close(self) -> None:
        self.events.close()
        self.db.close()


def read_latest_checkpoint(run_dir: Path) -> tuple[int, dict]:
    files = sorted((run_dir / "checkpoints").glob("day-*.json"), key=lambda p: int(p.stem[4:]))
    if not files:
        raise ValueError(f"No checkpoint to resume from in {run_dir}")
    return int(files[-1].stem[4:]), json.loads(files[-1].read_text(encoding="utf-8"))


def truncate_run(run_dir: Path, *, keep_below_tick: int) -> None:
    """Drop the rows a paused run wrote after its last checkpoint."""
    path = run_dir / "events.jsonl"
    kept = [line for line in path.read_text(encoding="utf-8").splitlines()
            if json.loads(line)["tick"] < keep_below_tick]  # fmt: skip
    path.write_text("".join(line + "\n" for line in kept), encoding="utf-8")
    with sqlite3.connect(run_dir / "memory.sqlite") as db:
        db.execute("delete from records where created_tick >= ?", (keep_below_tick,))
        db.execute("delete from retrievals where tick >= ?", (keep_below_tick,))


def read_memory(run_dir: Path) -> dict[str, tuple[list[MemoryRecord], dict[str, list[float]]]]:
    """Every agent's records and vectors, in creation order, for `Loop.restore`."""
    memory: dict[str, tuple[list[MemoryRecord], dict[str, list[float]]]] = {}
    columns = (
        "id, agent_id, type, description, created_tick, importance, valence, arousal, "
        "self_relevance, subjects, session_id, evidence, embedding"
    )
    with sqlite3.connect(run_dir / "memory.sqlite") as db:
        rows = db.execute(f"select {columns} from records order by rowid").fetchall()
    for row in rows:
        fields = dict(zip(columns.split(", "), row))
        blob = fields.pop("embedding")
        fields["subjects"] = json.loads(fields["subjects"])
        fields["evidence"] = json.loads(fields["evidence"])
        record = MemoryRecord(**fields)
        agent, id_ = record.agent_id, record.id
        records, vectors = memory.setdefault(agent, ([], {}))
        records.append(record)
        if blob is not None:
            vectors[id_] = list(struct.unpack(f"{len(blob) // 8}d", blob))
    return memory


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
    wiki = {"decisions.jsonl": result.decisions, "seed.json": seed_data}
    _publish(output, cfg, conversations, meta, usage, wiki)


def save_company_run(
    output: Path,
    cfg: Config,
    threads: dict[str, Thread],
    sessions: dict[str, dict],
    *,
    ticks: int,
    days: int,
    usage: dict | None = None,
) -> None:
    """Publish a company run: every session is one conversation, ordered by id.

    Decisions live in `events.jsonl` next to the corpus, not in a `decisions.jsonl` (plan §1-11).
    """
    conversations = [(sid, threads[sid], sessions[sid]) for sid in sorted(threads)]
    meta = {
        "ticks": ticks,
        "days": days,
        "stop_reason": "max_days",
        "generated_utterances": sum(len(t.utterances) for t in threads.values()),
    }
    _publish(output, cfg, conversations, meta, usage, {})


def _publish(output, cfg, conversations, meta, usage, extra_files: dict) -> None:
    """Publish the corpus only after every file has been written successfully."""
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".corpus-", dir=output.parent) as temporary:
        staging = Path(temporary)
        _write_corpus(staging, cfg, conversations, meta, usage)
        for name, data in extra_files.items():
            (write_jsonl if name.endswith(".jsonl") else write_json)(staging / name, data)
        if output.exists():
            raise FileExistsError(f"Output already exists: {output}")
        staging.rename(output)


def _write_corpus(
    output: Path, cfg: Config, conversations: list[tuple[str, Thread, dict]], meta: dict, usage
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
