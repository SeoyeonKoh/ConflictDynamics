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


# Listings run on every dialog open; these remember what does not change between them.
_EVENTS: dict[Path, tuple[tuple[int, int], tuple[int, int]]] = {}
_CATALOG: dict = {}


def _events_summary(path: Path) -> tuple[int, int]:
    """(event count, last tick) without parsing every line: the log is in tick order, so the
    last line has the last tick. Remembered until the file's size or mtime changes."""
    stat = path.stat()
    key = (stat.st_mtime_ns, stat.st_size)
    cached = _EVENTS.get(path)
    if cached and cached[0] == key:
        return cached[1]
    data = path.read_bytes()
    lines = [line for line in data.splitlines() if line.strip()]
    tick = json.loads(lines[-1]).get("tick", 0) if lines else 0
    _EVENTS[path] = (key, summary := (len(lines), tick))
    return summary


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
            count, ticks = _events_summary(events_path)
            config = _read(directory / "resolved_config.json")
            paused = _read(directory / "paused.json")
        except (OSError, ValueError):
            broken.append(name)
            continue
        usage = manifest.get("token_usage") or {}
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
                "events": count,
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


def _conf_stamp() -> tuple:
    """Changes whenever any file under conf/ changes, is added or is removed."""
    from .company_runtime import CONF_DIR

    return tuple(sorted((str(p), p.stat().st_mtime_ns) for p in CONF_DIR.rglob("*") if p.is_file()))


def _scenarios() -> list[dict]:
    """The static part of the catalog: building 17 configs takes over a second, so it is built
    once per state of conf/."""
    from . import company_runtime
    from .experiment import SCENARIOS, all_scenarios, estimate_calls

    stamp = _conf_stamp()
    if _CATALOG.get("stamp") == stamp:
        return _CATALOG["rows"]
    rows = []
    for name in [*LEAD, *(s for s in all_scenarios() if s not in LEAD)]:
        path = company_runtime.CONF_DIR / "scenario" / "company_c15" / f"{name}.yaml"
        try:
            raw = yaml.safe_load(path.read_text())
            cfg = company_runtime.build_company_config(name)
        except Exception:
            if name in SCENARIOS:
                raise
            continue  # a generated scenario edited by hand may no longer build
        rows.append({
            "name": name,
            "research_question": cfg.scenario.research_question,
            "extends": raw.get("extends"),
            "max_days": cfg.max_days,
            "estimated_calls": estimate_calls(cfg)["upper_bound_completion_calls"],
        })  # fmt: skip
    _CATALOG.update(stamp=stamp, rows=rows)
    return rows


def warm_catalog() -> None:
    """Build the static catalog ahead of the first request (a failure is left for that request)."""
    try:
        _scenarios()
    except Exception:  # noqa: BLE001 - the request that needs it reports the error
        pass


def scenario_catalog(runs_root: Path) -> list[dict]:
    """Every runnable scenario with its question, its parent, its length and what it costs."""
    rows, _ = discover_company_runs(runs_root) if runs_root.is_dir() else ([], [])
    catalog = []
    for static in _scenarios():
        name = static["name"]
        per_day = [
            r["tokens"] / r["days"]
            for r in rows
            if r["scenario"] == name and r["backend"] == "openai" and r["status"] == "completed"
            and r["days"] > 0
        ]  # fmt: skip
        catalog.append(static | {"tokens_per_day": statistics.median(per_day) if per_day else None})
    return catalog
