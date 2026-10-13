"""Run and audit the enterprise week with the demo backend only; no paid API path.

python scripts/weekly_operations_validation.py --output runs/domain-week-preview
"""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from conflict_sim.experiment import run_scenario


def audit(run_dir: Path) -> dict:
    cfg = json.loads((run_dir / "resolved_config.json").read_text())
    summary = json.loads((run_dir / "summary.json").read_text())
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
    ticks = cfg["ticks_per_day"] + cfg["overtime_ticks_per_day"]
    policy = cfg["weekly_operations"]
    breaks, activities, rejected = defaultdict(set), Counter(), Counter()
    for event in events:
        p = event["payload"]
        if event["kind"] == "action" and p.get("kind") == "accepted_activity":
            activities[p["activity"]] += 1
            if p["activity"] == "break":
                breaks[event["tick"]].add(event["actor"])
        if event["kind"] == "rejected":
            rejected[p["reason"]] += 1
    meetings = {}
    for m in cfg["scenario"]["meetings"]:
        sid = f"meeting:{m['id']}:{m['day']}"
        starts = [e for e in events if e["session"] == sid and e["payload"].get("start")]
        ends = [e for e in events if e["session"] == sid and e["payload"].get("end")]
        expected_start = m["day"] * ticks + m["tick"]
        expected_end = expected_start + m["duration_ticks"] - 1
        meetings[m["id"]] = bool(
            len(starts) == len(ends) == 1
            and starts[0]["tick"] == expected_start
            and ends[0]["tick"] == expected_end
            and starts[0]["payload"]["participants"] == m["participants"]
        )
    external = {}
    for b in policy["blocks"]:
        if b["kind"] == "external_meeting":
            rows = [
                e
                for e in events
                if e["payload"].get("id") == b["id"] and e["payload"].get("kind") == "calendar"
            ]
            external[b["id"]] = len(rows) == b["duration_ticks"] * len(b["participants"])
    minutes = {
        k: {"owner": v["owner"], "completed": v["done_tick"] is not None}
        for k, v in summary["tasks"].items()
        if k.startswith("MIN-")
    }
    deferred = summary["tasks"]["DETAIL-analysis"]
    checks = {
        "demo_only": cfg["backend"] == "demo" and summary["token_usage"] is None,
        "six_workdays_ten_people": summary["ticks"] == 228 and summary["agents"] == 10,
        "lunch_at_13": policy["lunch_start_tick"] == 16 and cfg["ticks_per_day"] == 36,
        "break_cap": max(map(len, breaks.values()), default=0) <= policy["max_breakers"],
        "all_scheduled_meetings": all(meetings.values()),
        "external_report_time_reserved": all(external.values()),
        "one_minutes_task_per_meeting": len(minutes) == len(meetings) + len(external),
        "all_minutes_completed_in_demo": all(v["completed"] for v in minutes.values()),
        "detail_deferred_not_deleted": deferred["done_tick"] is None
        and deferred["forced_block_until"] == summary["ticks"],
    }
    digest = hashlib.sha256(json.dumps(summary, sort_keys=True).encode()).hexdigest()
    return {
        "scenario": "r10_enterprise_weekly",
        "backend": "demo",
        "paid_api_used": False,
        "agents": summary["agents"],
        "days": summary["days"],
        "ticks": summary["ticks"],
        "tasks": len(summary["tasks"]),
        "sessions": summary["sessions"],
        "checks": checks,
        "all_checks_passed": all(checks.values()),
        "maximum_simultaneous_breaks": max(map(len, breaks.values()), default=0),
        "accepted_activities": dict(activities),
        "scheduled_meetings": meetings,
        "external_meetings": external,
        "minutes_tasks": minutes,
        "rejected_actions": summary["rejected_actions"],
        "top_rejection_reasons": rejected.most_common(5),
        "summary_sha256": digest,
        "limitations": [
            "Demo decisions do not establish natural LLM or employee behavior.",
            "20-minute standup plus 10-minute transition is one 30-minute reservation.",
            "Formal help consent, emergency reporting and role ratios are prompt norms.",
            "The issue meeting uses a scenario slot, not a general free-slot scheduler.",
            "Completion dates and workload/stress require domain review, not just passing checks.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run_scenario("r10_enterprise_weekly", args.output, backend="demo")
    report = audit(args.output)
    (args.output / "weekly_validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in [
                    "agents",
                    "days",
                    "ticks",
                    "all_checks_passed",
                    "maximum_simultaneous_breaks",
                    "rejected_actions",
                ]
            }
        )
    )
    if not report["all_checks_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
