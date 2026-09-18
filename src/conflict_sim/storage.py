"""Seed input and ConvoKit corpus output. No scoring happens here."""

import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from .agent import PROMPT_VERSION
from .conversation import RunResult
from .models import Config, Thread, Utterance


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


def save_run(
    output: Path, result: RunResult, cfg: Config, seed_data: dict, usage: dict | None = None
) -> None:
    """Publish the corpus only after every file has been written successfully."""
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".corpus-", dir=output.parent) as temporary:
        staging = Path(temporary)
        _write_corpus(staging, result, cfg, seed_data, usage)
        if output.exists():
            raise FileExistsError(f"Output already exists: {output}")
        staging.rename(output)


def _write_corpus(output: Path, result: RunResult, cfg: Config, seed_data: dict, usage) -> None:
    root = result.thread.utterances[0].id
    rows = []
    for utterance in result.thread.utterances:
        row = utterance.model_dump()
        # ConvoKit's Python API uses reply_to; its on-disk loader uses reply-to.
        row["reply-to"] = row.pop("reply_to")
        row.update(conversation_id=root, meta={}, vectors=[])
        rows.append(row)
    write_jsonl(output / "utterances.jsonl", rows)
    speakers = {agent.name for agent in cfg.agents} | {u.speaker for u in result.thread.utterances}
    write_json(
        output / "speakers.json", {name: {"meta": {}, "vectors": []} for name in sorted(speakers)}
    )
    write_json(output / "conversations.json", {root: {"meta": {}, "vectors": []}})
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
    write_jsonl(output / "decisions.jsonl", result.decisions)
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
            "ticks": result.ticks,
            "stop_reason": result.stop_reason,
            "generated_utterances": len(result.thread.utterances) - 2,
            "llm_usage": usage,
        },
    )
