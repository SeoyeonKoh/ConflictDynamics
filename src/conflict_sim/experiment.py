"""Repeatable C-16 runner for C-14 company presets and C-15 scenarios."""

import argparse
import json
import logging
import os
import random
import shutil
import signal
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, wait
from contextvars import ContextVar
from pathlib import Path

from .agent import Agent
from .company_runtime import apply_initial_relationships, build_company_config
from .environment import Environment
from .frames import Frames
from .llm import (
    DemoBackend,
    EmbedCache,
    LLMError,
    SharedRateGate,
    attach_stop,
    is_paid,
    make_backend,
)
from .loop import Loop
from .models import Config
from .storage import (
    RunWriter,
    read_latest_checkpoint,
    read_memory,
    save_company_run,
    truncate_run,
    write_json,
)
from .stream import Stream
from .tape import ReplayMismatch, Tape, full_tape, truncate_tape

SCENARIOS = (
    "r10_enterprise_weekly",
    "s0_baseline",
    "s1_dependency_failure",
    "s2_deadline_pressure",
    "s3_resource_competition",
    "s4_evaluation_season",
    "i1_manager_clarification",
    "i2_deadline_adjustment",
    "i3_private_mediation",
    "p0_kickoff",  # temporary: kickoff allocation and results reviews
    "p0_documents",  # temporary: p0_kickoff with a document at the end of every task
    "p0_kickoff_ko",  # p0_kickoff in Korean: Korean personas, tasks and talk
    "p0_documents_ko",  # p0_documents in Korean
    "r10_documents_ko",  # p0_documents_ko on ten agents in one day, for repeated tests
    "r10_human",  # r10_documents_ko with the human prompt style
    "p0_human",  # p0_documents with the human prompt style, in English
    "r10_midweek",  # r10_human as one day of a project already under way
    "r10_auth_scoped",  # approval delegation baseline (scoped delegation, r10_human control)
    "r10_auth_single",  # approval delegation variant S (single approver HDS-001)
    "r10_auth_cross",  # approval delegation variant M (multi/cross-delegated leads)
)

def all_scenarios() -> tuple[str, ...]:
    """The fixed scenarios, then the generated ones saved under conf/."""
    from . import company_runtime

    folder = company_runtime.CONF_DIR / "scenario" / "company_c15"
    return (*SCENARIOS, *sorted(p.stem for p in folder.glob("gen_*.yaml")))


RETRIEVAL_CALL_TYPES = frozenset({"memory_retrieval_embedding", "reflection_retrieval_embedding"})


def retrieval_cached_backend(backend, path: Path):
    """Reuse query vectors only; memory write batches and every retrieval stay unchanged."""
    return EmbedCache(backend, path, call_types=RETRIEVAL_CALL_TYPES)


def estimate_calls(cfg) -> dict[str, int]:
    """Conservative planning bound, not a bill: completions vary with reactions and sessions."""
    ticks = cfg.max_days * (cfg.ticks_per_day + cfg.overtime_ticks_per_day)
    plans = cfg.n_agents * cfg.max_days
    actions = cfg.n_agents * ticks
    meetings = sum(
        len(meeting.participants) * meeting.duration_ticks for meeting in cfg.scenario.meetings
    )
    appraisals = meetings if cfg.relation_appraisal == "llm" else 0
    return {
        "plan_calls": plans,
        "max_action_calls": actions,
        "scheduled_meeting_turns": meetings,
        "max_appraisal_calls": appraisals,
        "upper_bound_completion_calls": plans + actions + meetings + appraisals,
    }


class RunStopped(Exception):
    """Asked to stop (SIGTERM from the server): the run pauses before its next tick."""

    def __str__(self) -> str:
        return "stopped"


def replay_config(saved: dict, *, max_total_tokens=None, workers=None, flex=None,
                  flex_fallback=None, claude_max_concurrent=None) -> Config:  # fmt: skip
    """A replayed resume runs on its saved config. The overrides kept are the ones the tape's
    request keys do not see (model, prompt and sampling are left as recorded): the budget
    (0 is no cap), the worker count, Claude's concurrency and Flex processing with its
    fallback. Validated like any config (workers=0 is refused, not copied in)."""
    update = {"max_total_tokens": max_total_tokens or None} if max_total_tokens is not None else {}
    transport = (("workers", workers), ("flex", flex), ("flex_fallback", flex_fallback),
                 ("claude_max_concurrent", claude_max_concurrent))  # fmt: skip
    update |= {k: v for k, v in transport if v is not None}
    return Config.model_validate(saved | update)


