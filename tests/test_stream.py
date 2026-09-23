import json
import random
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_loop import Recorder, company_config
from websockets.sync.client import connect

from conflict_sim.agent import Agent
from conflict_sim.cli import _company_run
from conflict_sim.environment import Environment
from conflict_sim.frames import Frames
from conflict_sim.llm import DemoBackend
from conflict_sim.loop import Loop
from conflict_sim.models import Event
from conflict_sim.stream import Stream


def receive(socket, kind):
    while True:
        msg = json.loads(socket.recv(timeout=3))
        if msg["type"] == kind:
            return msg


def test_company_live_day_can_start_paused_step_and_finish(tmp_path, monkeypatch):
    from conflict_sim import cli

    ready = threading.Event()
    ports = []

    class ObservedStream(Stream):
        def start(self, port=0):
            port = super().start(port)
            ports.append(port)
            ready.set()
            return port

    monkeypatch.setattr(cli, "Stream", ObservedStream)
    cfg = company_config(live="true", stream_paused="true", stream_port=0, stream_speed=100)
    with ThreadPoolExecutor(1) as pool:
        run = pool.submit(_company_run, cfg, DemoBackend(), tmp_path, tmp_path / "corpus", None)
        assert ready.wait(5)
        with connect(f"ws://127.0.0.1:{ports[0]}", proxy=None) as socket:
            receive(socket, "hello")
            assert receive(socket, "status")["state"] == "paused"
            try:
                socket.send('{"type":"control","cmd":"step"}')
                assert receive(socket, "frame")["tick"] == 0
                socket.send('{"type":"control","cmd":"inspect","agent":"Alex"}')
                assert receive(socket, "inspect")["tick"] == 0
            finally:
                socket.send('{"type":"control","cmd":"resume"}')
            frames = []
            while True:
                message = json.loads(socket.recv(timeout=5))
                if message["type"] == "frame":
                    frames.append(message["tick"])
                if message["type"] == "status" and message["state"] == "completed":
                    break
            assert frames == list(range(1, 32))
        assert "32 ticks" in run.result(timeout=5)


def test_demo_journal_contains_complete_day_and_world_deltas(tmp_path):
    cfg = company_config()
    _company_run(cfg, DemoBackend(), tmp_path, tmp_path / "corpus", None)
    messages = [json.loads(line) for line in (tmp_path / "frames.jsonl").read_text().splitlines()]
    hello, *rest = messages
    assert hello["type"] == "hello" and hello["version"] == 1
    assert len(hello["agents"]) == 6
    frames = [m for m in rest if m["type"] == "frame"]
    assert [f["tick"] for f in frames] == list(range(32))
    assert all(len(f["agents"]) == 6 for f in frames)
    assert any(a.get("bubble") for f in frames for a in f["agents"])
    tasks = {t["id"]: t for t in hello["tasks"]}
    for frame in frames:
        tasks.update((t["id"], t) for t in frame["tasks"])
        for a in frame["agents"]:
            assert 0 <= a["x"] <= 960 and 0 <= a["y"] <= 640
    checkpoint = json.loads((tmp_path / "checkpoints/day-0.json").read_text())
    assert {k: v["progress"] for k, v in tasks.items()} == {
        k: v["progress"] for k, v in checkpoint["env"]["tasks"].items()
    }
    assert messages[-1]["state"] == "completed"
    assert all("reflection" not in a for f in frames for a in f["agents"])
    panels = [json.loads(line) for line in (tmp_path / "inspect.jsonl").read_text().splitlines()]
    assert {p["agent"] for p in panels if p["tick"] == 0} == {a["id"] for a in hello["agents"]}
    latest = {}
    for p in panels:  # replay rule: an agent's panel at tick t is its last line with tick <= t
        latest[p["agent"]] = p
    final = checkpoint["agents"]
    assert {n: p["state"]["stress"] for n, p in latest.items()} == {
        n: a["state"]["stress"] for n, a in final.items()
    }
    assert not any(m["type"] == "inspect" for m in messages)


