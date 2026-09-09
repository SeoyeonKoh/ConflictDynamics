import json

import pytest

from conflict_sim.engine import RunResult
from conflict_sim.models import AgentSpec, Config, Thread, Utterance
from conflict_sim.storage import load_seed, save_run


def seed_rows():
    return [
        {"id": "root", "speaker": "A", "text": "First", "reply_to": None, "timestamp": 0},
        {"id": "reply", "speaker": "B", "text": "Second", "reply_to": "root", "timestamp": 0},
    ]


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
            {"tick": 1, "agent": "C", "urge": 0.6, "posted": True},
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
    # The seed is recorded once, in its own file.
    assert "seed" not in metadata
    assert json.loads((output / "seed.json").read_text())["source"] == "synthetic"
    assert not (output / "config.yaml").exists()
    decisions = [json.loads(line) for line in (output / "decisions.jsonl").read_text().splitlines()]
    assert decisions == result.decisions
    with pytest.raises(FileExistsError):
        save_run(output, result, cfg, {})
    assert restored == thread