def run_scenario(
    scenario: str,
    run_dir: Path,
    *,
    backend: str = "demo",
    seed_offset: int = 0,
    pilot: bool = False,
    resume: bool = False,
    max_total_tokens: int | None = None,
    workers: int | None = None,
    live_port: int | None = None,
    retrieval_cache: bool = True,
    max_days: int | None = None,
    model_decide: str | None = None,
    model_speak: str | None = None,
    model_embed: str | None = None,
    embed_backend: str | None = None,
    claude_max_concurrent: int | None = None,
    tick_delay: float | None = None,
    stop: threading.Event | None = None,
    flex: bool | None = None,
    flex_fallback: bool | None = None,
    rate_gate: SharedRateGate | None = None,
) -> dict:
    """One run, journalled as it goes. A budget stop (`LLMError`) pauses at the last day-end
    checkpoint instead of failing; `resume=True` on the same run directory continues it."""
    if backend != "demo" and not pilot:
        raise PermissionError(
            f"{backend} execution requires --pilot before any repeated experiment"
        )
    if resume and not (run_dir / "paused.json").exists():
        raise FileNotFoundError(f"No paused run to resume: {run_dir}")
    if not resume and run_dir.exists():
        raise FileExistsError(f"Run directory already exists: {run_dir}")

    cfg = build_company_config(scenario, backend=backend)
    cfg = cfg.model_copy(update={"random_seed": cfg.random_seed + seed_offset})
    if max_total_tokens is not None:  # 0 is no cap
        cfg = cfg.model_copy(update={"max_total_tokens": max_total_tokens or None})
    if embed_backend == "openai" and model_embed is None:  # not the local model's name
        model_embed = OPENAI_EMBED_MODEL
    models = {"model_decide": model_decide, "model_speak": model_speak, "model_embed": model_embed,
              "embed_backend": embed_backend, "claude_max_concurrent": claude_max_concurrent}
    if any(v is not None for v in models.values()):
        cfg = Config.model_validate(cfg.model_dump() | {k: v for k, v in models.items() if v})
    if workers is not None:
        cfg = cfg.model_copy(update={"workers": workers})
    if flex is not None:  # OpenAI Flex processing; on by default (Config.flex)
        cfg = cfg.model_copy(update={"flex": flex})
    if flex_fallback is not None:  # Flex out of capacity: standard processing, or wait
        cfg = cfg.model_copy(update={"flex_fallback": flex_fallback})
    if max_days is not None:  # a shorter run than the scenario's, e.g. one day to look at
        cfg = cfg.model_copy(update={"max_days": max_days})
    tape_path = run_dir / "tape.sqlite"
    replay = resume and full_tape(tape_path)  # recorded from its first call: re-run from 0
    cut = None
    if replay:
        before = json.loads((run_dir / "paused.json").read_text(encoding="utf-8"))
        if before.get("replay") == "mismatch":
            raise ValueError(f"replay of {run_dir} did not match its tape: {before.get('reason')}")
        cut = before["tick"]
        saved = json.loads((run_dir / "resolved_config.json").read_text(encoding="utf-8"))
        # The saved config, so the replay asks what the tape recorded; what only changes how
        # calls travel (budget, parallelism, Flex) is still the caller's to set.
        cfg = replay_config(saved, max_total_tokens=max_total_tokens, workers=workers,
                            flex=flex, flex_fallback=flex_fallback,
                            claude_max_concurrent=claude_max_concurrent)  # fmt: skip
    elif resume and embed_backend is None:  # stored vectors compare only with their own model
        saved = json.loads((run_dir / "resolved_config.json").read_text(encoding="utf-8"))
        if saved.get("embed_backend"):
            cfg = Config.model_validate(cfg.model_dump() | {
                "embed_backend": saved["embed_backend"], "model_embed": saved["model_embed"]})
    # Decided on the final config (a resume runs on the saved one), before anything is moved.
    if is_paid(backend, cfg.embed_backend) and os.getenv("ALLOW_PAID_API_EXPERIMENTS") != "1":
        raise PermissionError("BLOCKED: user cost approval (ALLOW_PAID_API_EXPERIMENTS=1)")
    if replay:
        truncate_tape(tape_path, keep_below_tick=cut)
        _set_aside(run_dir)  # back if the tape turns out not to match
    restore = resume and not replay
    if resume:
        if restore:
            _, checkpoint = read_latest_checkpoint(run_dir)  # none: rerun into a new directory
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        manifest["status"] = "running"
        if replay:  # a run killed mid-replay still knows where its tape ends (live._settle)
            manifest["replay_cut"] = max(cut, manifest.get("replay_cut") or 0)
        # Continue the saved policy; old runs had no retrieval cache.
        retrieval_cache = manifest.get("retrieval_cache", {}).get("enabled", False)
    else:
        run_dir.mkdir(parents=True)
        write_json(run_dir / "resolved_config.json", cfg.model_dump())
        manifest = {
            "scenario": scenario,
            "seed": cfg.random_seed,
            "backend": backend,
            "model_id": cfg.model_decide if backend != "demo" else "demo",
            "llm": _llm_record(cfg),
            "git_commit": _git_commit(),
            "estimated_calls": estimate_calls(cfg),
            "status": "running",
        }
    cache_path = (
        Path.cwd() / cfg.embed_cache if cfg.embed_cache else run_dir / "retrieval_cache.sqlite"
    )
    if resume and manifest.get("retrieval_cache", {}).get("path"):
        cache_path = Path(manifest["retrieval_cache"]["path"])
    manifest["retrieval_cache"] = {
        "enabled": retrieval_cache,
        "path": str(cache_path.resolve()) if retrieval_cache else None,
        "call_types": sorted(RETRIEVAL_CALL_TYPES),
        "key": "model + exact text",
    }
    write_json(run_dir / "manifest.json", manifest)

    if backend == "demo":
        llm = DemoBackend(
            blocked_nudge_ticks=cfg.blocked_nudge_ticks,
            blocked_report_ticks=cfg.blocked_report_ticks,
        )
        usage = None
    else:
        llm = make_backend(cfg, Path.cwd() / ".env", audit_path=run_dir / "llm_audit.jsonl",
                           rate_gate=rate_gate)  # fmt: skip
        usage = llm.usage
    raw = llm  # the backend itself, before the caches and the tape wrap it
    attach_stop(raw, stop)  # a stop ends a 429/Flex wait at once, not after a minute's backoff

    if retrieval_cache:
        llm = retrieval_cached_backend(llm, cache_path)
    tape = None  # a run resumed from a checkpoint has no tape from tick 0: it records none
    if not restore:
        llm = tape = Tape(llm, tape_path, replay_until=cut, fresh=not resume)  # outermost
    agents = [Agent(spec, cfg, llm) for spec in cfg.agents]
    apply_initial_relationships(agents)
    env = Environment(cfg.environment, cfg.agents)
    if restore:
        truncate_run(run_dir, keep_below_tick=checkpoint["tick"])
    writer = RunWriter(run_dir)
    loop = Loop(cfg, agents, env, llm, random.Random(cfg.random_seed), writer)
    frames = Frames(cfg, run_dir.name)
    stream = None
    status = "failed"
    mismatched = False
    try:
        if restore:
            loop.restore(checkpoint, read_memory(run_dir))
        (run_dir / "paused.json").unlink(missing_ok=True)
        # The viewer journal (frames.jsonl, inspect.jsonl) is written tick by tick for replay.
        stream = Stream(
            run_dir / "frames.jsonl", frames.hello(loop.viewer_snapshot()),
            resume_tick=loop.tick_now if restore else None, delay=tick_delay or 0,
        )  # fmt: skip
        if usage is not None:  # a paid backend: the viewer shows spent tokens against the cap
            stream.budget = cfg.max_total_tokens or 0
        stream.publish([], frames.inspect(loop.viewer_snapshot()))

        said: list[str] = []  # subscription-limit warnings already shown

        def publish_tick(world, events, retrievals):
            stream.publish(*frames.capture(world.viewer_snapshot(), events, retrievals), usage)
            if stream.state != "running":  # a running status: a paused one reads as stopped
                return
            for warning in getattr(raw, "warnings", [])[len(said):]:
                said.append(warning)
                stream.status("running", warning, usage)

        loop.on_tick = publish_tick
        if replay:
            stream.status("replaying", str(cut))

        def at_tick():
            if tape is not None:
                tape.tick = loop.tick_now
            if replay and loop.tick_now == cut:
                shutil.rmtree(run_dir / ASIDE, ignore_errors=True)  # the replay matched
                stream.status("running")

        hooks = [at_tick]
        if live_port is not None:  # the viewer's live mode: watch, pause and step the engine
            if stop is not None:
                stream.interrupt = stop.is_set
                stop.wake = stream.wake  # the SIGTERM handler wakes a paused engine
            replaying = lambda: tape is not None and tape.replaying  # noqa: E731
            hooks.append(lambda: None if replaying() else stream.before_tick())
            print(f"Viewer WebSocket: ws://127.0.0.1:{stream.start(live_port)}", flush=True)
        if stop is not None:  # last: a stop that ended a paused wait lands here
            hooks.append(lambda: _stop_check(stop))
        loop.before_tick = lambda: [hook() for hook in hooks]
        if backend == "claude" and cfg.environment is not None:
            # An embedder that cannot load (the local model downloads on first use) pauses the
            # run here: after the viewer port is open, before tick 0, with the reason on screen.
            if stream.state == "running":  # replaying or paused statuses keep their meaning
                notice = "임베딩 모델을 준비합니다 (처음 한 번은 내려받습니다)."
                stream.status("running", notice, usage)
            raw.embed(["probe"])
        result = loop.run()
        save_company_run(
            run_dir / "corpus",
            cfg,
            loop.threads,
            loop.sessions,
            ticks=result.ticks,
            days=result.days,
            usage=usage,
        )
        summary = _summary(loop, result, usage)
        write_json(run_dir / "summary.json", summary)
        write_json(
            run_dir / "measurement_status.json",
            {
                "craft": "pending_optional_observer_run",
                "generation_feedback": False,
                "command": f"conflict-score {run_dir / 'corpus'}",
            },
        )
        stream.status("completed", "Run completed", usage)
        status = "completed"
        return summary
    except (LLMError, ValueError, RunStopped) as exc:  # a budget stop, a bad reply, a stop
        days = sorted(int(p.stem[4:]) for p in (run_dir / "checkpoints").glob("day-*.json"))
        tick = max(loop.tick_now, cut or 0)  # stopped while replaying: keep the whole tape
        paused = {"status": "paused", "reason": str(exc), "tick": tick,
                  "checkpoint": days[-1] if days else None}  # fmt: skip
        if isinstance(exc, ReplayMismatch):  # the tape cannot rebuild this run: keep what it had
            paused["replay"] = "mismatch"
            mismatched = True
        write_json(run_dir / "paused.json", paused)
        if stream is not None:
            stream.status("paused", str(exc), usage)
        status = "paused"
        return {"run_status": "paused", **paused, "token_usage": usage}
    except BaseException as exc:
        if stream is not None:
            try:
                stream.status("failed", str(exc), usage)
            except OSError:
                pass
        raise
    finally:
        loop.close()
        if loop.pool is not None:  # judgement threads may still hold the tape and the cache
            loop.pool.shutdown(wait=True, cancel_futures=True)
        if tape is not None:
            tape.close()
        elif isinstance(llm, EmbedCache):
            llm.close()
        writer.close()
        if stream is not None:
            stream.close()
        if mismatched:
            _put_back(run_dir)
        manifest["status"] = status
        manifest["token_usage"] = usage
        if "llm" in manifest:  # what the CLI reported once it ran
            for key in ("auth", "cli_version"):
                if getattr(raw, key, None):
                    manifest["llm"][key] = getattr(raw, key)
        # Each resumed segment has its own backend, so usage is kept per segment.
        manifest.setdefault("token_usage_segments", []).append(usage)
        write_json(run_dir / "manifest.json", manifest)


