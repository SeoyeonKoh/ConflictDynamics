"""Controlled H3 comparison. Defaults to demo; paid execution requires explicit approval.

Completions and memory writes are recorded in RAM in OFF and replayed in ON. Only query
embeddings are recomputed in ON. This isolates H3 from stochastic completion trajectories.
No raw prompts, generated responses or memory descriptions are persisted by this harness.
"""

import argparse
import json
import math
import os
import random
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path

from token_efficiency_analysis import Recorder, TraceDemo
from token_efficiency_h3_cache import digest, metrics

from conflict_sim.agent import Agent
from conflict_sim.company_runtime import apply_initial_relationships, build_company_config
from conflict_sim.environment import Environment
from conflict_sim.experiment import RETRIEVAL_CALL_TYPES, retrieval_cached_backend
from conflict_sim.llm import LLMError, OpenAIBackend, create_openai_client, strict_schema
from conflict_sim.loop import Loop
from conflict_sim.usage_audit import (
    audit_context,
    completion_metadata,
    current_context,
    log_call,
)


class BudgetStop(LLMError):
    pass


class Budget:
    """Conservative non-refundable reservations shared by both arms, including failed calls.

    UTF-8 bytes bound ordinary text tokens; 8192 tokens are reserved for the schema/envelope.
    Full output limit reserved, input charged at cache-write rate, no cached discount assumed.
    This is a client planning guard, not an authoritative provider billing cap.
    """

    def __init__(self, cap):
        self.cap = cap
        self.reserved = 0.0
        self.lock = threading.Lock()

    def reserve(self, input_bytes, output=0, embedding=False):
        amount = (
            (input_bytes + (0 if embedding else 8192)) * (0.02 if embedding else 0.125)
            + output * 0.50
        ) / 1e6
        with self.lock:
            if self.reserved + amount > self.cap:
                raise BudgetStop("Cost reservation cap reached before request")
            self.reserved += amount


class NoRetryOpenAI(OpenAIBackend):
    # Harness-only: avoid hidden SDK/transport retries and their unreserved charges.
    def _waiting_out_rate_limits(self, request):
        log_call("transport_attempt", call_count=1, transport_retry=False)
        return request()


class TapeBackend:
    def __init__(self, backend, path, tape, replay, budget=None):
        self.backend, self.audit_path = backend, path
        self.tape, self.replay, self.budget = tape, replay, budget
        self.model_embed = getattr(backend, "model_embed", "DemoBackend")
        self.counts = Counter()
        self.lock = threading.Lock()
        self.seconds = defaultdict(float)

    def key(self, kind):
        c = current_context()
        base = (
            kind,
            c.get("agent"),
            c.get("tick"),
            c.get("call_type"),
            c.get("action_retry", False),
            c.get("validation_retry", False),
        )
        with self.lock:
            number = self.counts[base]
            self.counts[base] += 1
        return base + (number,)

    def complete(self, **request):
        key = self.key("completion")
        signature = digest(
            {k: v.model_json_schema() if k == "schema" and v else v for k, v in request.items()}
        )
        start = time.perf_counter()
        if self.replay:
            expected, result = self.tape[key]
            if expected != signature:
                raise LLMError("Prompt/options diverged before replay; H3 comparison failed")
            log_call(
                "completion_replay",
                call_count=0,
                logical_call_count=1,
                **completion_metadata(request["system"], request["prompt"]),
            )
        else:
            if self.budget:
                schema = strict_schema(request["schema"]) if request.get("schema") else {}
                size = len((request["system"] + request["prompt"] + json.dumps(schema)).encode())
                self.budget.reserve(size, self.backend.output_limits[request["json_mode"]])
            result = self.backend.complete(**request)
            self.tape[key] = (signature, result)
        with self.lock:
            self.seconds["completion"] += time.perf_counter() - start
        return result

    def embed(self, texts):
        query = current_context().get("call_type") in RETRIEVAL_CALL_TYPES
        key = None if query else self.key("memory_write")
        signature = digest(texts)
        start = time.perf_counter()
        if self.replay and not query:
            expected, result = self.tape[key]
            if expected != signature:
                raise LLMError("Memory write input diverged before replay")
            log_call("embedding_replay", call_count=0, text_count=len(texts))
        else:
            if self.budget:
                self.budget.reserve(sum(len(t.encode()) for t in texts), embedding=True)
            result = self.backend.embed(texts)
            if not query:
                self.tape[key] = (signature, result)
        with self.lock:
            self.seconds["retrieval" if query else "memory_write"] += time.perf_counter() - start
        return result


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def total(records, field):
    values = [r.get(field) for r in records]
    return sum(values) if all(v is not None for v in values) else None


