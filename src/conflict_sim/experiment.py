"""Repeatable C-16 runner for C-14 company presets and C-15 scenarios."""

import argparse
import json
import os
import random
import subprocess
from pathlib import Path

from .agent import Agent
from .company_runtime import apply_initial_relationships, build_company_config
from .environment import Environment
from .frames import Frames
from .llm import DemoBackend, LLMError, OpenAIBackend, create_openai_client
from .loop import Loop
from .storage import (
    RunWriter,
    read_latest_checkpoint,
    read_memory,
    save_company_run,
    truncate_run,
    write_json,
)
from .stream import Stream

SCENARIOS = (
    "s0_baseline",
    "s1_dependency_failure",
    "s2_deadline_pressure",
    "s3_resource_competition",
    "s4_evaluation_season",
    "i1_manager_clarification",
    "i2_deadline_adjustment",
    "i3_private_mediation",
    "p0_kickoff",  # temporary: kickoff allocation and results reviews
)


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
) -> dict:
    """One run, journalled as it goes. A budget stop (`LLMError`) pauses at the last day-end
    checkpoint instead of failing; `resume=True` on the same run directory continues it."""
    if backend == "openai":
        if os.getenv("ALLOW_PAID_API_EXPERIMENTS") != "1":
            raise PermissionError("BLOCKED: user cost approval (ALLOW_PAID_API_EXPERIMENTS=1)")
        if not pilot:
            raise PermissionError(
                "OpenAI execution requires --pilot before any repeated experiment"
            )
    if resume and not (run_dir / "paused.json").exists():
        raise FileNotFoundError(f"No paused run to resume: {run_dir}")
    if not resume and run_dir.exists():
        raise FileExistsError(f"Run directory already exists: {run_dir}")

    cfg = build_company_config(scenario, backend=backend)
    cfg = cfg.model_copy(update={"random_seed": cfg.random_seed + seed_offset})
    if max_total_tokens is not None:
        cfg = cfg.model_copy(update={"max_total_tokens": max_total_tokens})
    if workers is not None:
        cfg = cfg.model_copy(update={"workers": workers})
    if resume:
        _, checkpoint = read_latest_checkpoint(run_dir)  # none yet: rerun into a new directory
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        manifest["status"] = "running"
    else:
        run_dir.mkdir(parents=True)
        write_json(run_dir / "resolved_config.json", cfg.model_dump())
        manifest = {
            "scenario": scenario,
            "seed": cfg.random_seed,
            "backend": backend,
            "model_id": cfg.model_decide if backend == "openai" else "demo",
            "git_commit": _git_commit(),
            "estimated_calls": estimate_calls(cfg),
            "status": "running",
        }
    write_json(run_dir / "manifest.json", manifest)

    if backend == "demo":
        llm = DemoBackend(
            blocked_nudge_ticks=cfg.blocked_nudge_ticks,
            blocked_report_ticks=cfg.blocked_report_ticks,
        )
        usage = None
    else:
        llm = OpenAIBackend(
            create_openai_client(Path.cwd() / ".env"),
            model_embed=cfg.model_embed,
            reasoning_effort=cfg.reasoning_effort,
            max_tokens_decide=cfg.max_tokens_decide,
            max_tokens_speak=cfg.max_tokens_speak,
            max_total_tokens=cfg.max_total_tokens,
            max_input_chars=cfg.max_input_chars,
            audit_path=run_dir / "llm_audit.jsonl",
        )
        usage = llm.usage

    agents = [Agent(spec, cfg, llm) for spec in cfg.agents]
    apply_initial_relationships(agents)
    env = Environment(cfg.environment, cfg.agents)
    if resume:
        truncate_run(run_dir, keep_below_tick=checkpoint["tick"])
    writer = RunWriter(run_dir)
    loop = Loop(cfg, agents, env, llm, random.Random(cfg.random_seed), writer)
    frames = Frames(cfg, run_dir.name)
    stream = None
    status = "failed"
    try:
        if resume:
            loop.restore(checkpoint, read_memory(run_dir))
            (run_dir / "paused.json").unlink()
        # The viewer journal (frames.jsonl, inspect.jsonl) is written tick by tick for replay.
        stream = Stream(
            run_dir / "frames.jsonl", frames.hello(loop.viewer_snapshot()),
            resume_tick=loop.tick_now if resume else None, delay=0,
        )  # fmt: skip
        stream.publish([], frames.inspect(loop.viewer_snapshot()))

        def publish_tick(world, events, retrievals):
            stream.publish(*frames.capture(world.viewer_snapshot(), events, retrievals), usage)

        loop.on_tick = publish_tick
        if live_port is not None:  # the viewer's live mode: watch, pause and step the engine
            loop.before_tick = stream.before_tick
            print(f"Viewer WebSocket: ws://127.0.0.1:{stream.start(live_port)}", flush=True)
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
    except (LLMError, ValueError) as exc:  # a budget stop or a reply the schema rejected
        days = sorted(int(p.stem[4:]) for p in (run_dir / "checkpoints").glob("day-*.json"))
        paused = {"status": "paused", "reason": str(exc), "tick": loop.tick_now,
                  "checkpoint": days[-1] if days else None}  # fmt: skip
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
        writer.close()
        if stream is not None:
            stream.close()
        manifest["status"] = status
        manifest["token_usage"] = usage
        # Each resumed segment has its own backend, so usage is kept per segment.
        manifest.setdefault("token_usage_segments", []).append(usage)
        write_json(run_dir / "manifest.json", manifest)


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run or dry-run C-16 company experiments")
    parser.add_argument("scenario", choices=(*SCENARIOS, "s0_smoke"))
    parser.add_argument("--output-root", type=Path, default=Path("runs/c16"))
    parser.add_argument("--backend", choices=("demo", "openai"), default="demo")
    parser.add_argument("--replicates", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--resume", action="store_true", help="continue paused replicates")
    parser.add_argument("--max-total-tokens", type=int, help="run token cap (OpenAI)")
    parser.add_argument("--workers", type=int, help="parallel LLM judgements per tick")
    parser.add_argument("--live-port", type=int, help="serve the live viewer on this port")
    args = parser.parse_args()
    if not 1 <= args.replicates <= 3:
        raise SystemExit("replicates must be between 1 and 3")
    if args.backend == "openai" and (not args.pilot or args.replicates != 1):
        raise SystemExit("OpenAI is limited to one --pilot run")
    cfg = build_company_config(args.scenario, backend=args.backend)
    if args.dry_run:
        print(
            json.dumps(
                {"config": cfg.model_dump(), "estimated_calls": estimate_calls(cfg)}, indent=2
            )
        )
        return
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
        )
        print(json.dumps({"run": str(run_dir), "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
