"""Exact query reuse changes computations, never memory retrieval or completion requests."""

import json
import runpy
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from conflict_sim.agent.memory import MemoryStore
from conflict_sim.experiment import retrieval_cached_backend, run_scenario
from conflict_sim.llm import DemoBackend
from conflict_sim.models import MemoryConfig
from conflict_sim.usage_audit import audit_context


class CountingDemo(DemoBackend):
    def __init__(self, model="demo", **kwargs):
        super().__init__(**kwargs)
        self.model_embed = model
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        return super().embed(texts)


def test_query_scope_reuses_exact_text_but_never_caches_memory_writes(tmp_path):
    raw = CountingDemo()
    cached = retrieval_cached_backend(raw, tmp_path / "cache.sqlite")
    try:
        with audit_context(call_type="memory_retrieval_embedding"):
            first = cached.embed(["same query"])
            assert cached.embed(["same query"]) == first
            cached.embed(["same  query"])
        with audit_context(call_type="reflection_retrieval_embedding"):
            assert cached.embed(["same query"]) == first
        with audit_context(call_type="memory_write_embedding"):
            assert cached.embed(["same query"]) == first
            cached.embed(["same query"])
        assert raw.calls == [["same query"], ["same  query"], ["same query"], ["same query"]]
    finally:
        cached.close()


def test_query_cache_persists_and_separates_models(tmp_path):
    path = tmp_path / "cache.sqlite"
    with audit_context(call_type="memory_retrieval_embedding"):
        for model, expected_calls in [("v1", 1), ("v1", 0), ("v2", 1)]:
            raw = CountingDemo(model)
            cache = retrieval_cached_backend(raw, path)
            try:
                assert cache.embed(["question"]) == DemoBackend().embed(["question"])
                assert len(raw.calls) == expected_calls
            finally:
                cache.close()


def test_cached_query_still_retrieves_current_memories_mood_and_last_access(tmp_path):
    raw = CountingDemo()
    cache = retrieval_cached_backend(raw, tmp_path / "cache.sqlite")
    store = MemoryStore("A", MemoryConfig(alpha_mood=1, recency_decay=1), cache, "demo")

    def append(tick, valence):
        r = store.append(
            description="same description",
            tick=tick,
            type="observation",
            importance=3,
            valence=valence,
            arousal=abs(valence),
            subjects=[],
        )
        store.set_embeddings({r.id: DemoBackend().embed(["question"])[0]})
        return r.id

    first = append(0, -0.8)
    try:
        with audit_context(call_type="memory_retrieval_embedding"):
            assert (
                store.retrieve("question", cache.embed(["question"])[0], 1, -0.5, 1)[0].id == first
            )
            second = append(2, 0.8)
            assert (
                store.retrieve("question", cache.embed(["question"])[0], 3, 0.5, 1)[0].id == second
            )
            assert (
                store.retrieve("question", cache.embed(["question"])[0], 3, -0.5, 1)[0].id == first
            )
        assert len(raw.calls) == 1
        assert store.last_access == {first: 3, second: 3}
        assert [row["ids"] for row in store.retrieval_log] == [[first], [second], [first]]
    finally:
        cache.close()


def test_concurrent_cold_misses_are_safe_but_can_compute_twice(tmp_path):
    class ConcurrentDemo(CountingDemo):
        def embed(self, texts):
            barrier.wait(timeout=5)
            return super().embed(texts)

    barrier = threading.Barrier(2)
    raw = ConcurrentDemo()
    cache = retrieval_cached_backend(raw, tmp_path / "cache.sqlite")

    def query():
        with audit_context(call_type="memory_retrieval_embedding"):
            return cache.embed(["cold question"])

    try:
        with ThreadPoolExecutor(2) as pool:
            jobs = [pool.submit(query) for _ in range(2)]
            vectors = [job.result(timeout=10) for job in jobs]
        assert vectors[0] == vectors[1] and len(raw.calls) == 2
        assert query() == vectors[0] and len(raw.calls) == 2  # warm lookup skips barrier
    finally:
        cache.close()


@pytest.mark.parametrize("workers", [1, 4])
def test_20_agent_paired_cache_smoke_is_behaviorally_identical(tmp_path, monkeypatch, workers):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    funcs = runpy.run_path(str(scripts / "token_efficiency_h3_cache.py"))
    result = funcs["compare"](tmp_path / "paired", workers)
    before, after = result["baseline"]["metrics"], result["cache_on"]["metrics"]
    assert before["retrieval_queries"] == after["retrieval_queries"] == 193
    assert before["retrieval_embedding_requests"] == 193
    assert 0 < after["cache_hits"] <= 111
    assert after["cache_misses"] + after["cache_hits"] == 193
    assert result["duplicate_computations_avoided"] == after["cache_hits"]
    assert before["memory_write_requests"] == after["memory_write_requests"] == 24
    assert before["memory_write_texts"] == after["memory_write_texts"] == 711
    assert before["completions"] == after["completions"] == 255
    assert result["behavior_identical"] and all(result["components_identical"].values())
    assert result["baseline"]["legacy_sha256"] == (
        "bece6540fa109233575014f9645c6b8a61e01f8d21fd599c18dacea66185a8e3"
    )
    if workers == 1:
        assert after["cache_hits"] == 111 and after["cache_misses"] == 82


def test_c16_runner_wires_cache_and_off_switch_without_changing_saved_results(
    tmp_path, monkeypatch
):
    import conflict_sim.experiment as experiment

    created = []

    def backend(**kwargs):
        raw = CountingDemo(**kwargs)
        created.append(raw)
        return raw

    monkeypatch.setattr(experiment, "DemoBackend", backend)
    before_dir, after_dir = tmp_path / "off", tmp_path / "on"
    before = run_scenario("s0_smoke", before_dir, retrieval_cache=False)
    after = run_scenario("s0_smoke", after_dir)
    assert before == after
    for name in ("events.jsonl", "frames.jsonl", "inspect.jsonl"):
        rows = []
        for directory in (before_dir, after_dir):
            entries = [json.loads(line) for line in (directory / name).read_text().splitlines()]
            for entry in entries:
                entry.pop("run_id", None)  # directory name in viewer hello, not simulation state
            rows.append(entries)
        assert rows[0] == rows[1]
    from conflict_sim.storage import read_memory

    def memories(directory):
        return {
            agent: ([r.model_dump() for r in records], {k: v.tolist() for k, v in vectors.items()})
            for agent, (records, vectors) in read_memory(directory).items()
        }

    assert memories(before_dir) == memories(after_dir)
    # Preset workers=4: concurrent cold misses make exact savings scheduling-dependent.
    assert len(created[0].calls) == 217 and 106 <= len(created[1].calls) < 217
    assert json.loads((after_dir / "manifest.json").read_text())["retrieval_cache"]["enabled"]
    assert not json.loads((before_dir / "manifest.json").read_text())["retrieval_cache"]["enabled"]
