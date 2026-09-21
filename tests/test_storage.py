import json
import sys

import numpy as np
import pytest

from conflict_sim.cga import extract_seeds, main
from conflict_sim.conversation import RunResult
from conflict_sim.models import AgentSpec, Config, Thread, Utterance
from conflict_sim.storage import load_seed, save_run, write_json, write_jsonl


def seed_rows():
    return [
        {"id": "root", "speaker": "A", "text": "First", "reply_to": None, "timestamp": 0},
        {"id": "reply", "speaker": "B", "text": "Second", "reply_to": "root", "timestamp": 0},
    ]


def test_failed_save_never_publishes_a_partial_corpus(tmp_path, monkeypatch):
    from conflict_sim import storage
    from conflict_sim.score import find_runs

    cfg = Config(
        n_agents=3, agents=[AgentSpec(name=name, persona="Uses citations.") for name in "ABC"]
    )
    result = RunResult(Thread([Utterance(**row) for row in seed_rows()]))
    original = storage.write_json

    def fail(path, data):
        assert find_runs(tmp_path) == []
        if path.name == "index.json":
            raise OSError("simulated disk failure")
        original(path, data)

    monkeypatch.setattr(storage, "write_json", fail)
    with pytest.raises(OSError, match="disk failure"):
        save_run(tmp_path / "run/corpus", result, cfg, {})
    assert not (tmp_path / "run/corpus").exists()
    assert not list((tmp_path / "run").iterdir())
    assert find_runs(tmp_path) == []


def test_seed_starts_a_session_from_one_or_more_utterances(tmp_path):
    path = tmp_path / "seed.json"
    path.write_text(json.dumps({"utterances": seed_rows()}))
    thread, data = load_seed(path)
    assert len(thread.utterances) == 2
    assert data["utterances"] == seed_rows()
    path.write_text(json.dumps({"utterances": seed_rows()[:1]}))
    assert len(load_seed(path)[0].utterances) == 1
    path.write_text(json.dumps({"utterances": []}))
    with pytest.raises(ValueError):
        load_seed(path)


def test_seed_timestamps_are_the_ticks_the_session_starts_from(tmp_path):
    rows = seed_rows()
    rows[1]["timestamp"] = 3
    path = tmp_path / "seed.json"
    path.write_text(json.dumps({"utterances": rows}))
    assert [u.timestamp for u in load_seed(path)[0].utterances] == [0, 3]


def test_convokit_export_roundtrips_and_keeps_config_and_decisions(tmp_path):
    cfg = Config(
        n_agents=3, agents=[AgentSpec(name=name, persona="Uses citations.") for name in "ABC"]
    )
    thread = Thread([Utterance(**row) for row in seed_rows()])
    thread.add(Utterance(id="post", speaker="C", text="A comment", reply_to="reply", timestamp=1))
    result = RunResult(
        thread,
        ticks=3,
        stop_reason="silence",
        seed_count=2,
        decisions=[
            {
                "tick": 1,
                "agent": "C",
                "urge": 0.6,
                "posted": True,
                "reflection": "Private impression, not a public comment.",
                "decision_source": "new",
                "decision_tick": 1,
            },
        ],
    )
    output = tmp_path / "run"
    save_run(output, result, cfg, {"source": "synthetic"})
    rows = [json.loads(line) for line in (output / "utterances.jsonl").read_text().splitlines()]
    assert all(row["conversation_id"] == "root" for row in rows)
    assert rows[2]["reply-to"] == "reply"
    restored = Thread(
        [
            Utterance(
                id=row["id"],
                speaker=row["speaker"],
                text=row["text"],
                reply_to=row["reply-to"],
                timestamp=row["timestamp"],
            )
            for row in rows
        ]
    )
    assert restored == thread

    assert set(json.loads((output / "speakers.json").read_text())) == {"A", "B", "C"}
    metadata = json.loads((output / "run.json").read_text())
    assert metadata["config"] == cfg.model_dump()
    assert metadata["stop_reason"] == "silence"
    assert metadata["generated_utterances"] == 1
    assert metadata["schema_version"] == 2
    assert metadata["prompt_version"] == "4"
    assert metadata["config"]["memory_mode"] == "summary"
    # The seed is recorded once, in its own file.
    assert "seed" not in metadata
    assert json.loads((output / "seed.json").read_text())["source"] == "synthetic"
    assert not (output / "config.yaml").exists()
    decisions = [json.loads(line) for line in (output / "decisions.jsonl").read_text().splitlines()]
    assert decisions == result.decisions
    for path in output.glob("*.json*"):
        if path.name != "decisions.jsonl":
            assert "Private impression" not in path.read_text()
    with pytest.raises(FileExistsError):
        save_run(output, result, cfg, {})
    assert restored == thread


