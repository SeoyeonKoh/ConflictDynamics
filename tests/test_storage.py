import json
import sys

import pytest

from conflict_sim.cga import extract_seeds, main
from conflict_sim.engine import RunResult
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


def test_seed_requires_exactly_two_initial_utterances(tmp_path):
    path = tmp_path / "seed.json"
    path.write_text(json.dumps({"utterances": seed_rows()}))
    thread, data = load_seed(path)
    assert len(thread.utterances) == 2
    assert data["utterances"] == seed_rows()
    path.write_text(json.dumps({"utterances": seed_rows()[:1]}))
    with pytest.raises(ValueError):
        load_seed(path)


def test_seed_must_use_simulation_tick_zero(tmp_path):
    rows = seed_rows()
    rows[1]["timestamp"] = 1514764800
    path = tmp_path / "seed.json"
    path.write_text(json.dumps({"utterances": rows}))
    with pytest.raises(ValueError, match="tick 0"):
        load_seed(path)


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
    assert metadata["prompt_version"] == "2"
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