OPENAI_EMBED_MODEL = "text-embedding-3-small"  # the OpenAI runs' own default (company_runtime)


def _llm_record(cfg: Config) -> dict:
    """How a run called its model: provider, embeddings, and what the Claude route cannot send
    or keep out (temperature; the CLI's own account, environment and date context)."""
    record = {"provider": cfg.backend, "embed_backend": cfg.embed_backend,
              "embed_model": cfg.model_embed, "temperature_sent": cfg.backend != "claude",
              "injected_context": cfg.backend == "claude"}  # fmt: skip
    if cfg.backend == "claude":
        from importlib.metadata import PackageNotFoundError, version

        try:
            record["sdk_version"] = version("claude-agent-sdk")
        except PackageNotFoundError:
            record["sdk_version"] = None
        record |= {"cli_version": None, "auth": None}
    return record


def _summary(loop, result, usage) -> dict:
    events = []
    path = loop.writer.run_dir / "events.jsonl"
    if path.exists():
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return {
        "label": "INTEGRATION SMOKE TEST" if loop.cfg.scenario.id == "s0_smoke" else "DRY RUN",
        "agents": len(loop.agents),
        "days": result.days,
        "ticks": result.ticks,
        "tasks": {task.id: task.snapshot() for task in loop.env.org.tasks.values()},
        "sessions": len(loop.sessions),
        "blocked_events": sum(
            event["kind"] == "task" and event["payload"].get("change") == "blocked"
            for event in events
        ),
        "unblocked_events": sum(
            event["kind"] == "task" and event["payload"].get("change") in {"ready", "unblocked"}
            for event in events
        ),
        "rejected_actions": sum(event["kind"] == "rejected" for event in events),
        "overtime_events": sum(event["kind"] == "overtime" for event in events),
        "stress": {agent.name: agent.state.stress for agent in loop.agents},
        "workload": {agent.name: agent.state.workload for agent in loop.agents},
        "overtime_ticks": {agent.name: agent.state.overtime_ticks for agent in loop.agents},
        "relations": {
            agent.name: {
                other: relation.relation for other, relation in agent.state.relations.items()
            }
            for agent in loop.agents
        },
        "token_usage": usage,
        "run_status": "completed",
    }


