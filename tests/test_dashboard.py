import json
import time
from pathlib import Path

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


def test_nested_run_addition_and_file_edits_invalidate_caches(tmp_path):
    from streamlit import cache_data

    from conflict_sim.dashboard import _cached_run, _cached_runs, _stamp_of

    cache_data.clear()
    first = write_corpus(tmp_path, "nested/one")
    root_mtime = tmp_path.stat().st_mtime_ns

    def read_list():
        return _cached_runs(str(tmp_path), _stamp_of(tmp_path.rglob("corpus/run.json")))

    assert len(read_list()[0]) == 1
    write_corpus(tmp_path, "nested/two")
    assert tmp_path.stat().st_mtime_ns == root_mtime
    assert len(read_list()[0]) == 2
    files = [first / name for name in ("run.json", "utterances.jsonl", "decisions.jsonl")]
    old = _cached_run(str(first), _stamp_of(files))
    (first / "decisions.jsonl").write_text(json.dumps({"agent": "C", "reflection": "Changed"}))
    fresh = _cached_run(str(first), _stamp_of(files))
    assert old["decisions"] != fresh["decisions"]
    (tmp_path / "nested/two/corpus/run.json").unlink()
    assert len(read_list()[0]) == 1


def test_measurements_appear_when_scored_externally_without_reload(tmp_path, monkeypatch):
    from streamlit import cache_data
    from streamlit.testing.v1 import AppTest

    from conflict_sim.score import derive_metrics

    cache_data.clear()
    corpus = write_corpus(tmp_path / "runs", "one")
    monkeypatch.chdir(tmp_path)
    dashboard = Path(__file__).resolve().parents[1] / "src/conflict_sim/dashboard.py"
    app = AppTest.from_file(str(dashboard)).run()
    app.radio[0].set_value("Saved runs").run()
    assert not app.exception
    assert any("No scores.json" in info.value for info in app.info)
    rows = [
        dict(id=id_, speaker=name, timestamp=tick, p=p)
        for id_, name, tick, p in [("root", "A", 0, 0.1), ("r1", "B", 0, 0.2), ("r2", "C", 1, 0.8)]
    ]
    (corpus.parent / "scores.json").write_text(
        json.dumps({"schema_version": 2, "series": rows, "metrics": derive_metrics(rows, 0.5)})
    )
    app.run()
    assert not app.exception
    assert any("index 2, tick 1" in item.value for item in app.markdown)
    share = next(frame.value for frame in app.dataframe if "Share" in frame.value.columns)
    assert share.loc["C", "Share"] == 1
    assert list(share.index) == ["C"]  # Seed speakers alone contribute no generated posts.
    (corpus.parent / "scores.json").write_text("{broken")
    app.run()
    assert not app.exception
    assert any("Could not read scores.json" in warning.value for warning in app.warning)


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


def test_agent_stance_is_displayed_and_escaped_without_changing_public_text():
    from conflict_sim.dashboard import agent_label

    agents = [{"name": "Alex", "stance": "출처 확인 <우선>", "persona": "Long persona."}]
    body = talk_page_html(talk_utterances(), "run", "rule", agents)
    assert "Alex · 출처 확인 &lt;우선&gt;" in body
    assert "<p>First post</p>" in body
    assert (
        agent_label({"name": "A", "persona": "Requests sources. Speaks bluntly."})
        == "A · Requests sources"
    )


