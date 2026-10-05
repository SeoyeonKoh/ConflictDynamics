"""One no-cost 20-agent smoke: metadata-only H1/H2/H3 analysis (no research conditions).

Run: python scripts/token_efficiency_analysis.py --output results/token_efficiency
"""

import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from conflict_sim.agent import Agent
from conflict_sim.company_runtime import apply_initial_relationships, build_company_config
from conflict_sim.environment import Environment
from conflict_sim.llm import DemoBackend
from conflict_sim.loop import Loop
from conflict_sim.usage_audit import (
    audit_context,
    completion_metadata,
    embedding_metadata,
    log_call,
)


class Recorder:
    def __init__(self):
        self.ticks = []

    def write_tick(self, events, memory_rows, retrieval_rows):
        self.ticks.append(
            (
                list(events),
                [(r, None if v is None else v.tolist()) for r, v in memory_rows],
                list(retrieval_rows),
            )
        )

    def write_checkpoint(self, day, data):
        pass


class TraceDemo:
    """Delegate unchanged DemoBackend requests; reuse production metadata helpers and scopes."""

    def __init__(self, path):
        self.backend = DemoBackend()
        self.path = path
        self.audit_path = path
        self.requests = []
        self.embeds = []

    def complete(self, **request):
        self.requests.append(
            json.dumps(
                {k: v.__name__ if k == "schema" and v else v for k, v in request.items()},
                sort_keys=True,
            )
        )
        result = self.backend.complete(**request)
        with audit_context(audit_path=self.path):
            log_call(
                "completion",
                call_count=1,
                record_source="demo",
                model=request["model"],
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                cached_tokens=None,
                schema=request["schema"].__name__ if request.get("schema") else None,
                **completion_metadata(request["system"], request["prompt"]),
            )
        return result

    def embed(self, texts):
        self.embeds.append(list(texts))
        result = self.backend.embed(texts)
        with audit_context(audit_path=self.path):
            log_call(
                "embedding",
                call_count=1,
                record_source="demo",
                model="DemoBackend",
                input_tokens=None,
                total_tokens=None,
                **embedding_metadata(texts),
            )
        return result


def section_summary(calls):
    """Consecutive comparisons are within agent/call_type, including same-tick retries."""
    values = defaultdict(list)
    for row in calls:
        for name, metric in row["section_metrics"].items():
            values[(row["call_type"], name)].append((row, metric))
    output = {}
    for (kind, name), entries in sorted(values.items()):
        prior = {}
        equal = pairs = unchanged_chars = 0
        for row, metric in entries:
            agent = row["agent"]
            if agent in prior:
                pairs += 1
                if prior[agent] == metric["sha256"]:
                    equal += 1
                    unchanged_chars += metric["chars"]
            prior[agent] = metric["sha256"]
        chars = [metric["chars"] for _, metric in entries]
        denominator = sum(r["system_chars"] + r["prompt_chars"] for r, _ in entries)
        output[f"{kind}/{name}"] = {
            "occurrences": len(entries),
            "mean_chars": sum(chars) / len(chars),
            "max_chars": max(chars),
            "total_chars": sum(chars),
            "unique_exact_hashes": len({m["sha256"] for _, m in entries}),
            "consecutive_pairs": pairs,
            "consecutive_equal": equal,
            "consecutive_equal_rate": equal / pairs if pairs else None,
            "unchanged_retransmitted_chars": unchanged_chars,
            "share_of_system_plus_prompt_chars": sum(chars) / denominator if denominator else 0,
        }
    return output


