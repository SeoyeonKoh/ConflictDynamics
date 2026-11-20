"""Several runs in one process (experiment --scenarios/--parallel-runs): their journals stay
apart, they share one API gate, and one stop pauses them all."""

import json
import threading
import time

import httpx
import openai
import pytest

from conflict_sim import experiment
from conflict_sim.experiment import run_batch, run_scenario, stop_all
from conflict_sim.llm import OpenAIBackend, SharedRateGate
from conflict_sim.usage_audit import audit_context

SCENARIOS = ("r10_human", "r10_auth_single", "s0_smoke")
KWARGS = {"backend": "demo", "max_days": 1}


def _jobs(root, scenarios=SCENARIOS):
    return [(name, root / name / "replicate-1", 0) for name in scenarios]


def test_runs_side_by_side_write_exactly_what_each_writes_alone(tmp_path):
    """Three demo runs at once: each run's events, frames and summary are byte for byte the
    ones it writes when it runs alone, so nothing leaked between them."""
    results = run_batch(_jobs(tmp_path / "together"), parallel=3, resume=False, kwargs=KWARGS)
    assert all("summary" in r for r in results), results
    for name in SCENARIOS:
        alone = tmp_path / "alone" / name / "replicate-1"
        run_scenario(name, alone, **KWARGS)
        together = tmp_path / "together" / name / "replicate-1"
        for journal in ("events.jsonl", "frames.jsonl", "summary.json"):
            assert (together / journal).read_bytes() == (alone / journal).read_bytes(), journal
        assert json.loads((together / "manifest.json").read_text())["scenario"] == name


def test_resume_continues_paused_runs_starts_missing_ones_and_skips_finished_ones(tmp_path):
    done = run_batch(_jobs(tmp_path, SCENARIOS[:1]), parallel=1, resume=False, kwargs=KWARGS)
    assert "summary" in done[0]
    paused = tmp_path / SCENARIOS[1] / "replicate-1"
    paused.mkdir(parents=True)
    (paused / "paused.json").write_text("{}")
    calls = []
    real = experiment.run_scenario
    experiment.run_scenario = lambda name, run_dir, **kw: calls.append((name, kw["resume"])) or {}
    try:
        results = run_batch(_jobs(tmp_path), parallel=3, resume=True, kwargs=KWARGS)
    finally:
        experiment.run_scenario = real
    assert "skipped" in results[0]  # finished: left alone
    assert sorted(calls) == [(SCENARIOS[1], True), (SCENARIOS[2], False)]  # resumed; started


def test_one_stop_pauses_every_run(tmp_path, monkeypatch):
    """SIGTERM/SIGINT call stop_all: every run pauses before its next tick and says so."""
    from conflict_sim.loop import Loop

    tick = Loop.tick
    monkeypatch.setattr(Loop, "tick", lambda self, t: (time.sleep(0.03), tick(self, t))[1])
    stops: list[threading.Event] = []
    out = {}
    worker = threading.Thread(target=lambda: out.update(results=run_batch(
        _jobs(tmp_path), parallel=3, resume=False, kwargs=KWARGS, stops=stops)))  # fmt: skip
    worker.start()
    deadline = time.monotonic() + 30
    while len(stops) < len(SCENARIOS) and time.monotonic() < deadline:
        time.sleep(0.01)
    def ticked(name):  # the run has finished at least one tick
        frames = tmp_path / name / "replicate-1" / "frames.jsonl"
        return frames.exists() and '"type": "frame"' in frames.read_text()

    while not all(ticked(n) for n in SCENARIOS) and time.monotonic() < deadline:
        time.sleep(0.01)
    stop_all(stops)
    worker.join(60)
    assert not worker.is_alive()
    for name, result in zip(SCENARIOS, out["results"], strict=True):
        assert result["summary"]["run_status"] == "paused", result
        paused = json.loads((tmp_path / name / "replicate-1" / "paused.json").read_text())
        assert paused["reason"] == "stopped" and paused["tick"] > 0