@pytest.fixture
def cga_corpus(tmp_path):
    corpus = tmp_path / "cga"
    corpus.mkdir()
    conversations, utterances = {}, []
    for split in ("train", "val"):
        for side in (0, 1):
            cid = f"{split}-{side}"
            conversations[cid] = {
                "split": split,
                "pair_id": f"{split}-{1 - side}",
                "conversation_has_personal_attack": bool(side),
            }
            for index, text in enumerate(("Header", "First comment", "Reply", "Future attack")):
                utterances.append(
                    {
                        "conversation_id": cid,
                        "id": f"{cid}-{index}",
                        "speaker": "A" if index < 2 else "B",
                        "reply-to": f"{cid}-{index - 1}" if index else None,
                        "timestamp": 100 + index,
                        "text": text,
                        "meta": {"is_section_header": index == 0},
                    }
                )
    write_json(corpus / "conversations.json", conversations)
    write_jsonl(corpus / "utterances.jsonl", utterances)
    return corpus


@pytest.mark.parametrize("wrapped", [False, True])
def test_cga_preserves_pairs_and_links_without_leaking_future_comments(
    cga_corpus, tmp_path, wrapped
):
    if wrapped:
        path = cga_corpus / "conversations.json"
        write_json(
            path, {cid: {"meta": meta} for cid, meta in json.loads(path.read_text()).items()}
        )
    output = tmp_path / "seeds"
    report = extract_seeds(cga_corpus, output)
    assert not report["excluded"]
    assert len(report["pairs"]) == 1
    assert report["pairs"][0]["conversation_ids"] == ["train-0", "train-1"]
    outcomes = []
    for filename in report["pairs"][0]["seed_files"]:
        thread, data = load_seed(output / filename)
        root, reply = thread.utterances
        assert [root.text, reply.text] == ["First comment", "Reply"]
        assert root.reply_to is None and reply.reply_to == root.id
        assert root.timestamp == reply.timestamp == 0
        assert data["original_seed"][0]["reply-to"] == f"{data['conversation_id']}-0"
        assert data["original_seed"][0]["timestamp"] == 101
        assert "Future attack" not in (output / filename).read_text()
        outcomes.append(data["cga"]["conversation_has_personal_attack"])
    assert sorted(outcomes) == [False, True]
    assert json.loads((output / "manifest.json").read_text()) == report
    with pytest.raises(FileExistsError):
        extract_seeds(cga_corpus, output)
    assert json.loads((output / "manifest.json").read_text()) == report
    validation = extract_seeds(cga_corpus, tmp_path / "validation", "val")
    assert validation["pairs"][0]["conversation_ids"] == ["val-0", "val-1"]


@pytest.mark.parametrize("invalid", ["sibling", "missing_pair", "split_mismatch", "same_outcome"])
def test_cga_excludes_the_whole_pair_and_records_why(cga_corpus, tmp_path, invalid):
    path = cga_corpus / "conversations.json"
    conversations = json.loads(path.read_text())
    if invalid == "sibling":
        path = cga_corpus / "utterances.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[2]["reply-to"] = rows[0]["id"]
        write_jsonl(path, rows)
    else:
        if invalid == "missing_pair":
            del conversations["train-1"]
        elif invalid == "split_mismatch":
            conversations["train-1"]["split"] = "val"
        else:
            conversations["train-1"]["conversation_has_personal_attack"] = False
        write_json(path, conversations)
    output = tmp_path / "seeds"
    report = extract_seeds(cga_corpus, output)
    assert report["pairs"] == []
    assert report["excluded"][0]["conversation_ids"] == ["train-0", "train-1"]
    assert report["excluded"][0]["reasons"]
    assert [path.name for path in output.iterdir()] == ["manifest.json"]


