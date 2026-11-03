import pytest

from conflict_sim.experiment import run_scenario
from conflict_sim.interview import moment, recall, run_embedder


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    path = tmp_path_factory.mktemp("iv") / "r"
    run_scenario("p0_documents_ko", path, max_days=1)
    return path


def test_a_moment_knows_only_what_happened_by_then(run):
    early, late = moment(run, "HDS-001", 5), moment(run, "HDS-001", 30)
    assert early.memory.records and all(r.created_tick <= 5 for r in early.memory.records)
    assert len(early.memory.records) < len(late.memory.records)
    assert early.name and early.persona and early.clock == "1일차 10:15"


def test_recall_never_reaches_past_the_moment(run):
    m = moment(run, "HDS-001", 12)
    got = recall(m, "왜 쉬었어요?", run_embedder(run, run / "no.env"))
    assert got and all(r.created_tick <= 12 for r in got)


def test_vectors_of_another_size_fall_back_to_recency(run):
    m = moment(run, "HDS-001", 12)
    assert recall(m, "q", lambda texts: [[0.1] * 1536 for _ in texts])


def test_moments_before_and_after_the_run_are_empty_or_full(run):
    assert moment(run, "HDS-001", -1).memory.records == []
    end = len(moment(run, "HDS-001", 33).memory.records)
    assert len(moment(run, "HDS-001", 10_000).memory.records) == end


def test_an_unknown_agent_is_a_key_error(run):
    with pytest.raises(KeyError):
        moment(run, "NOBODY", 3)
