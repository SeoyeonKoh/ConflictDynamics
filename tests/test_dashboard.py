import json

import pytest

pytest.importorskip("streamlit")

from conflict_sim.dashboard import discover_runs, load_run, reply_depth  # noqa: E402


def write_corpus(
    root, name, *, ticks=2, generated=1, rule="bidding", created="2026-09-09T00:00:00"
):
    corpus = root / name / "corpus"
    corpus.mkdir(parents=True)
    (corpus / "run.json").write_text(
        json.dumps(
            {
                "created_at": created,
                "ticks": ticks,
                "stop_reason": "silence",
                "generated_utterances": generated,
                "config": {
                    "rule": rule,
                    "n_agents": 3,
                    "random_seed": 7,
                    "backend": "demo",
                    "model_speak": None,
                },
            }
        )
    )
    rows = [
        {"id": "root", "speaker": "A", "text": "First", "reply-to": None, "timestamp": 0},
        {"id": "r1", "speaker": "B", "text": "Second", "reply-to": "root", "timestamp": 0},
        {"id": "r2", "speaker": "C", "text": "Third", "reply-to": "r1", "timestamp": 1},
    ]
    (corpus / "utterances.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    (corpus / "decisions.jsonl").write_text(
        json.dumps({"tick": 1, "agent": "C", "urge": 0.6, "posted": True, "reason": "posted"})
        + "\n"
    )
    return corpus


def test_runs_are_found_at_any_depth_and_sorted_newest_first(tmp_path):
    write_corpus(tmp_path, "2026-09-01/10-00-00", created="2026-09-01T10:00:00")
    write_corpus(tmp_path, "llm-smoke", created="2026-09-09T23:00:00", rule="round_robin")
    write_corpus(tmp_path, "multirun/2026-09-05/0", created="2026-09-05T12:00:00")
    rows, broken = discover_runs(tmp_path)
    assert broken == []
    assert [row["run"] for row in rows] == [
        "llm-smoke",
        "multirun/2026-09-05/0",
        "2026-09-01/10-00-00",
    ]
    assert rows[0]["rule"] == "round_robin"
    assert rows[0]["ticks"] == 2


def test_a_broken_run_is_reported_without_hiding_the_others(tmp_path):
    write_corpus(tmp_path, "good")
    broken_corpus = tmp_path / "bad" / "corpus"
    broken_corpus.mkdir(parents=True)
    (broken_corpus / "run.json").write_text("{not json")
    rows, broken = discover_runs(tmp_path)
    assert [row["run"] for row in rows] == ["good"]
    assert broken == ["bad"]


def test_missing_root_is_empty_rather_than_an_error(tmp_path):
    assert discover_runs(tmp_path / "absent") == ([], [])


def test_run_is_loaded_with_its_utterances_and_decisions(tmp_path):
    corpus = write_corpus(tmp_path, "one")
    run = load_run(corpus)
    assert run["meta"]["stop_reason"] == "silence"
    assert [u["id"] for u in run["utterances"]] == ["root", "r1", "r2"]
    assert run["decisions"][0]["agent"] == "C"


def test_reply_depth_follows_the_reply_chain(tmp_path):
    run = load_run(write_corpus(tmp_path, "one"))
    assert reply_depth(run["utterances"]) == {"root": 0, "r1": 1, "r2": 2}


def test_reply_depth_survives_a_dangling_or_cyclic_parent():
    utterances = [
        {"id": "root", "reply-to": None},
        {"id": "orphan", "reply-to": "missing"},
        {"id": "a", "reply-to": "b"},
        {"id": "b", "reply-to": "a"},
    ]
    depth = reply_depth(utterances)
    assert depth["root"] == 0
    assert depth["orphan"] == 1
    assert all(isinstance(value, int) for value in depth.values())
