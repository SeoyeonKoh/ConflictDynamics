import pytest

from conflict_sim.score import derive_metrics, find_runs, order_series


def series(*probabilities):
    return [
        {"id": f"u{index}", "speaker": "A", "timestamp": index, "p": value}
        for index, value in enumerate(probabilities)
    ]


def test_peak_and_steepest_rise_are_located_by_utterance():
    metrics = derive_metrics(series(0.1, 0.2, 0.9, 0.4), threshold=0.7)
    assert metrics["max_p"] == 0.9
    assert metrics["max_p_at"]["id"] == "u2"
    assert metrics["max_dp"] == pytest.approx(0.7)
    assert metrics["max_dp_at"]["id"] == "u2"


def test_forecast_horizon_is_the_first_crossing_not_the_peak():
    metrics = derive_metrics(series(0.1, 0.75, 0.6, 0.95), threshold=0.7)
    assert metrics["escalated"] is True
    assert metrics["forecast_horizon"]["index"] == 1
    assert metrics["max_p_at"]["index"] == 3


def test_a_run_that_never_crosses_reports_no_horizon():
    metrics = derive_metrics(series(0.35, 0.12, 0.05, 0.06), threshold=0.5)
    assert metrics["escalated"] is False
    assert metrics["forecast_horizon"] is None
    assert metrics["final_p"] == 0.06


def test_a_falling_series_reports_no_positive_rise():
    metrics = derive_metrics(series(0.4, 0.3, 0.2), threshold=0.5)
    assert metrics["max_dp"] < 0


def test_a_single_utterance_has_no_rise_to_report():
    metrics = derive_metrics(series(0.42), threshold=0.5)
    assert metrics["max_p"] == 0.42
    assert metrics["max_dp"] == 0.0


def test_empty_series_is_rejected():
    with pytest.raises(ValueError):
        derive_metrics([], threshold=0.5)


def test_runs_are_found_by_their_corpus(tmp_path):
    for name in ("a", "nested/b"):
        corpus = tmp_path / name / "corpus"
        corpus.mkdir(parents=True)
        (corpus / "utterances.jsonl").write_text("{}\n")
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
    assert derive_metrics(rows, threshold=0.5)["max_dp"] > 0
    assert derive_metrics(order_series(rows, corpus_order), threshold=0.5)["max_dp"] < 0


def test_rows_missing_from_the_corpus_sort_to_the_end():
    rows = [
        {"id": "stray", "speaker": "A", "timestamp": 9, "p": 0.1},
        {"id": "known", "speaker": "A", "timestamp": 0, "p": 0.2},
    ]
    assert [row["id"] for row in order_series(rows, ["known"])] == ["known", "stray"]
