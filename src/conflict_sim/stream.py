"""Local WebSocket transport and replay journal; never reads or mutates engine objects."""

import json
import math
import re
import threading
import time
from pathlib import Path

from websockets.exceptions import ConnectionClosed
from websockets.sync.server import serve


class Stream:
    def __init__(
        self, path: Path, hello: dict, *, resume_tick=None, paused=False, speed=1, delay=0.2
    ):
        self.condition = threading.Condition()
        self.paused, self.speed, self.delay = paused, speed, delay
        self.steps = 0
        self.closed = False
        self.history = _kept(
            path,
            resume_tick,
            lambda row: (
                row["type"] == "hello"
                or (row["type"] in ("frame", "event") and row["tick"] < resume_tick)
            ),
        )
        if not self.history:
            self.history = [json.dumps(hello, ensure_ascii=False)]
        path.write_text("\n".join(self.history) + "\n")
        self.file = path.open("a", encoding="utf-8")
        # Replay inspect: one line per agent whenever its panel changed, never sent over the socket.
        inspect_path = path.with_name("inspect.jsonl")
        kept = _kept(inspect_path, resume_tick, lambda row: row["tick"] < resume_tick)
        inspect_path.write_text("".join(line + "\n" for line in kept))
        self.inspect_file = inspect_path.open("a", encoding="utf-8")
        self.journaled = {}
        for line in kept:
            row = json.loads(line)
            self.journaled[row["agent"]] = _panel(row)
        self.inspections = {}
        self.server = self.thread = None
        self.clients = set()
        self.last_started = None
        self.state = "paused" if paused else "running"
        self.usage = {}
        self.status(self.state)

    def start(self, port=8765):
        self.server = serve(
            self._handle,
            "127.0.0.1",
            port,
            max_size=4096,
            close_timeout=1,
            origins=[None, re.compile(r"http://(localhost|127\.0\.0\.1)(:\d+)?")],
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.server.socket.getsockname()[1]

    def publish(self, messages, inspections=None, usage=None):
        with self.condition:
            if usage is not None:
                self.usage = dict(usage)
            if inspections is not None:
                self.inspections = inspections
                for agent, message in inspections.items():
                    if self.journaled.get(agent) != _panel(message):
                        self.journaled[agent] = _panel(message)
                        self.inspect_file.write(
                            json.dumps(message, ensure_ascii=False, allow_nan=False) + "\n"
                        )
                self.inspect_file.flush()
            for message in messages:
                line = json.dumps(message, ensure_ascii=False, allow_nan=False)
                self.file.write(line + "\n")
                self.history.append(line)
            self.file.flush()
            self.condition.notify_all()

    def status(self, state, message="", usage=None):
        with self.condition:
            self.state = state
            if usage is not None:
                self.usage = dict(usage)
            self.publish(
                [{"type": "status", "state": state, "message": message, "llm_usage": self.usage}]
            )

    def before_tick(self):
        """Only the simulation thread calls this: controls take effect at tick boundaries."""
        with self.condition:
            while not self.closed:
                if self.paused and not self.steps:
                    self.condition.wait()
                    continue
                remaining = (
                    self.delay / self.speed - (time.monotonic() - self.last_started)
                    if self.last_started is not None
                    else 0
                )
                if not self.paused and remaining > 0:
                    self.condition.wait(remaining)
                    continue
                if self.paused:
                    self.steps -= 1
                self.last_started = time.monotonic()
                return
            raise RuntimeError("Stream closed while the engine was waiting")

    def control(self, raw):
        """Return an optional private response; invalid controls cannot affect the engine."""
        try:
            msg = json.loads(raw)
            if not isinstance(msg, dict) or msg.get("type") != "control":
                raise ValueError("Expected a control message")
            cmd = msg.get("cmd")
            with self.condition:
                if cmd == "inspect":
                    agent = msg.get("agent")
                    if not isinstance(agent, str) or agent not in self.inspections:
                        raise ValueError("Unknown agent")
                    return self.inspections[agent]
                if self.state not in ("running", "paused"):
                    raise ValueError("Run is no longer active")
                if cmd in ("pause", "resume", "step"):
                    self.paused = cmd != "resume"
                    self.steps = self.steps + 1 if cmd == "step" else 0
                    self.status("paused" if self.paused else "running")
                elif cmd == "speed":
                    value = msg.get("value")
                    if (
                        type(value) not in (float, int)
                        or not math.isfinite(value)
                        or not 0 < value <= 100
                    ):
                        raise ValueError("Speed must be a finite number in (0, 100]")
                    self.speed = value
                else:
                    raise ValueError("Unknown control command")
                self.condition.notify_all()
        except (ValueError, TypeError) as exc:
            return {"type": "error", "message": str(exc)}
        return None

    def _handle(self, socket):
        # Each client has its own history cursor. Network writes never block the engine.
        with self.condition:
            self.clients.add(socket)
        cursor = 0
        try:
            while True:
                with self.condition:
                    batch = self.history[cursor:]
                    closed = self.closed
                for line in batch:
                    socket.send(line)
                    cursor += 1
                if closed:
                    return
                try:
                    raw = socket.recv(timeout=0.05)
                except TimeoutError:
                    continue
                response = self.control(raw)
                if response is not None:
                    socket.send(json.dumps(response, ensure_ascii=False))
        except ConnectionClosed:
            pass
        finally:
            with self.condition:
                self.clients.discard(socket)
                self.condition.notify_all()

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()
            # Let connected handlers flush the terminal status, with a bounded slow-client wait.
            self.condition.wait_for(lambda: not self.clients, timeout=1)
            clients = list(self.clients)
        for client in clients:
            client.close()
        if self.server is not None:
            self.server.shutdown()
            self.thread.join(timeout=2)
        self.file.close()
        self.inspect_file.close()


def _kept(path, resume_tick, keep):
    """Lines of an earlier segment that survive a resume; a fresh run keeps none."""
    lines = []
    if resume_tick is not None and path.exists():
        for line in path.read_text().splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                break  # a process may have died in its final append
            if keep(row):
                lines.append(line)
    return lines


def _panel(message):
    return {k: v for k, v in message.items() if k != "tick"}
