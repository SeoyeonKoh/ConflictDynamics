import json
import os
import random
import sqlite3

from conflict_sim.experiment import run_scenario
from conflict_sim.llm import DemoBackend
from conflict_sim.tape import Tape


class Noisy(DemoBackend):
    """Demo replies with random urges and importances, and random vectors: two runs differ, so
    only a replayed tape can make a resumed run match the one it continues."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.random = random.Random(os.urandom(8))

    def complete(self, **request):
        reply = super().complete(**request)
        try:
            data = json.loads(reply)
        except ValueError:
            return reply
        if isinstance(data, dict):
            if "urge" in data:
                data["urge"] = self.random.random()
            if "importance" in data:
                data["importance"] = self.random.randint(1, 10)
        return json.dumps(data, ensure_ascii=False)

    def embed(self, texts):
        return [[self.random.uniform(-1, 1) for _ in range(8)] for _ in texts]


class Echo(DemoBackend):
    def complete(self, **request):
        return "reply:" + request["prompt"]


def test_tape_records_every_reply_and_vector_with_its_tick(tmp_path):
    tape = Tape(Echo(), tmp_path / "tape.sqlite")
    tape.tick = 3
    reply = tape.complete(system="s", prompt="p", model="demo", temperature=0, json_mode=True)
    tape.embed(["a", "b"])
    tape.close()
    db = sqlite3.connect(tmp_path / "tape.sqlite")
    assert db.execute("select tick, reply from completions").fetchall() == [(3, reply)]
    assert [r[0] for r in db.execute("select text from embeddings order by text")] == ["a", "b"]


def test_the_same_text_embeds_to_its_first_vector(tmp_path):
    tape = Tape(Noisy(), tmp_path / "tape.sqlite")
    assert tape.embed(["a"]) == tape.embed(["a"])


def test_experiment_run_writes_a_tape(tmp_path):
    run_scenario("s0_smoke", tmp_path / "run")
    assert (tmp_path / "run" / "tape.sqlite").is_file()


import threading  # noqa: E402

import pytest  # noqa: E402
from run_helpers import frames, restore_demo, rows, stop_when_tick  # noqa: E402

import conflict_sim.experiment as experiment  # noqa: E402

# p0_documents_ko (Demo, 2 days of 34 ticks): results_review runs ticks 26-27, so a stop at 26
# pauses with that meeting open; final_review runs 60-61 on day 2, after the day-2 standup.
OPEN_MEETING, DAY_TWO = 26, 60


def _stopped(tmp_path, monkeypatch, name, at, base=DemoBackend):
    run, stop = tmp_path / name, threading.Event()
    stop_when_tick(monkeypatch, stop, at, base=base)
    paused = run_scenario("p0_documents_ko", run, stop=stop)
    assert paused["run_status"] == "paused" and paused["tick"] > at  # first call at or after
    restore_demo(monkeypatch, base)
    return run


@pytest.mark.parametrize("stop_at", [OPEN_MEETING, DAY_TWO])
def test_resume_from_any_tick_replays_to_the_same_run(tmp_path, monkeypatch, stop_at):
    straight = tmp_path / "a"
    run_scenario("p0_documents_ko", straight)
    stopped = _stopped(tmp_path, monkeypatch, "b", stop_at)
    assert run_scenario("p0_documents_ko", stopped, resume=True)["run_status"] == "completed"
    assert rows(straight, "events.jsonl") == rows(stopped, "events.jsonl")
    strip = lambda rs: [r | {"run_id": None} if r["type"] == "hello" else r for r in rs]  # noqa: E731
    assert strip(frames(straight)) == strip(frames(stopped))


def test_replay_reuses_recorded_randomness_up_to_the_cut(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment, "DemoBackend", Noisy)
    run = _stopped(tmp_path, monkeypatch, "r", 20, base=Noisy)
    before = [e for e in rows(run, "events.jsonl") if e["tick"] <= 20]
    run_scenario("p0_documents_ko", run, resume=True)
    assert [e for e in rows(run, "events.jsonl") if e["tick"] <= 20] == before


def test_a_mid_tick_error_drops_that_tick_and_resumes(tmp_path, monkeypatch):
    from run_helpers import tick_of

    class Fails(DemoBackend):  # unusable replies at tick 15, retries too: the run pauses
        def complete(self, **request):
            return "not json" if tick_of(request) == 15 else super().complete(**request)

    monkeypatch.setattr(experiment, "DemoBackend", Fails)
    run = tmp_path / "e"
    assert run_scenario("p0_documents_ko", run)["run_status"] == "paused"
    assert json.loads((run / "paused.json").read_text())["tick"] == 15
    restore_demo(monkeypatch)
    assert run_scenario("p0_documents_ko", run, resume=True)["run_status"] == "completed"


def test_a_tape_that_does_not_match_pauses_instead_of_calling_the_api(tmp_path, monkeypatch):
    run = _stopped(tmp_path, monkeypatch, "m", 20)
    with sqlite3.connect(run / "tape.sqlite") as db:
        db.execute("update completions set key = 'x' where seq = (select max(seq) from completions"
                   " where tick = 10)")  # fmt: skip
    resumed = run_scenario("p0_documents_ko", run, resume=True)
    assert resumed["run_status"] == "paused" and "replay" in resumed["reason"].lower()


def test_a_stop_during_replay_keeps_the_tape(tmp_path, monkeypatch):
    run = _stopped(tmp_path, monkeypatch, "s", 30)
    cut = json.loads((run / "paused.json").read_text())["tick"]
    kept = sqlite3.connect(run / "tape.sqlite").execute(
        "select count(*) from completions where tick < ?", (cut,)).fetchone()
    stop = threading.Event()
    stop.set()  # asked to stop while the tape is still being replayed
    paused = run_scenario("p0_documents_ko", run, resume=True, stop=stop)
    assert paused["run_status"] == "paused"
    assert json.loads((run / "paused.json").read_text())["tick"] == cut
    assert sqlite3.connect(run / "tape.sqlite").execute(
        "select count(*) from completions where tick < ?", (cut,)).fetchone() == kept


def test_resuming_a_run_without_a_full_tape_twice_keeps_its_files(tmp_path, monkeypatch):
    """A run recorded before tapes (or resumed from a checkpoint) has no tape from tick 0: its
    second resume must not take the replay path and wipe what it has."""
    from run_helpers import tick_of

    from conflict_sim.llm import LLMError

    class Trips(DemoBackend):
        def complete(self, **request):
            if (tick_of(request) or 0) >= 40:
                raise LLMError("Run token budget reached; no further API calls")
            return super().complete(**request)

    monkeypatch.setattr(experiment, "DemoBackend", Trips)
    run = tmp_path / "old"
    run_scenario("p0_documents_ko", run)
    (run / "tape.sqlite").unlink()  # as if recorded before tapes existed
    run_scenario("p0_documents_ko", run, resume=True)  # checkpoint path, pauses again at 40
    assert json.loads((run / "paused.json").read_text())["tick"] == 40
    events = len(rows(run, "events.jsonl"))
    restore_demo(monkeypatch)
    assert run_scenario("p0_documents_ko", run, resume=True)["run_status"] == "completed"
    assert len(rows(run, "events.jsonl")) > events
    assert any((run / "checkpoints").glob("day-*.json"))


def test_a_replay_mismatch_restores_the_run_and_is_not_resumable_again(tmp_path, monkeypatch):
    from conflict_sim.runs import discover_company_runs

    run = _stopped(tmp_path, monkeypatch, "mm", 20)
    events = rows(run, "events.jsonl")
    with sqlite3.connect(run / "tape.sqlite") as db:
        db.execute("update completions set key = 'x' where seq = (select max(seq) from completions"
                   " where tick = 10)")  # fmt: skip
    assert run_scenario("p0_documents_ko", run, resume=True)["run_status"] == "paused"
    assert rows(run, "events.jsonl") == events  # what the run had is back
    row = next(r for r in discover_company_runs(tmp_path)[0] if r["run"] == "mm")
    assert row["resumable"] is False
    with pytest.raises(ValueError, match="replay"):
        run_scenario("p0_documents_ko", run, resume=True)
