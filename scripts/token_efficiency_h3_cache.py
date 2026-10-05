"""No-cost paired 20-agent smoke; compare exact retrieval cache OFF/ON.

Run: python scripts/token_efficiency_h3_cache.py --output work/h3-cache
"""

import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

from token_efficiency_analysis import Recorder, TraceDemo

from conflict_sim.agent import Agent
from conflict_sim.company_runtime import apply_initial_relationships, build_company_config
from conflict_sim.environment import Environment
from conflict_sim.experiment import RETRIEVAL_CALL_TYPES, retrieval_cached_backend
from conflict_sim.loop import Loop


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def metrics(rows, enabled):
    queries = [
        r
        for r in rows
        if r["call_type"] in RETRIEVAL_CALL_TYPES
        and r["event"] == ("embedding_cache" if enabled else "embedding")
    ]
    requests = [r for r in rows if r["event"] == "embedding"]
    retrieval = [r for r in requests if r["call_type"] in RETRIEVAL_CALL_TYPES]
    hits = sum(r.get("cache_hits", 0) for r in queries)
    misses = sum(r.get("cache_misses", r["text_count"]) for r in queries)
    grouped = {}
    for field in ("agent", "tick"):
        groups = defaultdict(lambda: {"queries": 0, "hits": 0, "misses": 0})
        for row in queries:
            item = groups[str(row[field])]
            item["queries"] += row["text_count"]
            item["hits"] += row.get("cache_hits", 0)
            item["misses"] += row.get("cache_misses", row["text_count"])
        grouped[f"per_{field}"] = dict(sorted(groups.items()))
    count = sum(r["text_count"] for r in queries)
    return {
        "retrieval_queries": count,
        "retrieval_embedding_requests": sum(r["call_count"] for r in retrieval),
        "retrieval_embedding_texts": sum(r["text_count"] for r in retrieval),
        "all_embedding_requests": sum(r["call_count"] for r in requests),
        "all_embedding_texts": sum(r["text_count"] for r in requests),
        "memory_write_requests": sum(
            r["call_count"] for r in requests if r["call_type"] == "memory_write_embedding"
        ),
        "memory_write_texts": sum(
            r["text_count"] for r in requests if r["call_type"] == "memory_write_embedding"
        ),
        "cache_lookups": len(queries) if enabled else 0,
        "cache_hits": hits,
        "cache_misses": misses if enabled else None,
        "cache_hit_rate": hits / count if enabled and count else None,
        "completions": sum(r["call_count"] for r in rows if r["event"] == "completion"),
        **grouped,
    }


def run_one(output, enabled, workers):
    output.mkdir(parents=True, exist_ok=False)
    cfg = build_company_config("s0_smoke").model_copy(update={"workers": workers})
    raw = TraceDemo(output / "demo_audit.jsonl")
    raw.model_embed = "DemoBackend"
    llm = retrieval_cached_backend(raw, output / "query_cache.sqlite") if enabled else raw
    agents = [Agent(spec, cfg, llm) for spec in cfg.agents]
    apply_initial_relationships(agents)
    recorder = Recorder()
    loop = Loop(
        cfg,
        agents,
        Environment(cfg.environment, cfg.agents),
        llm,
        random.Random(cfg.random_seed),
        recorder,
    )
    states = []

    def capture(world, events, retrievals):
        # Detach nested mutable state at every tick; final-only comparisons can miss divergence.
        states.append(
            json.loads(
                json.dumps(
                    {
                        "checkpoint": world.checkpoint(),
                        "viewer": world.viewer_snapshot(),
                        "busy": world.busy,
                        "live": sorted(world.live),
                        "last_access": {a.name: a.memory.last_access for a in agents},
                    }
                )
            )
        )

    loop.on_tick = capture
    try:
        loop.run()
    finally:
        loop.close()
        if enabled:
            if loop.pool is not None:
                loop.pool.shutdown(wait=True, cancel_futures=True)
            llm.close()
    ticks = [
        [[e.model_dump() for e in events], [[r.model_dump(), v] for r, v in records], retrievals]
        for events, records, retrievals in recorder.ticks
    ]
    old_semantic = {
        "ticks": ticks,
        "agents": [a.snapshot() for a in agents],
        "prompts": sorted(raw.requests),
        "embeds": sorted(raw.embeds),
    }
    behavior = {k: v for k, v in old_semantic.items() if k != "embeds"} | {"states": states}
    components = {
        key: digest(value)
        for key, value in {
            "events": [tick[0] for tick in ticks],
            "memory_records_and_vectors": [tick[1] for tick in ticks],
            "selected_retrieval_ids_and_queries": [tick[2] for tick in ticks],
            "agent_state": behavior["agents"],
            "tasks_and_environment": [s["checkpoint"]["env"] for s in states],
            "conversations": [
                [s["checkpoint"]["threads"], s["checkpoint"]["sessions"]] for s in states
            ],
            "relationships_and_stress": [s["checkpoint"]["agents"] for s in states],
            "prompt_inputs": behavior["prompts"],
            "tick_states": states,
        }.items()
    }
    rows = [json.loads(line) for line in raw.path.read_text().splitlines()]
    return {
        "metrics": metrics(rows, enabled),
        "behavior_sha256": digest(behavior),
        "component_sha256": components,
        "legacy_sha256": digest(old_semantic),
    }


def compare(output, workers=4):
    output.mkdir(parents=True, exist_ok=False)
    baseline = run_one(output / "baseline", False, workers)
    optimized = run_one(output / "cache_on", True, workers)
    before = baseline["metrics"]["retrieval_embedding_texts"]
    after = optimized["metrics"]["retrieval_embedding_texts"]
    result = {
        "method": {
            "scenario": "s0_smoke",
            "seed": 1413,
            "agents": 20,
            "ticks": 32,
            "workers": workers,
            "paid_api_calls": 0,
            "cache_start": "empty per run",
            "backend": "unchanged DemoBackend with metadata recorder",
        },
        "baseline": baseline,
        "cache_on": optimized,
        "duplicate_computations_avoided": before - after,
        "retrieval_computation_reduction": (before - after) / before,
        "behavior_identical": baseline["behavior_sha256"] == optimized["behavior_sha256"],
        "components_identical": {
            k: baseline["component_sha256"][k] == optimized["component_sha256"][k]
            for k in baseline["component_sha256"]
        },
    }
    (output / "h3_cache_comparison.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not result["behavior_identical"]:
        raise AssertionError("Cache changed simulation results")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    result = compare(args.output, args.workers)
    print(
        json.dumps(
            {
                "behavior_identical": result["behavior_identical"],
                "avoided": result["duplicate_computations_avoided"],
                "baseline": {
                    k: v
                    for k, v in result["baseline"]["metrics"].items()
                    if not k.startswith("per_")
                },
                "cache_on": {
                    k: v
                    for k, v in result["cache_on"]["metrics"].items()
                    if not k.startswith("per_")
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