def test_the_gate_never_lets_more_than_max_in_flight_through():
    gate, seen = SharedRateGate(3), []

    def call():
        with gate.slot():
            seen.append(gate.in_flight)
            time.sleep(0.02)

    threads = [threading.Thread(target=call) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert gate.peak == 3 and max(seen) <= 3 and gate.in_flight == 0
    with pytest.raises(ValueError):
        SharedRateGate(0)


def test_a_429_in_one_run_holds_every_run_sharing_the_gate(monkeypatch):
    """Run A is told to wait; run B, sharing the gate, does not call until that has passed."""
    monkeypatch.setattr("conflict_sim.llm._retry_after", lambda headers: 0.3)
    gate, sent = SharedRateGate(4), []
    limited = iter([True])

    def respond(request):
        sent.append((request.headers["x-run"], time.monotonic()))
        if next(limited, False):
            return httpx.Response(429, json={"error": {"message": "Rate limit reached for tokens",
                                                       "type": "rate_limit_error",
                                                       "code": "rate_limit_exceeded"}})  # fmt: skip
        return httpx.Response(200, json=_completion("ok"))

    def backend(run):
        client = openai.OpenAI(api_key="k", base_url="https://example.invalid/v1", max_retries=0,
                               default_headers={"x-run": run},
                               http_client=_http(respond))  # fmt: skip
        return OpenAIBackend(client, rate_gate=gate)

    a, b = backend("a"), backend("b")
    start = time.monotonic()
    first = threading.Thread(target=lambda: a.complete(system="S", prompt="P", model="m",
                                                       temperature=0, json_mode=False))  # fmt: skip
    first.start()
    while not sent:
        time.sleep(0.005)
    b.complete(system="S", prompt="P", model="m", temperature=0, json_mode=False)
    first.join()
    b_sent = next(t for run, t in sent if run == "b")
    assert b_sent - start >= 0.3 and gate.cooldowns == 1


def test_without_a_gate_a_run_waits_alone_as_before(monkeypatch):
    waits = []
    monkeypatch.setattr("conflict_sim.llm.time.sleep", waits.append)
    replies = iter([httpx.Response(429, headers={"retry-after-ms": "10"},
                                   json={"error": {"message": "Rate limited", "type": "x",
                                                   "code": "rate_limit_exceeded"}})])  # fmt: skip
    client = openai.OpenAI(api_key="k", base_url="https://example.invalid/v1", max_retries=0,
                           http_client=httpx.Client(transport=httpx.MockTransport(
                               lambda r: next(replies, httpx.Response(200, json=_completion("ok")))
                           )))  # fmt: skip
    assert OpenAIBackend(client).complete(system="S", prompt="P", model="m", temperature=0,
                                          json_mode=False) == "ok"  # fmt: skip
    assert len(waits) == 1


def test_parallel_runs_audit_into_their_own_files(tmp_path):
    """The audit trail rides on a context variable and each backend's own path: two runs
    calling at once never write into each other's llm_audit.jsonl."""
    respond = lambda r: httpx.Response(200, json=_completion("ok"))  # noqa: E731

    def run(name):
        client = openai.OpenAI(api_key="k", base_url="https://example.invalid/v1", max_retries=0,
                               http_client=_http(respond))  # fmt: skip
        backend = OpenAIBackend(client, audit_path=tmp_path / f"{name}.jsonl")
        with audit_context(agent=name):
            for _ in range(15):
                backend.complete(system="S", prompt="P", model="m", temperature=0,
                                 json_mode=False)  # fmt: skip

    threads = [threading.Thread(target=run, args=(n,)) for n in ("A", "B", "C")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for name in ("A", "B", "C"):
        rows = [json.loads(line) for line in (tmp_path / f"{name}.jsonl").read_text().splitlines()]
        assert rows and {r["agent"] for r in rows} == {name}


def test_the_cli_runs_several_scenarios_and_keeps_one_scenario_as_it_was(tmp_path, capsys):
    root = tmp_path / "cli"
    experiment.main(["--scenarios", "r10_human", "s0_smoke", "--parallel-runs", "2",
                     "--max-in-flight", "4", "--output-root", str(root)])  # fmt: skip
    lines = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    assert [line["run"] for line in lines[:2]] == [
        str(root / "r10_human" / "replicate-1"), str(root / "s0_smoke" / "replicate-1")]
    assert lines[2]["rate_gate"]["max_in_flight"] == 4
    experiment.main(["--scenarios", "r10_human", "s0_smoke", "--resume", "--output-root",
                     str(root)])  # fmt: skip
    assert all("skipped" in json.loads(x) for x in capsys.readouterr().out.splitlines())
    with pytest.raises(SystemExit):
        experiment.main(["r10_human", "--scenarios", "s0_smoke", "--dry-run"])
    with pytest.raises(SystemExit):  # paid runs keep the cost guard: one --pilot each
        experiment.main(["--scenarios", "r10_human", "s0_smoke", "--backend", "openai"])


def _http(respond):
    return httpx.Client(transport=httpx.MockTransport(respond))


def _completion(text):
    return {
        "id": "x", "object": "chat.completion", "created": 0, "model": "m",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
    }  # fmt: skip


# ---- review fixes (2026-11-20): stop, gate, queue, CLI, dry-run, shared cache ----


def _flex_busy_backend(**options):
    busy = {"error": {"message": "Resource Unavailable", "type": "rate_limit_error"}}
    client = openai.OpenAI(api_key="k", base_url="https://example.invalid/v1", max_retries=0,
                           http_client=_http(lambda r: httpx.Response(429, json=busy)))  # fmt: skip
    return OpenAIBackend(client, flex=True, flex_fallback=False, **options)


def test_a_stop_ends_a_flex_wait_at_once():
    """C1: a run waiting for Flex (backoff up to a minute, for hours) stops as soon as asked."""
    from conflict_sim.llm import CallStopped

    backend = _flex_busy_backend()
    backend.stop = threading.Event()
    threading.Timer(0.2, backend.stop.set).start()
    start = time.monotonic()
    with pytest.raises(CallStopped, match="stopped"):
        backend.complete(system="S", prompt="P", model="m", temperature=0, json_mode=False)
    assert time.monotonic() - start < 1.0


def test_a_stop_ends_a_shared_cooldown_and_a_queue_for_a_slot():
    from conflict_sim.llm import CallStopped

    gate, stop = SharedRateGate(1), threading.Event()
    gate.cool_down(30)
    threading.Timer(0.2, stop.set).start()
    start = time.monotonic()
    with pytest.raises(CallStopped):
        with gate.slot(stop):
            pass
    assert time.monotonic() - start < 1.0
    gate, stop, held = SharedRateGate(1), threading.Event(), threading.Event()
    holder = threading.Thread(target=lambda: gate.slot().__enter__() and held.wait(5))
    with gate.slot():  # the only slot is taken: the next caller queues
        threading.Timer(0.2, stop.set).start()
        start = time.monotonic()
        with pytest.raises(CallStopped):
            with gate.slot(stop):
                pass
    assert time.monotonic() - start < 1.0 and not holder.is_alive()


def test_a_cooldown_set_while_queued_for_a_slot_is_still_waited_out():
    """M1: a caller that passed the cooldown check and then queued for the slot must not fire
    the moment the slot frees if a 429 arrived meanwhile."""
    gate, entered = SharedRateGate(1), []
    with gate.slot():
        waiter = threading.Thread(target=lambda: gate.slot().__enter__() or entered.append(
            time.monotonic()))  # fmt: skip
        waiter.start()
        time.sleep(0.1)  # the waiter is queued on the slot now
        gate.cool_down(0.4)  # this call got a 429
        released = time.monotonic()
    waiter.join(5)
    assert entered and entered[0] - released >= 0.4


def test_a_stop_keeps_queued_runs_from_starting(tmp_path, monkeypatch):
    """M2: more runs than slots; a stop pauses the running one and the queued ones never start."""
    started = []

    def fake_run(name, run_dir, *, stop, **_):
        started.append(name)
        stop.wait(5)
        return {"run_status": "paused"}

    monkeypatch.setattr(experiment, "run_scenario", fake_run)
    stops: list[threading.Event] = []
    timer = threading.Timer(0.3, lambda: stop_all(stops))
    timer.start()
    results = run_batch(_jobs(tmp_path), parallel=1, resume=False, kwargs={}, stops=stops)
    assert started == [SCENARIOS[0]]
    assert results[0] == {"run": str(tmp_path / SCENARIOS[0] / "replicate-1"),
                          "summary": {"run_status": "paused"}}  # fmt: skip
    assert all(r.get("skipped") == "stopped before it started" for r in results[1:])


def test_one_failing_run_leaves_the_others_and_the_batch_exits_nonzero(tmp_path, monkeypatch,
                                                                      capsys):  # fmt: skip
    def fake_run(name, run_dir, **_):
        if name == SCENARIOS[1]:
            raise RuntimeError("boom")
        return {"run_status": "completed"}

    monkeypatch.setattr(experiment, "run_scenario", fake_run)
    with pytest.raises(SystemExit) as exit_:
        experiment.main(["--scenarios", *SCENARIOS, "--parallel-runs", "3",
                         "--output-root", str(tmp_path)])  # fmt: skip
    assert exit_.value.code == 1
    lines = [json.loads(x) for x in capsys.readouterr().out.splitlines()]
    assert ["error" in line for line in lines] == [False, True, False]
    assert "boom" in lines[1]["error"]


@pytest.mark.parametrize("argv, message", [
    (["--max-in-flight", "0"], "max-in-flight"),
    (["--max-in-flight", "-2"], "max-in-flight"),
    (["--parallel-runs", "0"], "parallel-runs"),
    (["--scenarios", "r10_human", "r10_human"], "twice"),
])  # fmt: skip
def test_the_batch_cli_refuses_bad_limits_and_duplicate_scenarios(argv, message):
    """M3: no silent 'unlimited' for --max-in-flight 0, and no two runs in one directory."""
    base = [] if "--scenarios" in argv else ["--scenarios", "r10_human", "s0_smoke"]
    with pytest.raises(SystemExit, match=message):
        experiment.main([*base, *argv, "--dry-run"])


def test_paid_batches_fail_before_any_run_starts_without_approval(tmp_path, monkeypatch):
    monkeypatch.delenv("ALLOW_PAID_API_EXPERIMENTS", raising=False)
    with pytest.raises(SystemExit, match="ALLOW_PAID_API_EXPERIMENTS"):
        experiment.main(["--scenarios", "r10_human", "s0_smoke", "--backend", "openai",
                         "--pilot", "--output-root", str(tmp_path)])  # fmt: skip
    assert not any(tmp_path.iterdir())


def test_a_batch_dry_run_shows_the_overrides_the_runs_would_use(capsys):
    """M4: --dry-run with --scenarios prints what each run would really use."""
    experiment.main(["--scenarios", "r10_human", "s0_smoke", "--dry-run", "--no-flex-fallback",
                     "--flex", "1", "--workers", "3", "--days", "2", "--max-total-tokens", "0",
                     "--claude-max-concurrent", "2"])  # fmt: skip
    for line in capsys.readouterr().out.splitlines():
        cfg = json.loads(line)["config"]
        assert (cfg["flex"], cfg["flex_fallback"], cfg["workers"], cfg["max_days"]) == (
            True, False, 3, 2)
        assert cfg["max_total_tokens"] is None and cfg["claude_max_concurrent"] == 2


def test_replay_config_takes_claude_concurrency_and_validates():
    from pydantic import ValidationError

    from conflict_sim.company_runtime import build_company_config
    from conflict_sim.experiment import replay_config

    saved = build_company_config("r10_human").model_dump()
    assert replay_config(saved, claude_max_concurrent=7).claude_max_concurrent == 7
    with pytest.raises(ValidationError):
        replay_config(saved, workers=0)


def test_runs_sharing_one_embedding_cache_file_write_at_once(tmp_path):
    """M5: two runs' caches on one file (cfg.embed_cache), many threads writing: no 'database
    is locked', and every vector written is read back."""
    from conflict_sim.llm import EmbedCache

    class Embedder:
        model_embed = "fake"
        usage = {}

        def embed(self, texts):
            return [[float(len(t)), 1.0] for t in texts]

    path = tmp_path / "embed.sqlite"
    caches = [EmbedCache(Embedder(), path) for _ in range(2)]
    errors = []

    def write(cache, base):
        try:
            for i in range(60):
                cache.embed([f"{base}-{i}-{j}" for j in range(3)])
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(caches[i % 2], i)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert caches[0].db.execute("pragma journal_mode").fetchone()[0] == "wal"
    count = caches[1].db.execute("select count(*) from embeddings").fetchone()[0]
    assert count == 8 * 60 * 3


def test_a_claude_run_gives_its_gate_and_stop_to_its_openai_embedder(monkeypatch):
    """m4: Claude's OpenAI embeddings go through the batch's gate and stop with the run."""
    from conflict_sim import llm

    monkeypatch.setattr(llm, "create_openai_client", lambda env: object())
    gate = SharedRateGate(2)
    embed = llm.make_embedder("openai", "text-embedding-3-small", None, gate)
    assert embed.backend.rate_gate is gate

    class Claude:
        _embed = embed

    stop = threading.Event()
    llm.attach_stop(Claude(), stop)
    assert embed.backend.stop is stop


def test_the_first_ctrl_c_pauses_and_the_second_quits_at_once(tmp_path, monkeypatch):
    """C1: a run slow to pause must not swallow a second Ctrl+C; signals are restored after."""
    import os
    import signal

    def slow_run(name, run_dir, *, stop, **_):
        stop.wait(10)
        time.sleep(4)  # pausing takes long (a request in flight)
        return {"run_status": "paused"}

    monkeypatch.setattr(experiment, "run_scenario", slow_run)
    before = signal.getsignal(signal.SIGINT)
    for delay in (0.3, 0.8):
        threading.Timer(delay, os.kill, (os.getpid(), signal.SIGINT)).start()
    start = time.monotonic()
    with pytest.raises(KeyboardInterrupt):
        experiment.main(["--scenarios", "r10_human", "--output-root", str(tmp_path)])
    assert time.monotonic() - start < 3  # not the 4 s the run would still take to pause
    assert signal.getsignal(signal.SIGINT) is before
