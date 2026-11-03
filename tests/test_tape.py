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