def test_inspect_journal_writes_changes_only_and_rolls_back_at_resume(tmp_path):
    path = tmp_path / "frames.jsonl"

    def panel(tick, stress):
        message = {"type": "inspect", "agent": "Alex", "tick": tick, "state": {"stress": stress}}
        return {"Alex": message}

    stream = Stream(path, {"type": "hello"})
    for tick, stress in [(0, 0.1), (1, 0.1), (2, 0.4), (3, 0.4), (4, 0.9)]:
        stream.publish([], panel(tick, stress))
    stream.close()
    rows = [json.loads(line) for line in (tmp_path / "inspect.jsonl").read_text().splitlines()]
    assert [r["tick"] for r in rows] == [0, 2, 4]
    resumed = Stream(path, {"type": "hello"}, resume_tick=3)
    resumed.publish([], panel(3, 0.4))  # same as the kept tick-2 line: not repeated
    resumed.publish([], panel(3, 0.5))
    resumed.close()
    rows = [json.loads(line) for line in (tmp_path / "inspect.jsonl").read_text().splitlines()]
    assert [(r["tick"], r["state"]["stress"]) for r in rows] == [(0, 0.1), (2, 0.4), (3, 0.5)]


def test_frames_preserve_outcome_direction_and_inspection_without_engine_mutation():
    cfg = company_config()
    llm = DemoBackend()
    loop = Loop(
        cfg,
        [Agent(s, cfg, llm) for s in cfg.agents],
        Environment(cfg.environment, cfg.agents),
        llm,
        random.Random(42),
        Recorder(),
    )
    try:
        frames = Frames(cfg, "test")
        before = loop.checkpoint()
        events = [
            Event(
                tick=0,
                day=0,
                kind="outcome",
                actor="Alex",
                target="Erin",
                payload={"a": "Alex", "b": "Erin", "relation_delta": -0.2},
            )
        ]
        messages, inspections = frames.capture(
            loop.viewer_snapshot(), events, [{"agent_id": "Alex", "ids": ["memory-1"]}]
        )
        assert messages[-1]["actors"] == ["Alex", "Erin"]
        assert messages[-1]["payload"]["relation_delta"] == -0.2
        assert inspections["Alex"]["retrieved"] == ["memory-1"]
        assert loop.checkpoint() == before
        again, _ = frames.capture(loop.viewer_snapshot(), [], [])
        assert again[0]["tasks"] == [] and again[0]["resources"] == []
    finally:
        loop.close()


def test_websocket_history_controls_inspect_and_terminal_status(tmp_path):
    stream = Stream(tmp_path / "frames.jsonl", {"type": "hello"}, paused=True, delay=0)
    stream.publish(
        [{"type": "frame", "tick": 0}], {"Alex": {"type": "inspect", "agent": "Alex", "tick": 0}}
    )
    port = stream.start(0)
    first_tick, second_tick = threading.Event(), threading.Event()

    def engine():
        stream.before_tick()
        first_tick.set()
        stream.before_tick()
        second_tick.set()

    worker = threading.Thread(target=engine)
    worker.start()
    try:
        with connect(f"ws://127.0.0.1:{port}", proxy=None) as socket:
            assert receive(socket, "hello") == {"type": "hello"}
            assert receive(socket, "frame")["tick"] == 0
            assert not first_tick.wait(0.05)
            socket.send(json.dumps({"type": "control", "cmd": "inspect", "agent": "Alex"}))
            assert receive(socket, "inspect")["agent"] == "Alex"
            socket.send(json.dumps({"type": "control", "cmd": "step"}))
            assert receive(socket, "status")["state"] == "paused"
            assert first_tick.wait(2)
            assert not second_tick.wait(0.1)
            socket.send(json.dumps({"type": "control", "cmd": "resume"}))
            assert receive(socket, "status")["state"] == "running"
            assert second_tick.wait(2)
            stream.publish([{"type": "frame", "tick": 1}])
            assert receive(socket, "frame")["tick"] == 1
            # Reconnect has the same hello/history path, without missing or duplicating frames.
            with connect(f"ws://127.0.0.1:{port}", proxy=None) as other:
                receive(other, "hello")
                assert receive(other, "frame")["tick"] == 0
                assert receive(other, "frame")["tick"] == 1
            stream.status("completed")
            assert receive(socket, "status")["state"] == "completed"
    finally:
        stream.control('{"type":"control","cmd":"resume"}')
        worker.join(timeout=2)
        stream.close()