def test_cga_keeps_file_order_for_equal_timestamps_and_allows_same_speaker(cga_corpus, tmp_path):
    path = cga_corpus / "utterances.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[2]["speaker"] = rows[1]["speaker"]
    rows[2]["timestamp"] = rows[1]["timestamp"]
    # Put a later comment before the first two in the source file.
    rows.insert(0, rows.pop(3))
    write_jsonl(path, rows)
    output = tmp_path / "seeds"
    report = extract_seeds(cga_corpus, output)
    thread, _ = load_seed(output / report["pairs"][0]["seed_files"][0])
    assert [u.id for u in thread.utterances] == ["train-0-1", "train-0-2"]
    assert [u.speaker for u in thread.utterances] == ["A", "A"]


def test_cga_invalid_source_leaves_no_output(cga_corpus, tmp_path):
    (cga_corpus / "utterances.jsonl").write_text("{broken json")
    output = tmp_path / "seeds"
    with pytest.raises(ValueError):
        extract_seeds(cga_corpus, output)
    assert not output.exists()


def test_cga_normalizes_missing_parent_nan_to_json_null(cga_corpus, tmp_path):
    path = cga_corpus / "utterances.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[1]["reply-to"] = float("nan")
    path.write_text("\n".join(json.dumps(row) for row in rows))
    output = tmp_path / "seeds"
    report = extract_seeds(cga_corpus, output)
    _, data = load_seed(output / report["pairs"][0]["seed_files"][0])
    assert data["original_seed"][0]["reply-to"] is None
    assert "NaN" not in (output / report["pairs"][0]["seed_files"][0]).read_text()


def test_cga_cli_reports_empty_selection_as_failure(cga_corpus, tmp_path, monkeypatch):
    output = tmp_path / "seeds"
    monkeypatch.setattr(
        sys, "argv", ["conflict-seeds", str(cga_corpus), str(output), "--split", "test"]
    )
    with pytest.raises(SystemExit, match="No eligible pairs"):
        main()
    assert json.loads((output / "manifest.json").read_text())["pairs"] == []


# --- company runs (A-6) ---


def company_cfg():
    return Config(n_agents=3, agents=[AgentSpec(name=name, persona="Works.") for name in "ABC"])


def test_run_writer_appends_events_and_memory_rows_once_per_tick(tmp_path):
    import sqlite3

    from conflict_sim.models import Event, MemoryRecord
    from conflict_sim.storage import RunWriter

    record = MemoryRecord(
        id="A:0", agent_id="A", type="observation", description="B looks angry.", created_tick=1,
        importance=3, valence=-0.9, arousal=0.9, self_relevance=0, subjects=["B"],
    )  # fmt: skip
    writer = RunWriter(tmp_path)
    writer.write_tick(
        [Event(tick=1, day=0, kind="action", actor="A", payload={"kind": "rest"})],
        [(record, [0.5, 0.5])],
        [{"agent_id": "A", "tick": 1, "query": "q", "ids": ["A:0"]}],
    )
    writer.write_tick([Event(tick=2, day=0, kind="task", actor="spec", payload={})], [], [])
    writer.close()
    lines = (tmp_path / "events.jsonl").read_text().splitlines()
    assert [json.loads(line)["kind"] for line in lines] == ["action", "task"]
    with sqlite3.connect(tmp_path / "memory.sqlite") as db:
        rows = db.execute(
            "select id, agent_id, subjects, length(embedding) from records"
        ).fetchall()
        assert rows == [("A:0", "A", '["B"]', 16)]  # two float64s
        assert db.execute("select agent_id, tick, ids from retrievals").fetchall() == [
            ("A", 1, '["A:0"]')
        ]