def duplicate_summary(rows):
    flat = [(r, m) for r in rows for m in r["text_metrics"]]
    groups = defaultdict(list)
    for row, metric in flat:
        groups[row["agent"]].append((row["model"], metric))
    exact = {(r["model"], m["sha256"]) for r, m in flat}
    normalized = {(r["model"], m["whitespace_sha256"]) for r, m in flat}
    by_agent = {}
    for agent, entries in sorted(groups.items()):
        unique = len({(model, m["sha256"]) for model, m in entries})
        pairs = max(0, len(entries) - 1)
        repeated = sum(
            (a, am["sha256"]) == (b, bm["sha256"]) for (a, am), (b, bm) in zip(entries, entries[1:])
        )
        by_agent[agent] = {
            "total": len(entries),
            "unique": unique,
            "duplicate_rate": (len(entries) - unique) / len(entries),
            "consecutive_pairs": pairs,
            "consecutive_equal": repeated,
            "consecutive_equal_rate": repeated / pairs if pairs else None,
        }
    owners = defaultdict(set)
    for row, metric in flat:
        owners[(row["model"], metric["sha256"])].add(row["agent"])
    count = len(flat)
    seen = set()
    duplicate_chars = 0
    for row, metric in flat:
        key = (row["model"], metric["sha256"])
        if key in seen:
            duplicate_chars += metric["chars"]
        seen.add(key)
    total_chars = sum(metric["chars"] for _, metric in flat)
    return {
        "total_queries": count,
        "total_query_chars": total_chars,
        "mean_query_chars": total_chars / count if count else 0,
        "max_query_chars": max((m["chars"] for _, m in flat), default=0),
        "hypothetical_exact_duplicate_chars_avoided": duplicate_chars,
        "unique_exact_queries": len(exact),
        "duplicate_queries": count - len(exact),
        "exact_duplicate_rate": (count - len(exact)) / count if count else 0,
        "unique_whitespace_normalized_queries": len(normalized),
        "whitespace_duplicate_rate": (count - len(normalized)) / count if count else 0,
        "duplicate_within_agent": sum(v["total"] - v["unique"] for v in by_agent.values()),
        "pooled_within_agent_duplicate_rate": sum(
            v["total"] - v["unique"] for v in by_agent.values()
        )
        / count
        if count
        else 0,
        "consecutive_pairs": sum(v["consecutive_pairs"] for v in by_agent.values()),
        "consecutive_equal": sum(v["consecutive_equal"] for v in by_agent.values()),
        "hashes_shared_by_multiple_agents": sum(len(v) > 1 for v in owners.values()),
        "per_agent": by_agent,
        "per_agent_tick": dict(
            sorted(Counter(f"{r['agent']}@{r['tick']}" for r, _ in flat).items())
        ),
        "maximum_retrieval_queries_per_agent_tick": max(
            Counter((r["agent"], r["tick"]) for r, _ in flat).values(), default=0
        ),
        "hypothetical_cold_exact_cache": {
            "text_embeddings_avoided": count - len(exact),
            "single_text_requests_avoided": count - len(exact),
            "assumptions": "same model, exact text, sequential/warmed cache or single-flight; "
            "current runner has no cache; concurrent cold misses may duplicate",
        },
    }


