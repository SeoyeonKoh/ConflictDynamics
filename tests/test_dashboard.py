import json

import pytest

pytest.importorskip("streamlit")

from conflict_sim.dashboard import (  # noqa: E402
    MAX_INDENT,
    discover_runs,
    load_run,
    reply_depth,
    talk_page_html,
)


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


def talk_utterances():
    return [
        {"id": "root", "speaker": "Alex", "text": "First post", "reply-to": None, "timestamp": 0},
        {"id": "r1", "speaker": "Blake", "text": "A reply", "reply-to": "root", "timestamp": 0},
        {"id": "r2", "speaker": "Casey", "text": "Deeper", "reply-to": "r1", "timestamp": 3},
    ]


def test_talk_page_indents_each_comment_by_its_reply_depth():
    html = talk_page_html(talk_utterances(), "llm-rr6", "round_robin")
    assert 'data-depth="0"' in html
    assert 'data-depth="1"' in html
    assert 'data-depth="2"' in html


def test_talk_page_escapes_comment_text_instead_of_rendering_it():
    hostile = talk_utterances()
    hostile[0]["text"] = "<script>alert(1)</script> & *not italic*"
    hostile[0]["speaker"] = "<b>Alex</b>"
    html = talk_page_html(hostile, "run", "sub")
    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; *not italic*" in html
    assert "<b>Alex</b>" not in html


def test_talk_page_marks_the_seed_and_signs_generated_comments_with_their_tick():
    html = talk_page_html(talk_utterances(), "llm-rr6", "round_robin")
    assert html.count(">seed<") == 2
    assert "tick 3" in html
    assert "llm-rr6" in html and "round_robin" in html


def test_talk_page_keeps_blank_lines_as_separate_paragraphs():
    rows = talk_utterances()
    rows[0]["text"] = "One.\n\nTwo."
    html = talk_page_html(rows, "run", "sub")
    assert "<p>One.</p>" in html and "<p>Two.</p>" in html


def test_talk_page_stops_indenting_past_the_outdent_limit():
    rows = [{"id": "u0", "speaker": "A", "text": "root", "reply-to": None, "timestamp": 0}]
    for index in range(1, 10):
        rows.append(
            {
                "id": f"u{index}",
                "speaker": "A",
                "text": "reply",
                "reply-to": f"u{index - 1}",
                "timestamp": index,
            }
        )
    html = talk_page_html(rows, "deep", "sub")
    widest = f"margin-left:{MAX_INDENT * 1.6:g}em"
    assert widest in html
    assert f"margin-left:{(MAX_INDENT + 1) * 1.6:g}em" not in html
    assert 'data-depth="9"' in html
    assert "outdented from depth 9" in html