DERIVED = ("events.jsonl", "frames.jsonl", "inspect.jsonl", "memory.sqlite", "memory.sqlite-wal",
           "memory.sqlite-shm", "summary.json", "measurement_status.json")  # fmt: skip


ASIDE = ".before-replay"


def _set_aside(run_dir: Path) -> None:
    """A replayed run rebuilds everything from its tape; what it had waits in ASIDE until the
    replay reaches its cut. An earlier replay killed midway left ASIDE already: keep that one."""
    aside = run_dir / ASIDE
    keep = not aside.exists()
    aside.mkdir(exist_ok=True)
    for name in (*DERIVED, "checkpoints", "corpus"):
        path = run_dir / name
        if not path.exists():
            continue
        if keep:
            path.rename(aside / name)
        elif path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def _put_back(run_dir: Path) -> None:
    """The tape did not match: drop the partial rebuild and restore what the run had."""
    aside = run_dir / ASIDE
    for path in aside.iterdir():
        target = run_dir / path.name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        path.rename(target)
    aside.rmdir()


def _stop_check(stop: threading.Event) -> None:
    if stop.is_set():
        raise RunStopped


def _git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run or dry-run C-16 company experiments")
    names = (*all_scenarios(), "s0_smoke")
    parser.add_argument("scenario", nargs="?", choices=names)
    parser.add_argument("--scenarios", nargs="+", choices=names, metavar="SCENARIO",
                        help="several scenarios in one process (see --parallel-runs)")
    parser.add_argument("--parallel-runs", type=int, default=1,
                        help="runs at once in this process (with --scenarios or --replicates)")
    parser.add_argument("--max-in-flight", type=int,
                        help="API calls at once across all runs here; a 429 holds them all off")
    parser.add_argument("--output-root", type=Path, default=Path("runs/c16"))
    parser.add_argument("--backend", choices=("demo", "openai", "claude"), default="demo")
    parser.add_argument("--replicates", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--resume", action="store_true", help="continue paused replicates")
    parser.add_argument("--max-total-tokens", type=int, help="run token cap (OpenAI); 0 is none")
    parser.add_argument("--model-decide", help="judgement model (OpenAI)")
    parser.add_argument("--model-speak", help="speech model (OpenAI)")
    parser.add_argument("--model-embed", help="embedding model (OpenAI or local)")
    parser.add_argument("--embed-backend", choices=("openai", "local"),
                        help="where a claude run's embeddings come from")
    parser.add_argument("--claude-max-concurrent", type=int,
                        help="Claude CLI processes at once (claude backend)")
    parser.add_argument("--tick-delay", type=float,
                        help="seconds between live ticks (default 1 for a live demo, else 0)")
    parser.add_argument("--workers", type=int, help="parallel LLM judgements per tick")
    parser.add_argument("--days", type=int, help="run this many days instead of the scenario's")
    parser.add_argument("--live-port", type=int, help="serve the live viewer on this port")
    parser.add_argument(
        "--no-retrieval-cache", action="store_true", help="disable exact query reuse"
    )
    parser.add_argument("--flex", type=int, choices=(0, 1),
                        help="OpenAI Flex processing at half price (default 1); 0 turns it off")
    parser.add_argument("--no-flex", dest="flex", action="store_const", const=0,
                        help="the same as --flex 0")  # fmt: skip
    parser.add_argument("--flex-fallback", type=int, choices=(0, 1),
                        help="Flex out of capacity: 1 retries on standard processing (default), "
                             "0 waits for Flex")  # fmt: skip
    parser.add_argument("--no-flex-fallback", dest="flex_fallback", action="store_const", const=0,
                        help="the same as --flex-fallback 0")  # fmt: skip
    args = parser.parse_args(argv)
    if (args.scenario is None) == (args.scenarios is None):
        parser.error("name one scenario, or several with --scenarios")
    if args.scenarios is not None or args.parallel_runs != 1 or args.max_in_flight is not None:
        return _main_many(args)
    if not 1 <= args.replicates <= 3:
        raise SystemExit("replicates must be between 1 and 3")
    if args.backend != "demo" and (not args.pilot or args.replicates != 1):
        raise SystemExit(f"{args.backend} is limited to one --pilot run")
    cfg = build_company_config(args.scenario, backend=args.backend)
    if args.flex is not None:
        cfg = cfg.model_copy(update={"flex": bool(args.flex)})
    if args.flex_fallback is not None:
        cfg = cfg.model_copy(update={"flex_fallback": bool(args.flex_fallback)})
    if args.dry_run:
        print(
            json.dumps(
                {"config": cfg.model_dump(), "estimated_calls": estimate_calls(cfg)}, indent=2
            )
        )
        return
    stop = threading.Event()
    def on_term(*_):
        stop.set()
        getattr(stop, "wake", lambda: None)()

    signal.signal(signal.SIGTERM, on_term)
    for replicate in range(args.replicates):
        run_dir = args.output_root / args.scenario / f"replicate-{replicate + 1}"
        if args.resume and not (run_dir / "paused.json").exists():
            continue
        summary = run_scenario(
            args.scenario,
            run_dir,
            backend=args.backend,
            seed_offset=replicate,
            pilot=args.pilot,
            resume=args.resume,
            max_total_tokens=args.max_total_tokens,
            workers=args.workers,
            live_port=args.live_port,
            retrieval_cache=not args.no_retrieval_cache,
            max_days=args.days,
            model_decide=args.model_decide,
            model_speak=args.model_speak,
            model_embed=args.model_embed,
            embed_backend=args.embed_backend,
            claude_max_concurrent=args.claude_max_concurrent,
            flex=None if args.flex is None else bool(args.flex),
            flex_fallback=None if args.flex_fallback is None else bool(args.flex_fallback),
            stop=stop,
            tick_delay=args.tick_delay if args.tick_delay is not None else (
                1.0 if args.live_port is not None and args.backend == "demo" else 0
            ),
        )
        print(json.dumps({"run": str(run_dir), "summary": summary}, ensure_ascii=False))


RUN_LABEL: ContextVar[str] = ContextVar("run_label", default="")


class _RunLabel(logging.Filter):
    """Prefix each log line with the run it came from, when several share one process."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.run = RUN_LABEL.get() or "-"
        return True


def _run_kwargs(args) -> dict:
    """run_scenario's options from the command line, the same for every run of a call."""
    return dict(
        backend=args.backend, pilot=args.pilot, max_total_tokens=args.max_total_tokens,
        workers=args.workers, retrieval_cache=not args.no_retrieval_cache, max_days=args.days,
        model_decide=args.model_decide, model_speak=args.model_speak,
        model_embed=args.model_embed, embed_backend=args.embed_backend,
        claude_max_concurrent=args.claude_max_concurrent,
        flex=None if args.flex is None else bool(args.flex),
        flex_fallback=None if args.flex_fallback is None else bool(args.flex_fallback),
        tick_delay=args.tick_delay or 0,
    )  # fmt: skip


def _what_to_do(run_dir: Path, resume: bool) -> tuple[str, str]:
    """For a run of a batch, what to do and why: "resume" a paused one (with --resume),
    "start" a missing one, or "skip": finished, paused without --resume, or a directory with
    neither a summary nor a pause (killed hard: see it before running it again)."""
    if (run_dir / "paused.json").exists():
        return ("resume", "") if resume else ("skip", "paused; continue it with --resume")
    if not run_dir.exists():
        return "start", ""
    if (run_dir / "summary.json").exists():
        return "skip", "finished"
    return "skip", "exists with no summary.json or paused.json (stopped hard?)"


def run_batch(jobs: list[tuple[str, Path, int]], *, parallel: int, resume: bool,
              kwargs: dict, stops: list[threading.Event] | None = None,
              rate_gate: SharedRateGate | None = None) -> list[dict]:  # fmt: skip
    """Several runs in one process, `parallel` at a time, sharing `rate_gate`. Each run gets
    its own stop event (appended to `stops`, for a signal handler to set): one run's error is
    that run's result, never the others'. The batch's own event goes in `stops` first, so a
    stop also keeps queued runs from starting. Results in the order of `jobs`."""
    stops = [] if stops is None else stops
    cancelled = threading.Event()  # set by stop_all with the rest: queued runs never start
    stops.insert(0, cancelled)

    def one(scenario: str, run_dir: Path, replicate: int) -> dict:
        RUN_LABEL.set(f"{scenario}/{run_dir.name}")
        if cancelled.is_set():
            return {"run": str(run_dir), "skipped": "stopped before it started"}
        what, why = _what_to_do(run_dir, resume)
        if what == "skip":
            return {"run": str(run_dir), "skipped": why}
        stop = threading.Event()
        stops.append(stop)
        if cancelled.is_set():  # a stop that came between the check above and the append
            stop.set()
        try:
            summary = run_scenario(scenario, run_dir, seed_offset=replicate,
                                   resume=what == "resume", stop=stop, rate_gate=rate_gate,
                                   **kwargs)  # fmt: skip
            return {"run": str(run_dir), "summary": summary}
        except Exception as exc:  # noqa: BLE001 - one run's failure is reported, not shared
            logging.getLogger(__name__).exception("run %s failed", run_dir)
            return {"run": str(run_dir), "error": f"{type(exc).__name__}: {exc}"}

    pool = ThreadPoolExecutor(max(1, parallel), thread_name_prefix="run")
    try:
        futures = [pool.submit(one, *job) for job in jobs]
        while not all(f.done() for f in futures):  # a timed wait keeps signals deliverable
            wait(futures, timeout=0.5)
    except BaseException:  # a second Ctrl+C: do not wait for runs still pausing
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown(wait=True)
    return [f.result() for f in futures]


def stop_all(stops: list[threading.Event]) -> None:
    """Every running run pauses before its next tick (and a paused-waiting one wakes to do so)."""
    for stop in list(stops):
        stop.set()
        getattr(stop, "wake", lambda: None)()


def _overridden(cfg: Config, args) -> Config:
    """The config a run will use given the command line's overrides, as run_scenario applies
    them, so a --dry-run shows what would run."""
    update = {k: v for k, v in (
        ("flex", None if args.flex is None else bool(args.flex)),
        ("flex_fallback", None if args.flex_fallback is None else bool(args.flex_fallback)),
        ("workers", args.workers), ("max_days", args.days),
        ("claude_max_concurrent", args.claude_max_concurrent),
        ("model_decide", args.model_decide), ("model_speak", args.model_speak),
        ("model_embed", args.model_embed), ("embed_backend", args.embed_backend),
    ) if v is not None}  # fmt: skip
    if args.max_total_tokens is not None:
        update["max_total_tokens"] = args.max_total_tokens or None
    return Config.model_validate(cfg.model_dump() | update) if update else cfg


def _main_many(args) -> None:
    """Several runs in one process: --scenarios in replicate-major order (S, D, M, S, D, M...),
    `--parallel-runs` at a time, API calls capped by `--max-in-flight` and held off together
    after a 429. --resume continues the paused runs, starts the missing ones and skips the
    finished ones. SIGTERM, or a first Ctrl+C, pauses them all; a second Ctrl+C quits at once."""
    scenarios = args.scenarios or [args.scenario]
    if args.parallel_runs < 1:
        raise SystemExit("--parallel-runs must be at least 1")
    if args.max_in_flight is not None and args.max_in_flight < 1:
        raise SystemExit("--max-in-flight must be at least 1")
    if len(set(scenarios)) != len(scenarios):  # two runs would share one run directory
        raise SystemExit(f"--scenarios names a scenario twice: {' '.join(scenarios)}")
    if args.live_port is not None:
        raise SystemExit("--live-port serves one run; leave it out with several")
    if not 1 <= args.replicates <= 3:
        raise SystemExit("replicates must be between 1 and 3")
    if args.backend != "demo" and (not args.pilot or args.replicates != 1):
        raise SystemExit(f"{args.backend} is limited to one --pilot run per scenario")
    if args.dry_run:
        for name in scenarios:
            cfg = _overridden(build_company_config(name, backend=args.backend), args)
            print(json.dumps({"scenario": name, "config": cfg.model_dump(),
                              "estimated_calls": estimate_calls(cfg)}))  # fmt: skip
        return
    if is_paid(args.backend, args.embed_backend) and os.getenv("ALLOW_PAID_API_EXPERIMENTS") != "1":
        raise SystemExit("BLOCKED: user cost approval (ALLOW_PAID_API_EXPERIMENTS=1)")
    jobs = [(name, args.output_root / name / f"replicate-{r + 1}", r)
            for r in range(args.replicates) for name in scenarios]  # fmt: skip
    gate = SharedRateGate(args.max_in_flight) if args.max_in_flight is not None else None
    stops: list[threading.Event] = []
    interrupts = 0

    def on_signal(signum, _frame):
        nonlocal interrupts
        if signum == signal.SIGINT:
            interrupts += 1
            if interrupts > 1:  # the second Ctrl+C: no more waiting for a graceful pause
                signal.signal(signal.SIGINT, signal.default_int_handler)
                raise KeyboardInterrupt
        stop_all(stops)

    handler = logging.StreamHandler()
    handler.addFilter(_RunLabel())
    handler.setFormatter(logging.Formatter("[%(run)s] %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    level = root.level
    previous = {sig: signal.signal(sig, on_signal) for sig in (signal.SIGTERM, signal.SIGINT)}
    root.addHandler(handler)
    root.setLevel(logging.WARNING)
    try:
        results = run_batch(jobs, parallel=args.parallel_runs, resume=args.resume,
                            kwargs=_run_kwargs(args), stops=stops, rate_gate=gate)  # fmt: skip
    finally:  # the process may go on (tests, a caller): leave logging and signals as found
        root.removeHandler(handler)
        root.setLevel(level)
        for sig, old in previous.items():
            signal.signal(sig, old)
    for result in results:
        print(json.dumps(result, ensure_ascii=False))
    if gate is not None:
        print(json.dumps({"rate_gate": {"max_in_flight": gate.max_in_flight, "peak": gate.peak,
                                        "cooldowns": gate.cooldowns}}))  # fmt: skip
    if any("error" in r for r in results):
        raise SystemExit(1)


def console_main() -> None:
    """The command's entry: a KeyboardInterrupt (the second Ctrl+C of a batch) quits at once,
    instead of the interpreter joining run threads that are still pausing."""
    try:
        main()
    except KeyboardInterrupt:
        os._exit(130)


if __name__ == "__main__":
    console_main()