def efficiency(records, enabled, seconds, wall):
    result = metrics(records, enabled)
    completions = [r for r in records if r["event"] == "completion"]
    embeds = [r for r in records if r["event"] == "embedding"]
    query = [r for r in embeds if r["call_type"] in RETRIEVAL_CALL_TYPES]
    result |= {
        "api_requests_attempted": sum(r["event"] == "transport_attempt" for r in records),
        "logical_completion_calls": len(completions)
        + sum(r["event"] == "completion_replay" for r in records),
        "embedding_input_tokens": total(embeds, "input_tokens"),
        "retrieval_embedding_input_tokens": total(query, "input_tokens"),
        "completion_input_tokens": total(completions, "input_tokens"),
        "completion_output_tokens": total(completions, "output_tokens"),
        "completion_cached_tokens": total(completions, "cached_tokens"),
        "total_tokens": total(completions + embeds, "total_tokens"),
        "wall_seconds": wall,
        "backend_seconds": dict(seconds),
    }
    if not completions and enabled:
        result["completion_input_tokens"] = result["completion_output_tokens"] = 0
    priced = all(r.get("input_tokens") is not None for r in completions + embeds)
    result["actual_incremental_estimated_usd"] = (
        sum(
            (r["input_tokens"] - (r.get("cached_tokens") or 0)) * 0.10
            + (r.get("cached_tokens") or 0) * 0.01
            + r["output_tokens"] * 0.50
            for r in completions
        )
        / 1e6
        + sum(r["input_tokens"] * 0.02 for r in embeds) / 1e6
        if priced
        else None
    )
    return result


def behavioral(loop, states, recorder):
    events = [e.model_dump() for es, _, _ in recorder.ticks for e in es]
    tasks = [t.snapshot() for t in loop.env.org.tasks.values()]
    utterances = [u.model_dump() for thread in loop.threads.values() for u in thread.utterances]
    by_kind = Counter(e["kind"] for e in events)
    action_kinds = Counter(e["payload"].get("kind") for e in events if e["kind"] == "action")
    return {
        "tasks": [
            {
                k: t.get(k)
                for k in (
                    "owner",
                    "due",
                    "worked",
                    "done_tick",
                    "blocked_since",
                    "overdue",
                    "lifecycle",
                    "progress",
                    "status",
                )
            }
            for t in tasks
        ],
        "overdue_tasks": sum(t.get("overdue", False) for t in tasks),
        "completed_tasks": sum(t.get("lifecycle") == "done" for t in tasks),
        "blocked_task_ticks": sum(
            sum(t.get("status") == "blocked" for t in s["env"]["org"]["tasks"].values())
            for s in states
        ),
        "ignored_requests": sum(bool(e["payload"].get("ignored")) for e in events),
        "refused_requests": sum(bool(e["payload"].get("refused")) for e in events),
        "escalation_report_actions": action_kinds["report"],
        "message_actions": sum(action_kinds[k] for k in ("message", "gossip", "report")),
        "structural_events": {kind: by_kind[kind] for kind in ("shock", "task", "evaluation")},
        "social_trajectory": [
            {
                "tick": s["tick"] - 1,
                "agents": {
                    name: {
                        key: row["state"].get(key, 0)
                        for key in ("stress", "mood", "workload", "overtime_ticks")
                    }
                    for name, row in s["agents"].items()
                },
                "relationships_sha256": digest(
                    {name: row["state"]["relations"] for name, row in s["agents"].items()}
                ),
            }
            for s in states
        ],
        "sessions": len(loop.sessions),
        "utterances": len(utterances),
        "average_session_utterances": len(utterances) / len(loop.sessions) if loop.sessions else 0,
        "event_counts": dict(by_kind),
        "action_counts": dict(action_kinds),
        "agent_state": {
            a.name: {k: v for k, v in a.snapshot()["state"].items() if k != "relations"}
            for a in loop.agents
        },
        "relationships": {
            a.name: {
                name: {
                    "relation": r.relation,
                    "familiarity": r.familiarity,
                    "task_trust": r.task_trust,
                    "grievance_count": len(r.grievances),
                }
                for name, r in a.state.relations.items()
            }
            for a in loop.agents
        },
        "overtime_ticks": {a.name: a.state.overtime_ticks for a in loop.agents},
        "trajectories_sha256": digest(states),
        "events_sha256": digest(events),
        "utterances_sha256": digest(utterances),
    }