def test_company_corpus_holds_one_conversation_per_session(tmp_path):
    from conflict_sim.storage import save_company_run

    def post(id, speaker, text, reply_to, tick):
        return Utterance(id=id, speaker=speaker, text=text, reply_to=reply_to, timestamp=tick)

    def meta(sid, kind, place, start, end, public):
        return {"id": sid, "kind": kind, "participants": ["A", "B"], "place": place,
                "start": start, "end": end, "public": public}  # fmt: skip

    talk = Thread(
        [
            post("talk:17:A", "A", "Hi", None, 17),
            post("talk:17:A:sim:1", "B", "Hey", "talk:17:A", 17),
        ]
    )
    dm = Thread([post("dm:A:B:0", "B", "Update?", None, 2)])
    threads = {"talk:17:A": talk, "dm:A:B:0": dm}
    sessions = {
        "talk:17:A": meta("talk:17:A", "talk", "cafeteria", 17, 19, True),
        "dm:A:B:0": meta("dm:A:B:0", "message", None, 2, None, False),
    }
    output = tmp_path / "corpus"
    save_company_run(output, company_cfg(), threads, sessions, ticks=32, days=1)
    rows = [json.loads(line) for line in (output / "utterances.jsonl").read_text().splitlines()]
    assert [(r["id"], r["conversation_id"]) for r in rows] == [
        ("dm:A:B:0", "dm:A:B:0"), ("talk:17:A", "talk:17:A"), ("talk:17:A:sim:1", "talk:17:A"),
    ]  # fmt: skip
    conversations = json.loads((output / "conversations.json").read_text())
    assert (
        conversations["talk:17:A"]["meta"]["kind"] == "talk"
        and conversations["dm:A:B:0"]["meta"]["end"] is None
    )
    meta = json.loads((output / "run.json").read_text())
    assert (meta["stop_reason"], meta["ticks"], meta["days"], meta["generated_utterances"]) == (
        "max_days",
        32,
        1,
        3,
    )
    assert not (output / "seed.json").exists() and not (output / "decisions.jsonl").exists()


def test_checkpoints_are_written_read_and_run_files_truncated_to_them(tmp_path):
    import sqlite3

    from conflict_sim.models import Event, MemoryRecord
    from conflict_sim.storage import (
        RunWriter,
        read_latest_checkpoint,
        read_memory,
        truncate_run,
    )

    def record(n, tick):
        return MemoryRecord(
            id=f"A:{n}", agent_id="A", type="action", description=f"r{n}", created_tick=tick,
            importance=3, valence=0, arousal=0, self_relevance=0,
        )  # fmt: skip

    writer = RunWriter(tmp_path)
    for tick in (30, 31, 32, 33):
        writer.write_tick(
            [Event(tick=tick, day=tick // 32, kind="task", actor="spec", payload={})],
            [(record(tick, tick), np.array([0.1, 0.2]) if tick % 2 else [0.1, 0.2])],
            [{"agent_id": "A", "tick": tick, "query": "q", "ids": []}],
        )
        if tick == 31:
            writer.write_checkpoint(0, {"tick": 32, "day": 0})
    writer.close()
    assert read_latest_checkpoint(tmp_path) == (0, {"tick": 32, "day": 0})
    assert (tmp_path / "checkpoints/day-0.json").is_file()

    truncate_run(tmp_path, keep_below_tick=32)
    lines = (tmp_path / "events.jsonl").read_text().splitlines()
    assert [json.loads(line)["tick"] for line in lines] == [30, 31]
    memory = read_memory(tmp_path)
    records, vectors = memory["A"]
    assert [r.created_tick for r in records] == [30, 31]
    assert isinstance(vectors["A:31"], np.ndarray) and vectors["A:31"].tolist() == [0.1, 0.2]
    with sqlite3.connect(tmp_path / "memory.sqlite") as db:
        assert db.execute("select max(tick) from retrievals").fetchone() == (31,)