def analyze(rows, events):
    calls = [r for r in rows if r["event"] == "completion"]
    decisions = [r for r in calls if r["schema"] is not None]
    act = [r for r in decisions if r["call_type"] == "act"]
    first = [r for r in act if not r["action_retry"] and not r["validation_retry"]]
    action_only = sum(r["action_retry"] and not r["validation_retry"] for r in act)
    validation_only = sum(r["validation_retry"] and not r["action_retry"] for r in act)
    both = sum(r["action_retry"] and r["validation_retry"] for r in act)
    reasons = Counter(
        re.sub(r"\b(?:HDS-\d+|T\d+)\b", "<ID>", e.payload["reason"])
        for e in events
        if e.kind == "rejected"
    )
    queries = [
        r
        for r in rows
        if r["event"] == "embedding"
        and r["call_type"] in ("memory_retrieval_embedding", "reflection_retrieval_embedding")
    ]
    act_groups = defaultdict(list)
    for row in act:
        act_groups[(row["agent"], row["tick"])].append(row)
    excess = sum(max(0, len(group) - 1) for group in act_groups.values())
    h2 = {
        "all_completions": len(calls),
        "total_json_decisions": len(decisions),
        "all_first_attempt_json_decisions": sum(
            not r["action_retry"] and not r["validation_retry"] for r in decisions
        ),
        "act_completions": len(act),
        "act_agent_tick_groups": len(act_groups),
        "act_groups_with_multiple_completions": sum(len(g) > 1 for g in act_groups.values()),
        "act_max_completions_per_agent_tick_observed": max(map(len, act_groups.values())),
        "act_groups_with_only_retry_tagged_completions": sum(
            all(r["action_retry"] for r in g) for g in act_groups.values()
        ),
        "act_calls_above_one_per_agent_tick": excess,
        "act_group_amplification_ratio": len(act) / len(act_groups),
        "act_first_attempt_completions": len(first),
        "act_action_retry_only": action_only,
        "act_validation_retry_only": validation_only,
        "act_both_retries": both,
        "act_retry_tagged_completions": len(act) - len(first),
        "retry_ratio_note": "flagged/unflagged is not additional calls per agent-tick; "
        "retry-only groups may have no earlier LLM action completion",
        "act_retry_tagged_vs_unflagged_ratio": len(act) / len(first) if first else None,
        "all_validation_retry_completions": sum(r["validation_retry"] for r in decisions),
        "transport_retries": 0,
        "transport_retry_note": "Demo has no provider transport",
        "rejection_events": sum(reasons.values()),
        "rejection_reasons_normalized": dict(reasons),
        "validation_failure_events": sum(r["event"] == "validation_failure" for r in rows),
        "validation_failure_types": dict(
            Counter(r["failure_type"] for r in rows if r["event"] == "validation_failure")
        ),
        "theoretical_act_max_completions_per_agent_tick": 6,
    }
    return {
        "H1": {
            "unit": "characters, not tokens",
            "sections": section_summary(calls),
            "all_input_chars": sum(r["system_chars"] + r["prompt_chars"] for r in calls),
            "act_input_chars": sum(r["system_chars"] + r["prompt_chars"] for r in act),
        },
        "H2": h2,
        "H3": duplicate_summary(queries),
        "call_types": dict(Counter(r["call_type"] for r in calls)),
        "embedding_types": dict(Counter(r["call_type"] for r in rows if r["event"] == "embedding")),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/token_efficiency"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    cfg = build_company_config("s0_smoke")
    llm = TraceDemo(args.output / "demo_audit.jsonl")
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
    try:
        loop.run()
    finally:
        loop.close()
    events = [e for events, _, _ in recorder.ticks for e in events]
    semantic = {
        "ticks": [
            [
                [e.model_dump() for e in events],
                [[r.model_dump(), v] for r, v in records],
                retrievals,
            ]
            for events, records, retrievals in recorder.ticks
        ],
        "agents": [a.snapshot() for a in agents],
        "prompts": sorted(llm.requests),
        "embeds": sorted(llm.embeds),
    }
    rows = [json.loads(line) for line in llm.path.read_text().splitlines()]
    summary = analyze(rows, events)
    summary["method"] = {
        "backend": "unchanged DemoBackend",
        "scenario": "s0_smoke",
        "seed": cfg.random_seed,
        "agents": cfg.n_agents,
        "ticks": 32,
        "paid_api_calls": 0,
        "baseline_commit": "45893f2",
        "behavior_sha256": hashlib.sha256(
            json.dumps(semantic, sort_keys=True).encode()
        ).hexdigest(),
    }
    summary["comparison"] = [
        {
            "hypothesis": "H1",
            "recommendation": "MEASURE MORE",
            "observed_unit": "characters",
            "token_savings": None,
            "reason": "large fixed instructions; pruning risk and actual provider cache unknown",
        },
        {
            "hypothesis": "H2",
            "recommendation": "LOW PRIORITY",
            "observed_unit": "completion calls",
            "token_savings": None,
            "reason": "retry-tagged calls include first LLM calls after a non-LLM action",
        },
        {
            "hypothesis": "H3",
            "recommendation": "IMPLEMENT NEXT",
            "observed_unit": "query texts and single-text calls",
            "token_savings": None,
            "reason": "exact repeated model/text keys; existing cache is not wired to C16 runner",
        },
    ]
    summary["recommended_implementations"] = [
        {
            "priority": 1,
            "hypothesis": "H3",
            "change": "wire the existing exact model/text EmbedCache to the C16 runner",
            "scope": "cache query vectors, recompute retrieval rankings every time",
            "upper_bound_texts_avoided": summary["H3"]["duplicate_queries"],
            "caveat": "concurrent cold misses reduce benefit; paid-run benefit unmeasured",
        },
    ]
    (args.output / "hypothesis_analysis.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "H2": summary["H2"],
                "H3": {
                    k: v
                    for k, v in summary["H3"].items()
                    if k not in ("per_agent", "per_agent_tick")
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
