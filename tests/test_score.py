import json
import os
from pathlib import Path

import pytest

from conflict_sim import score
from conflict_sim.score import derive_metrics, find_runs, order_series


def series(*probabilities):
    return [
        {"id": f"u{index}", "speaker": "A", "timestamp": index, "p": value}
        for index, value in enumerate(probabilities)
    ]


def finished_run(directory, rows):
    corpus = directory / "corpus"
    corpus.mkdir(parents=True)
    for name in score.CORPUS_FILES:
        (corpus / name).write_text("{}\n")
    (corpus / "run.json").write_text(json.dumps({"stop_reason": "max_ticks"}))
    (corpus / "utterances.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    return corpus


def test_peak_and_steepest_rise_are_located_by_utterance():
    metrics = derive_metrics(series(0.1, 0.2, 0.9, 0.4), threshold=0.7)
    assert metrics["max_p"] == 0.9
    assert metrics["max_p_at"]["id"] == "u2"
    assert metrics["max_delta_p"] == pytest.approx(0.7)
    assert metrics["max_delta_p_at"]["id"] == "u2"


def test_first_threshold_crossing_is_not_the_peak():
    metrics = derive_metrics(series(0.1, 0.75, 0.6, 0.95), threshold=0.7)
    assert metrics["threshold_exceeded"] is True
    assert metrics["first_threshold_crossing"] == {"index": 1, "id": "u1", "tick": 1}
    assert metrics["max_p_at"]["index"] == 3


def test_a_run_that_never_crosses_reports_no_crossing():
    metrics = derive_metrics(series(0.35, 0.12, 0.05, 0.06), threshold=0.5)
    assert metrics["threshold_exceeded"] is False
    assert metrics["first_threshold_crossing"] is None
    assert metrics["final_p"] == 0.06


def test_a_falling_series_reports_no_positive_rise():
    metrics = derive_metrics(series(0.4, 0.3, 0.2), threshold=0.5)
    assert metrics["max_delta_p"] < 0


def test_a_single_utterance_has_no_rise_to_report():
    metrics = derive_metrics(series(0.42), threshold=0.5)
    assert metrics["max_p"] == 0.42
    assert metrics["max_delta_p"] == 0.0


@pytest.mark.parametrize("probability, exceeded", [(0.49, False), (0.5, False), (0.51, True)])
def test_threshold_comparison_matches_craft(probability, exceeded):
    metrics = derive_metrics(series(0.1, probability), threshold=0.5)
    assert metrics["threshold_exceeded"] is exceeded
    assert metrics["first_threshold_crossing"] == (
        {"index": 1, "id": "u1", "tick": 1} if exceeded else None
    )


def test_the_first_utterance_can_already_exceed_the_threshold():
    metrics = derive_metrics(series(0.75, 0.9), threshold=0.7)
    assert metrics["first_threshold_crossing"] == {"index": 0, "id": "u0", "tick": 0}


def test_probability_changes_are_per_utterance_not_per_tick():
    rows = series(0.1, 0.3, 0.2)
    for row, tick in zip(rows, [0, 0, 5]):
        row["timestamp"] = tick
    metrics = derive_metrics(rows, threshold=0.5)
    assert metrics["max_delta_p"] == pytest.approx(0.2)
    assert metrics["max_delta_p_at"] == {"index": 1, "id": "u1", "tick": 0}


def test_empty_series_is_rejected():
    with pytest.raises(ValueError):
        derive_metrics([], threshold=0.5)


def test_runs_are_found_by_their_corpus(tmp_path):
    for name in ("a", "nested/b"):
        finished_run(tmp_path / name, series(0.1, 0.2))
    partial = tmp_path / "partial/corpus"
    partial.mkdir(parents=True)
    (partial / "utterances.jsonl").write_text("{}\n")
    (tmp_path / "no-corpus").mkdir()
    assert find_runs(tmp_path) == [tmp_path / "a", tmp_path / "nested/b"]


def test_series_follows_corpus_order_not_lexicographic_id_order():
    scrambled = [
        {"id": "root:sim:10", "speaker": "A", "timestamp": 2, "p": 0.4},
        {"id": "example-reply", "speaker": "B", "timestamp": 0, "p": 0.2},
        {"id": "root:sim:2", "speaker": "C", "timestamp": 1, "p": 0.3},
        {"id": "example-root", "speaker": "A", "timestamp": 0, "p": 0.9},
    ]
    corpus_order = ["example-root", "example-reply", "root:sim:2", "root:sim:10"]
    assert [row["id"] for row in order_series(scrambled, corpus_order)] == corpus_order


def test_ordering_decides_whether_the_first_step_is_a_rise_or_a_fall():
    rows = [
        {"id": "example-reply", "speaker": "B", "timestamp": 0, "p": 0.2275},
        {"id": "example-root", "speaker": "A", "timestamp": 0, "p": 0.3562},
    ]
    corpus_order = ["example-root", "example-reply"]
    assert derive_metrics(rows, threshold=0.5)["max_delta_p"] > 0
    assert derive_metrics(order_series(rows, corpus_order), threshold=0.5)["max_delta_p"] < 0


def test_rows_missing_from_the_corpus_are_rejected():
    rows = [
        {"id": "stray", "speaker": "A", "timestamp": 9, "p": 0.1},
        {"id": "known", "speaker": "A", "timestamp": 0, "p": 0.2},
    ]
    with pytest.raises(ValueError, match="match the corpus"):
        order_series(rows, ["known"])


@pytest.mark.parametrize(
    "rows",
    [series(0.1), series(0.1, None), series(0.1, float("nan")), [series(0.1)[0], series(0.1)[0]]],
)
def test_missing_duplicate_and_invalid_forecasts_do_not_overwrite_scores(
    tmp_path, monkeypatch, rows
):
    finished_run(tmp_path, series(0.1, 0.2))
    previous = tmp_path / "scores.json"
    previous.write_text("previous successful score\n")
    monkeypatch.setattr(
        score, "forecast_corpus", lambda *a, **k: {"series": rows, "threshold": 0.5, "model": {}}
    )
    with pytest.raises(ValueError):
        score.score_run(tmp_path)
    assert previous.read_text() == "previous successful score\n"


def test_cli_reports_failures_but_continues_with_remaining_runs(tmp_path, monkeypatch, capsys):
    good = tmp_path / "good"
    rows = series(0.1, 0.2)
    finished_run(good, rows)
    monkeypatch.setattr(
        score, "forecast_corpus", lambda *a, **k: {"series": rows, "threshold": 0.5, "model": {}}
    )
    monkeypatch.setattr(
        "sys.argv", ["conflict-score", str(tmp_path / "missing"), str(good), str(good)]
    )
    with pytest.raises(SystemExit) as error:
        score.main()
    assert error.value.code == 1
    captured = capsys.readouterr()
    assert "failed" in captured.err
    assert "Scored 1 run(s); failed 1" in captured.out
    assert (good / "scores.json").is_file()


def test_score_file_and_cli_use_the_same_metric_definitions(tmp_path, monkeypatch, capsys):
    rows = series(0.1, 0.5)
    finished_run(tmp_path, rows)
    monkeypatch.setattr(
        score,
        "forecast_corpus",
        lambda *args, **kwargs: {
            "series": rows,
            "threshold": 0.5,
            "model": {"forecaster": "CRAFT"},
        },
    )
    monkeypatch.setattr("sys.argv", ["conflict-score", str(tmp_path)])

    score.main()

    report = json.loads((tmp_path / "scores.json").read_text())
    assert report["schema_version"] == 2
    assert report["series"] == rows
    assert report["metrics"]["threshold_exceeded"] is False
    assert report["metrics"]["first_threshold_crossing"] is None
    assert not {"escalated", "forecast_horizon", "max_dp", "max_dp_at"} & report["metrics"].keys()
    output = capsys.readouterr().out
    assert "max delta p/utterance=+0.4000" in output
    assert "first threshold crossing=none" in output
    assert "p > 0.5" in output


@pytest.mark.parametrize("terminal", ["completed", "stopped", "failed"])
def test_live_scoring_reuses_model_and_ignores_reflection_only_updates(
    tmp_path, monkeypatch, terminal
):
    rows = [
        dict(row, text=f"Comment {index}", **{"reply-to": None if index == 0 else "u0"})
        for index, row in enumerate(series(0.1, 0.2, 0.3))
    ]
    # The public progress file contains no forecast values.
    public = [{key: value for key, value in row.items() if key != "p"} for row in rows]
    if terminal == "completed":
        finished_run(tmp_path, public)
    states = [
        {"status": "running", "utterances": public[:2]},
        {"status": "running", "utterances": public[:2], "decisions": [{"reflection": "PRIVATE"}]},
        {"status": terminal, "utterances": public},
    ]
    path = tmp_path / "live.json"
    path.write_text(json.dumps(states.pop(0)))
    monkeypatch.setattr(score, "sleep", lambda _: path.write_text(json.dumps(states.pop(0))))
    loads, prefixes = [], []
    model = object()
    monkeypatch.setattr(score, "load_forecaster", lambda *a: loads.append(a) or model)

    def infer(utterances, forecaster, *args):
        assert forecaster is model
        prefixes.append(utterances)
        return {"series": rows[: len(utterances)], "threshold": 0.5, "model": {}}

    monkeypatch.setattr(score, "forecast_public", infer)
    score.watch_run(tmp_path)
    assert len(loads) == 1
    assert prefixes == [public[:2], public]
    assert json.loads((tmp_path / "live-scores.json").read_text())["series"] == rows
    assert (tmp_path / "scores.json").exists() is (terminal == "completed")
    assert score.find_runs(tmp_path) == ([tmp_path] if terminal == "completed" else [])


def test_live_scoring_failure_preserves_previous_score(tmp_path, monkeypatch):
    path = tmp_path / "live-scores.json"
    path.write_text("previous result")
    (tmp_path / "live.json").write_text(json.dumps({"utterances": [{"id": "u0"}]}))
    monkeypatch.setattr(score, "load_forecaster", lambda *a: None)
    monkeypatch.setattr(score, "forecast_public", lambda *a: {"series": series(None)})
    with pytest.raises(ValueError, match="finite forecast"):
        score.watch_run(tmp_path)
    assert path.read_text() == "previous result"
    assert not (tmp_path / "scores.json").exists()


def test_live_cli_rejects_a_missing_snapshot_without_waiting(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["conflict-score", "--live", str(tmp_path)])
    with pytest.raises(SystemExit, match="No live.json"):
        score.main()


@pytest.mark.craft
@pytest.mark.skipif(
    os.environ.get("CONFLICT_CRAFT_INTEGRATION") != "1",
    reason="Set CONFLICT_CRAFT_INTEGRATION=1 for real local CRAFT inference",
)
def test_real_craft_scores_every_public_utterance_in_order(tmp_path, monkeypatch):
    import importlib

    import torch  # noqa: F401  ConvoKit exports CRAFT only after torch is loaded.
    from convokit import Forecaster  # noqa: F401  Follow the production import order.

    from conflict_sim.conversation import RunResult
    from conflict_sim.models import AgentSpec, Config, Thread, Utterance
    from conflict_sim.storage import save_run

    weights = Path.home() / ".convokit/saved-models/craft-wiki-finetuned"
    assert all(
        (weights / name).is_file()
        for name in ("craft_full.tar", "index2word.json", "word2index.json")
    ), "Cache CRAFT weights first"
    craft = importlib.import_module("convokit.forecaster.CRAFTModel")

    def cached_download(name, **kwargs):
        assert name == score.DEFAULT_WEIGHTS
        return str(weights)

    # Only asset lookup is redirected. Tokenization, model inference and saving are real.
    monkeypatch.setattr(craft, "download", cached_download)
    seen_contexts = []
    process_context = craft.processContext

    def observe_context(voc, context, label):
        seen_contexts.append([utterance.id for utterance in context.context])
        return process_context(voc, context, label)

    monkeypatch.setattr(craft, "processContext", observe_context)
    rows = [
        Utterance(
            id="z-root",
            speaker="A",
            text="The company report describes an environmental benefit.",
            reply_to=None,
            timestamp=0,
        ),
        Utterance(
            id="a-reply",
            speaker="B",
            text="Could we find an independent source first?",
            reply_to="z-root",
            timestamp=0,
        ),
        Utterance(
            id="z-root:sim:10",
            speaker="C",
            text="Please compare the cited passages before editing.",
            reply_to="a-reply",
            timestamp=1,
        ),
        Utterance(
            id="z-root:sim:2",
            speaker="A",
            text="We can attribute this claim directly to the company.",
            reply_to="z-root",
            timestamp=1,
        ),
    ]
    cfg = Config(
        n_agents=3, agents=[AgentSpec(name=name, persona="Uses citations.") for name in "ABC"]
    )
    save_run(
        tmp_path / "corpus",
        RunResult(Thread(rows), ticks=1),
        cfg,
        {"utterances": [u.model_dump() for u in rows[:2]]},
    )
    report = score.score_run(tmp_path)
    assert seen_contexts == [[row.id for row in rows[:end]] for end in range(1, len(rows) + 1)]
    assert [row["id"] for row in report["series"]] == [row.id for row in rows]
    assert len(report["series"]) == 4
    assert all(0 <= row["p"] <= 1 for row in report["series"])
    assert report["model"]["forecaster"] == "CRAFT"
    assert json.loads((tmp_path / "scores.json").read_text()) == report
    public = [dict(u.model_dump(exclude={"reply_to"}), **{"reply-to": u.reply_to}) for u in rows]
    live_path = tmp_path / "live.json"
    live_path.write_text(json.dumps({"status": "running", "utterances": public[:2]}))
    monkeypatch.setattr(
        score,
        "sleep",
        lambda _: live_path.write_text(json.dumps({"status": "completed", "utterances": public})),
    )
    seen_contexts.clear()
    score.watch_run(tmp_path)
    live_report = json.loads((tmp_path / "live-scores.json").read_text())
    assert seen_contexts == [[u.id for u in rows[:end]] for end in (1, 2, 1, 2, 3, 4)]
    assert [row["p"] for row in live_report["series"]] == pytest.approx(
        [row["p"] for row in report["series"]]
    )
    assert json.loads((tmp_path / "scores.json").read_text())["series"] == live_report["series"]