@pytest.mark.parametrize(
    "raw",
    [
        "broken",
        "[]",
        "null",
        "{}",
        '{"type":"control","cmd":"speed","value":0}',
        '{"type":"control","cmd":"speed","value":NaN}',
        '{"type":"control","cmd":"speed","value":true}',
        '{"type":"control","cmd":"inspect","agent":[]}',
        '{"type":"control","cmd":"unknown"}',
    ],
)
def test_invalid_controls_are_private_errors(tmp_path, raw):
    stream = Stream(tmp_path / "frames.jsonl", {"type": "hello"})
    try:
        assert stream.control(raw)["type"] == "error"
        assert not stream.paused and stream.speed == 1
        assert stream.control('{"type":"control","cmd":"speed","value":2}') is None
        assert stream.speed == 2
    finally:
        stream.close()


def test_resume_discards_partial_day_and_terminal_status(tmp_path):
    path = tmp_path / "frames.jsonl"
    stream = Stream(path, {"type": "hello"})
    stream.publish([{"type": "frame", "tick": i} for i in range(35)])
    stream.status("paused", "budget")
    stream.close()
    with path.open("a") as f:
        f.write('{"type":')
    resumed = Stream(path, {"type": "hello"}, resume_tick=32)
    try:
        rows = [json.loads(line) for line in resumed.history]
        assert [r["tick"] for r in rows if r["type"] == "frame"] == list(range(32))
        assert [r for r in rows if r["type"] == "status"] == [
            {"type": "status", "state": "running", "message": "", "llm_usage": {}}
        ]
    finally:
        resumed.close()


def test_a_snapshot_never_places_an_agent_in_a_session_the_frame_does_not_list():
    """A bubble outlives its session by a tick; membership comes from `busy`, not the bubble."""
    cfg = company_config(max_days=1)
    llm = DemoBackend()
    loop = Loop(
        cfg,
        [Agent(s, cfg, llm) for s in cfg.agents],
        Environment(cfg.environment, cfg.agents),
        llm,
        random.Random(42),
        Recorder(),
    )
    seen_bubble_without_session = False

    def check(world, events, retrievals):
        nonlocal seen_bubble_without_session
        snapshot = world.viewer_snapshot()
        live = {s["id"] for s in snapshot["sessions"]}
        for a in snapshot["agents"]:
            assert a["session"] is None or a["session"] in live, (snapshot["tick"], a)
            seen_bubble_without_session |= "bubble" in a and a["session"] is None

    loop.on_tick = check
    try:
        loop.run()
    finally:
        loop.close()
    assert seen_bubble_without_session  # the case the invariant is about actually occurred


def test_a_bad_stream_map_fails_the_run_instead_of_pausing_it(tmp_path):
    tiled = {"layers": [{"objects": []}]}
    (tmp_path / "empty.json").write_text(json.dumps(tiled))
    cfg = company_config(stream_map=str(tmp_path / "empty.json"))
    run_dir = tmp_path / "run"
    with pytest.raises(ValueError, match="missing places"):
        _company_run(cfg, DemoBackend(), run_dir, run_dir / "corpus", None)
    assert not (run_dir / "paused.json").exists()


def test_a_journal_that_cannot_be_written_does_not_mask_the_failure(tmp_path, monkeypatch):
    class Trips(DemoBackend):
        def complete(self, **request):
            raise RuntimeError("engine fault")

    def broken_status(self, state, message="", usage=None):
        if state != "running":
            raise OSError("disk full")

    monkeypatch.setattr(Stream, "status", broken_status)
    run_dir = tmp_path / "run"
    with pytest.raises(RuntimeError, match="engine fault"):
        _company_run(company_config(), Trips(), run_dir, run_dir / "corpus", None)
