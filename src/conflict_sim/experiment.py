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
from .llm import DemoBackend, OpenAIBackend, create_openai_client
from .loop import Loop
from .storage import RunWriter, save_company_run, write_json, write_jsonl

SCENARIOS = (
    "s0_baseline",
    "s1_dependency_failure",
    "s2_deadline_pressure",
    "s3_resource_competition",
    "s4_evaluation_season",
    "i1_manager_clarification",
    "i2_deadline_adjustment",
    "i3_private_mediation",
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
) -> dict:
    if backend == "openai":
        if os.getenv("ALLOW_PAID_API_EXPERIMENTS") != "1":
            raise PermissionError("BLOCKED: user cost approval (ALLOW_PAID_API_EXPERIMENTS=1)")
        if not pilot:
            raise PermissionError(
                "OpenAI execution requires --pilot before any repeated experiment"
            )
    if run_dir.exists():
        raise FileExistsError(f"Run directory already exists: {run_dir}")

    cfg = build_company_config(scenario, backend=backend)
    cfg = cfg.model_copy(update={"random_seed": cfg.random_seed + seed_offset})
    estimates = estimate_calls(cfg)
    run_dir.mkdir(parents=True)
    write_json(run_dir / "resolved_config.json", cfg.model_dump())
    write_json(
        run_dir / "manifest.json",
        {
            "scenario": scenario,
            "seed": cfg.random_seed,
            "backend": backend,
            "model_id": cfg.model_decide if backend == "openai" else "demo",
            "git_commit": _git_commit(),
            "estimated_calls": estimates,
            "status": "running",
        },
    )

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
        )
        usage = llm.usage

    agents = [Agent(spec, cfg, llm) for spec in cfg.agents]
    apply_initial_relationships(agents)
    env = Environment(cfg.environment, cfg.agents)
    writer = RunWriter(run_dir)
    loop = Loop(cfg, agents, env, llm, random.Random(cfg.random_seed), writer)
    frames = []
    loop.on_tick = lambda world, events, retrievals: frames.append(world.viewer_snapshot())
    status = "failed"
    try:
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
        write_jsonl(run_dir / "frames.jsonl", frames)
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
        status = "completed"
        return summary
    finally:
        loop.close()
        writer.close()
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        manifest["status"] = status
        manifest["token_usage"] = usage
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
        summary = run_scenario(
            args.scenario,
            run_dir,
            backend=args.backend,
            seed_offset=replicate,
            pilot=args.pilot,
        )
        print(json.dumps({"run": str(run_dir), "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