def run_arm(cfg, output, backend_name, tape, enabled, ticks, budget):
    output.mkdir(parents=True, exist_ok=False)
    path = output / "audit.jsonl"
    if backend_name == "demo":
        raw = TraceDemo(path)
        raw.model_embed = "DemoBackend"
    else:
        raw = NoRetryOpenAI(
            create_openai_client(Path.cwd() / ".env").with_options(max_retries=0),
            model_embed=cfg.model_embed,
            reasoning_effort=cfg.reasoning_effort,
            max_tokens_decide=cfg.max_tokens_decide,
            max_tokens_speak=cfg.max_tokens_speak,
            max_total_tokens=cfg.max_total_tokens,
            max_input_chars=cfg.max_input_chars,
            audit_path=path,
        )
    wrapped = TapeBackend(raw, path, tape, enabled, budget)
    llm = retrieval_cached_backend(wrapped, output / "query_cache.sqlite") if enabled else wrapped
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
    loop.on_tick = lambda world, es, rs: states.append(json.loads(json.dumps(world.checkpoint())))
    start = time.perf_counter()
    status = "completed"
    error = None
    try:
        with audit_context(audit_path=path):
            loop.run_until(ticks - 1)
    except (LLMError, ValueError, KeyError) as exc:
        status, error = "stopped", type(exc).__name__
    finally:
        loop.close()
        if loop.pool:
            loop.pool.shutdown(wait=True, cancel_futures=True)
        if enabled:
            llm.close()
    records = rows(path)
    lookups = {}
    for row in records:
        if row["event"] == "embedding_cache":
            for item in row["lookup_text_metrics"]:
                lookups[(row["agent"], row["tick"], item["sha256"])] = row
        elif row["event"] == "retrieval_result":
            lookup = lookups.get((row["agent"], row["tick"], row["query_sha256"]))
            row["cache_status"] = ("hit" if lookup["cache_hits"] else "miss") if lookup else "off"
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    result = {
        "status": status,
        "error_type": error,
        "completed_ticks": len(states),
        "efficiency": efficiency(records, enabled, wrapped.seconds, time.perf_counter() - start),
        "behavior": behavioral(loop, states, recorder),
    }
    (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def indexed(records, event):
    counts, result = Counter(), {}
    for r in records:
        if r["event"] not in event:
            continue
        base = (r.get("agent"), r.get("tick"), r.get("call_type"), r.get("query_sha256"))
        n = counts[base]
        counts[base] += 1
        result[base + (n,)] = r
    return result


def compare_metadata(off, on):
    checks = {}
    for name, events, fields in (
        (
            "retrieval",
            {"retrieval_result"},
            [
                "embedding_model",
                "vector_sha256",
                "scoring_context_sha256",
                "ranked_ids",
                "selected_ids",
                "scores",
                "result_sha256",
            ],
        ),
        (
            "prompt",
            {"completion", "completion_replay"},
            ["system_sha256", "payload_sha256", "combined_prompt_sha256"],
        ),
    ):
        a, b = indexed(off, events), indexed(on, events)
        mismatches = [
            list(k) for k in a.keys() & b.keys() if any(a[k].get(f) != b[k].get(f) for f in fields)
        ]
        checks[name] = {
            "off_count": len(a),
            "on_count": len(b),
            "missing_keys": len(a.keys() ^ b.keys()),
            "mismatch_keys": mismatches,
            "identical": bool(a) and a.keys() == b.keys() and not mismatches,
        }
    return checks


def paired(output, *, backend="demo", ticks=8, workers=4, approved=False, cost_cap=0.5):
    if not 1 <= ticks <= 32 or workers < 1 or not math.isfinite(cost_cap) or cost_cap <= 0:
        raise ValueError("ticks 1..32, workers >=1 and positive cost cap required")
    # This is checked before directory creation or constructing an OpenAI client.
    if backend == "openai" and (not approved or os.getenv("ALLOW_PAID_API_EXPERIMENTS") != "1"):
        raise PermissionError("Explicit user approval and paid-run environment gate required")
    cfg = build_company_config("s0_smoke", backend=backend).model_copy(update={"workers": workers})
    if backend == "openai" and (
        cfg.model_decide != "gpt-6-luna"
        or cfg.model_speak != "gpt-6-luna"
        or cfg.model_embed != "text-embedding-3-small"
    ):
        raise ValueError("Reverify pricing for these models before paid execution")
    output.mkdir(parents=True, exist_ok=False)
    budget = Budget(cost_cap) if backend == "openai" else None
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "backend": backend,
                "ticks": ticks,
                "config_sha256": digest(cfg.model_dump()),
                "config": cfg.model_dump(),
                "cache_off": False,
                "cache_on": True,
                "cold_isolated_cache": True,
                "mode": "frozen_completion_and_memory_write_replay",
                "cost_reservation_cap_usd": cost_cap,
                "approved": approved,
                "raw_tape_persisted": False,
            },
            indent=2,
        )
    )
    tape = {}
    off = run_arm(cfg, output / "off", backend, tape, False, ticks, budget)
    on = (
        run_arm(cfg, output / "on", backend, tape, True, ticks, budget)
        if off["status"] == "completed"
        else None
    )
    checks = (
        compare_metadata(rows(output / "off/audit.jsonl"), rows(output / "on/audit.jsonl"))
        if on
        else None
    )
    result = {
        "off": off,
        "on": on,
        "equality": checks,
        "reserved_usd": budget.reserved if budget else 0,
        "paid_api_executed": backend == "openai"
        and bool(
            off["efficiency"]["api_requests_attempted"]
            + (on["efficiency"]["api_requests_attempted"] if on else 0)
        ),
        "success": bool(
            on
            and on["status"] == "completed"
            and all(c["identical"] for c in checks.values())
            and off["behavior"] == on["behavior"]
        ),
    }
    if on:
        # Counterfactual full-pipeline accounting, clearly separate from actual paid replay.
        before, after = off["efficiency"], on["efficiency"]
        normalized = dict(after)
        for field in (
            "completions",
            "completion_input_tokens",
            "completion_output_tokens",
            "completion_cached_tokens",
            "memory_write_requests",
            "memory_write_texts",
        ):
            normalized[field] = before[field]
        normalized["all_embedding_requests"] = (
            before["memory_write_requests"] + after["retrieval_embedding_requests"]
        )
        normalized["all_embedding_texts"] = (
            before["memory_write_texts"] + after["retrieval_embedding_texts"]
        )
        for field in ("embedding_input_tokens", "total_tokens"):
            x, old, new = (
                before[field],
                before["retrieval_embedding_input_tokens"],
                after["retrieval_embedding_input_tokens"],
            )
            normalized[field] = x - old + new if all(v is not None for v in (x, old, new)) else None
        old, new = (
            before["retrieval_embedding_input_tokens"],
            after["retrieval_embedding_input_tokens"],
        )
        normalized["counterfactual_estimated_usd"] = (
            (before["actual_incremental_estimated_usd"] + (new - old) * 0.02 / 1e6)
            if old is not None and new is not None
            else None
        )
        normalized["label"] = (
            "counterfactual: baseline completion/write usage + measured ON query usage"
        )
        result["counterfactual_on_efficiency"] = normalized
        lines = [
            "# Controlled H3 Comparison",
            "",
            "| Metric | OFF | ON counterfactual | Change |",
            "|---|---:|---:|---:|",
        ]
        for field in (
            "retrieval_queries",
            "retrieval_embedding_requests",
            "all_embedding_requests",
            "all_embedding_texts",
            "embedding_input_tokens",
            "cache_hits",
            "cache_misses",
            "logical_completion_calls",
            "completion_input_tokens",
            "completion_output_tokens",
            "total_tokens",
        ):
            a, b = before[field], normalized[field]
            delta = (
                b - a if isinstance(a, (int, float)) and isinstance(b, (int, float)) else "unknown"
            )
            lines.append(f"| {field} | {a} | {b} | {delta} |")
        lines += [
            "",
            "Completion/write usage in ON is reused, not independently measured.",
            "Latency and actual incremental paid usage are separate fields in comparison.json.",
        ]
        (output / "comparison.md").write_text("\n".join(lines) + "\n")
    (output / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=("demo", "openai"), default="demo")
    parser.add_argument("--ticks", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--user-approved-paid-run", action="store_true")
    parser.add_argument("--cost-cap-usd", type=float, default=0.5)
    parser.add_argument("--compare-only", action="store_true")
    args = parser.parse_args()
    if args.compare_only:
        checks = compare_metadata(
            rows(args.output / "off/audit.jsonl"), rows(args.output / "on/audit.jsonl")
        )
        print(json.dumps(checks, indent=2))
        if not all(check["identical"] for check in checks.values()):
            raise SystemExit(1)
        return
    result = paired(
        args.output,
        backend=args.backend,
        ticks=args.ticks,
        workers=args.workers,
        approved=args.user_approved_paid_run,
        cost_cap=args.cost_cap_usd,
    )
    print(
        json.dumps({"success": result["success"], "paid_api_executed": result["paid_api_executed"]})
    )
    if not result["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
