import json
import shutil

import pytest

from conflict_sim.experiment import run_scenario
from conflict_sim.interview import (
    DemoInterviewer,
    ask,
    listing,
    load,
    moment,
    recall,
    run_embedder,
    start,
)


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


def test_an_interview_is_saved_and_leaves_the_run_alone(run):
    files = lambda: {p: p.read_bytes() for p in run.rglob("*")  # noqa: E731
                     if p.is_file() and "interviews" not in p.parts}  # fmt: skip
    before = files()
    iv = start(run, "HDS-001", 12, "demo", "demo")
    assert iv["summary"]["name"] and iv["summary"]["clock"] == "1일차 12:00"
    embed = run_embedder(run, run / "no.env")
    turn = ask(run, iv["id"], "지금 뭐 하고 있어요?", DemoInterviewer(), "demo", embed)
    assert turn["a"] and turn["retrieved"] and all(r["tick"] <= 12 for r in turn["retrieved"])
    assert files() == before
    assert load(run, iv["id"])["turns"][0]["q"] == "지금 뭐 하고 있어요?"
    assert listing(run, "HDS-001")[0]["questions"] == 1


def test_an_empty_question_is_refused(run):
    iv = start(run, "HDS-001", 3, "demo", "demo")
    with pytest.raises(ValueError):
        ask(run, iv["id"], "   ", DemoInterviewer(), "demo", None)


def test_a_bad_interview_id_is_a_key_error(run):
    with pytest.raises(KeyError):
        load(run, "../manifest")


def test_a_rebuilt_run_marks_its_interviews_stale(run, tmp_path):
    copy = tmp_path / "copy"
    shutil.copytree(run, copy)
    iv = start(copy, "HDS-001", 3, "demo", "demo")
    manifest = json.loads((copy / "manifest.json").read_text())
    segments = manifest.get("token_usage_segments", []) + [None]
    (copy / "manifest.json").write_text(json.dumps(manifest | {"token_usage_segments": segments}))
    assert load(copy, iv["id"])["stale"] is True
