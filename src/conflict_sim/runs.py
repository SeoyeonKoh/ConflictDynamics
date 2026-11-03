"""Run, people and scenario listings for the viewer's server; no dashboard imports."""

import json
import statistics
from pathlib import Path

import yaml

from .tape import full_tape

LEAD = ("r10_midweek", "r10_enterprise_weekly", "r10_human", "r10_documents_ko")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def discover_company_runs(root: Path) -> tuple[list[dict], list[str]]:
    """Find company-simulation runs, including runs that stopped before corpus export."""
    rows: list[dict] = []
    broken: list[str] = []
    for manifest_path in sorted(root.rglob("manifest.json")):
        directory = manifest_path.parent
        events_path = directory / "events.jsonl"
        if not events_path.is_file():
            continue
        name = str(directory.relative_to(root))
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            events = _read_jsonl(events_path)
            config = _read(directory / "resolved_config.json")
            paused = _read(directory / "paused.json")
        except (OSError, ValueError):
            broken.append(name)
            continue
        usage = manifest.get("token_usage") or {}
        ticks = max((event.get("tick", 0) for event in events), default=0)
        span = (config.get("environment") or {}).get("day_span") or 34
        rows.append(
            {
                "run": name,
                "scenario": manifest.get("scenario"),
                "status": manifest.get("status", "unknown"),
                "model": manifest.get("model_id"),
                "backend": manifest.get("backend"),
                "seed": manifest.get("seed"),
                "ticks": ticks,
                "days": (ticks + 1) / span,
                "events": len(events),
                "tokens": sum(
                    int(item.get("total_tokens", 0))
                    for item in usage.values()
                    if isinstance(item, dict)
                ),
                "paused_tick": paused.get("tick"),
                "tape": full_tape(directory / "tape.sqlite"),  # resumes at its exact tick
                "resumable": bool(paused) and paused.get("replay") != "mismatch"
                and (
                    full_tape(directory / "tape.sqlite")
                    or any((directory / "checkpoints").glob("day-*.json"))
                ),
                "modified": manifest_path.stat().st_mtime_ns,
                "directory": str(directory),
            }
        )
    rows.sort(key=lambda row: row["modified"], reverse=True)
    return rows, broken


def people(run_dir: Path) -> list[dict]:
    """Who is in a run, by the names its scenario gives them."""
    agents = _read(run_dir / "resolved_config.json").get("agents", [])
    return [
        {"id": a["name"], "name": a.get("display_name") or a["name"],
         "title": a.get("role") or a.get("title")}  # role reads as a job; title is a code
        for a in agents
    ]


def scenario_catalog(runs_root: Path) -> list[dict]:
    """Every runnable scenario with its question, its parent, its length and what it costs."""
    from .company_runtime import CONF_DIR, build_company_config
    from .experiment import SCENARIOS, estimate_calls

    rows, _ = discover_company_runs(runs_root) if runs_root.is_dir() else ([], [])
    names = [*LEAD, *(s for s in SCENARIOS if s not in LEAD)]
    catalog = []
    for name in names:
        raw = yaml.safe_load((CONF_DIR / "scenario" / "company_c15" / f"{name}.yaml").read_text())
        cfg = build_company_config(name)
        per_day = [
            r["tokens"] / r["days"]
            for r in rows
            if r["scenario"] == name and r["backend"] == "openai" and r["status"] == "completed"
            and r["days"] > 0
        ]  # fmt: skip
        catalog.append(
            {
                "name": name,
                "research_question": cfg.scenario.research_question,
                "extends": raw.get("extends"),
                "max_days": cfg.max_days,
                "estimated_calls": estimate_calls(cfg)["upper_bound_completion_calls"],
                "tokens_per_day": statistics.median(per_day) if per_day else None,
            }
        )
    return catalog