def test_replay_controls_hide_future_reflections_and_stop_at_the_end(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    from conflict_sim import dashboard

    corpus = write_corpus(tmp_path, "one")
    first = {"agent": "C", "tick": 1, "reflection": "Earlier view", "urge": 0.6, "posted": False}
    second = first | {"tick": 2, "reflection": "Later view", "posted": True}
    (corpus / "decisions.jsonl").write_text("\n".join(json.dumps(row) for row in (first, second)))
    clock = [0.0]
    monkeypatch.setattr(dashboard, "monotonic", lambda: clock[0])

    def view(path):
        from pathlib import Path

        from conflict_sim.dashboard import load_run, replay_view

        replay_view(load_run(Path(path)), path)

    app = AppTest.from_function(view, args=(str(corpus),)).run()
    assert not app.exception
    assert app.session_state["replay_tick"] == 0
    assert not app.text
    next(b for b in app.button if b.label == "다음 tick").click().run()
    assert not app.exception
    assert [item.value for item in app.text] == ["Earlier view"]
    next(b for b in app.button if b.label == "재생").click().run()
    assert app.session_state["replay_playing"]
    next(b for b in app.button if b.label == "일시정지").click().run()
    clock[0] = 10
    app.run()
    assert app.session_state["replay_tick"] == 1
    next(b for b in app.button if b.label == "재생").click().run()
    clock[0] = 12
    app.run()
    assert not app.exception
    assert app.session_state["replay_tick"] == 2
    assert not app.session_state["replay_playing"]
    assert [item.value for item in app.text] == ["Later view"]
    app.button(key="replay_reset").click().run()
    assert app.session_state["replay_tick"] == 0
    assert not app.text


def test_scoring_toggle_starts_once_stops_and_displays_failure(tmp_path, monkeypatch):
    from streamlit import cache_data
    from streamlit.testing.v1 import AppTest

    cache_data.clear()
    write_corpus(tmp_path / "runs", "one")
    monkeypatch.chdir(tmp_path)
    processes = []

    class Process:
        returncode = None

        def __init__(self, args, **kwargs):
            self.args = args
            processes.append(self)

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = -15

        def wait(self, **kwargs):
            return self.returncode

    monkeypatch.setattr("subprocess.Popen", Process)
    script = Path(__file__).resolve().parents[1] / "src/conflict_sim/dashboard.py"
    app = AppTest.from_file(str(script)).run()
    app.radio[0].set_value("Saved runs").run()
    assert not processes  # Off by default; no scoring from simply opening the page.
    app.toggle(key="auto_scoring").set_value(True).run()
    assert not app.exception
    app.run()
    assert len(processes) == 1
    assert "conflict_sim.score" in processes[0].args
    app.toggle(key="auto_scoring").set_value(False).run()
    assert processes[0].returncode == -15
    app.toggle(key="auto_scoring").set_value(True).run()
    assert len(processes) == 2
    processes[1].returncode = 1
    (tmp_path / "runs/one/score.log").write_text("CRAFT dependency unavailable")
    app.run()
    assert not app.exception
    assert any("채점에 실패" in error.value for error in app.error)
    assert any("CRAFT dependency unavailable" in code.value for code in app.code)
    app.run()
    assert len(processes) == 2  # Failure does not create a retry loop.


@pytest.mark.parametrize("with_reflections", [False, True])
def test_dashboard_opens_old_logs_and_displays_new_and_reused_reflections(
    tmp_path, monkeypatch, with_reflections
):
    from streamlit import cache_data
    from streamlit.testing.v1 import AppTest

    cache_data.clear()  # AppTest instances share Streamlit's process-wide cache.
    corpus = write_corpus(tmp_path / "runs", "example")
    if with_reflections:
        first = {
            "tick": 1,
            "agent": "C",
            "urge": 0.8,
            "posted": False,
            "reflection": "I want a better source, but have not spoken yet.",
            "decision_source": "new",
            "decision_tick": 1,
        }
        events = [
            first,
            first | {"tick": 2, "posted": True, "decision_source": "retry"},
            first | {"agent": "A", "urge": 0.2, "reflection": "I am content to wait."},
        ]
        (corpus / "decisions.jsonl").write_text(
            "\n".join(json.dumps(event) for event in events) + "\n"
        )
    dashboard = Path(__file__).resolve().parents[1] / "src/conflict_sim/dashboard.py"
    monkeypatch.chdir(tmp_path)
    app = AppTest.from_file(str(dashboard)).run()
    app.radio[0].set_value("Saved runs").run()
    assert not app.exception
    if with_reflections:
        assert app.metric[3].value == "0.5"  # The retry is not another urge observation.
        app.selectbox[1].select("C").run()
        assert app.text[0].value == first["reflection"]
        assert any("New reflection" in item.value for item in app.caption)
        app.selectbox[2].select(2).run()
        assert not app.exception
        assert app.text[0].value == first["reflection"]
        assert any(
            "Reused reflection" in item.value and "tick 1" in item.value for item in app.caption
        )
    else:
        assert app.metric[3].value == "0.6"
        assert app.info[0].value == "This run recorded no reflections."


@pytest.mark.parametrize("stop_early", [False, True])
def test_live_ui_starts_once_streams_reflections_and_completes_or_stops(
    tmp_path, monkeypatch, stop_early
):
    from streamlit import cache_data
    from streamlit.testing.v1 import AppTest

    cache_data.clear()
    monkeypatch.chdir(tmp_path)
    dashboard = Path(__file__).resolve().parents[1] / "src/conflict_sim/dashboard.py"
    app = AppTest.from_file(str(dashboard)).run()
    assert not app.exception
    assert not list(tmp_path.rglob("console.log"))  # Loading the UI never starts a run.
    if not stop_early:
        app.selectbox(key="live_preset").set_value("wording").run()
        assert any("Alex · 조사 결과를 제목에 분명히 반영" in item.value for item in app.text)
    app.sidebar.text_input[0].set_value("runs, with spaces").run()
    app.number_input[0].set_value(12 if stop_early else 1)
    app.selectbox(key="live_memory").set_value("none")
    next(button for button in app.button if button.label == "Start simulation").click().run()
    process = app.session_state["live_process"]
    directory = app.session_state["live_directory"]
    try:
        assert app.number_input[0].value == (12 if stop_early else 1)
        assert app.selectbox(key="live_memory").value == "none"
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            time.sleep(0.05)
            app.run()
            assert not app.exception
            assert app.session_state["live_process"].pid == process.pid
            progress_path = directory / "live.json"
            events = (
                json.loads(progress_path.read_text()).get("decisions", [])
                if progress_path.exists()
                else []
            )
            if stop_early and any(event.get("reflection") for event in events):
                assert process.poll() is None
                assert next(b for b in app.button if b.label == "Start simulation").disabled
                next(b for b in app.button if b.label == "Stop simulation").click().run()
                break
            if not stop_early and process.poll() is not None:
                app.run()
                break
        assert process.poll() is not None
        assert not app.exception
        assert app.text  # Reflections appear even before the first public reply.
        assert not next(b for b in app.button if b.label == "Start simulation").disabled
        assert len(list(tmp_path.rglob("console.log"))) == 1
        progress = json.loads((directory / "live.json").read_text())
        assert progress["config"]["memory_mode"] == "none"
        assert progress["utterances"][0]["id"] == ("example-root" if stop_early else "wording-root")
        assert any(
            event.get("reflection") in [item.value for item in app.text]
            for event in progress["decisions"]
            if event.get("reflection")
        )
        assert progress["status"] == ("stopped" if stop_early else "completed")
        if stop_early:
            assert not (directory / "corpus").exists()
            assert app.warning
        else:
            assert (directory / "corpus/run.json").is_file()
            assert app.success
            app.radio[0].set_value("Saved runs").run()
            assert not app.exception
            assert app.selectbox[0].options
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
