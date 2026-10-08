# ruff: noqa: E501, E731, E741  (research harness)
"""Why agents rest: each workday rest is split by whether the agent had work it could do then
(an own task ready or in progress, from the run's task events), where it rested, and whether a
model call chose it or the plan did.

    python3 probes/naturalness/reststats.py RUN_DIR [RUN_DIR ...]
"""

import json
import sys
from collections import Counter, defaultdict

BREAK = {"pantry", "cafeteria", "lobby"}
OPEN = {"ready", "in_progress"}


def load(d):
    ev = [json.loads(l) for l in open(f"{d}/events.jsonl")]
    cfg = json.load(open(f"{d}/resolved_config.json"))
    summary = json.load(open(f"{d}/summary.json"))
    summary = summary.get("summary", summary)
    judged = set()
    for l in open(f"{d}/llm_audit.jsonl"):
        r = json.loads(l)
        if r.get("event") == "completion" and r.get("call_type") == "act":
            judged.add((r["agent"], int(r["tick"])))
    return ev, cfg, summary, judged


def workers_at(cfg, summary, ev):
    """task -> (tick from which, set of workers)."""
    specs = {t["id"]: t for t in cfg["environment"]["org"]["tasks"]}
    assigned_at = {e["actor"]: e["tick"] for e in ev if e["kind"] == "task" and e["payload"].get("change") == "assigned"}
    out = {}
    for tid, t in summary["tasks"].items():
        team = {t.get("owner"), *specs.get(tid, {}).get("contributors", []), *t.get("assigned", []), *t.get("helpers", [])} - {None}
        out[tid] = (assigned_at.get(tid, 0), team)
    return out


def states(ev, tasks, initial):
    """task -> sorted [(tick, state)] from the task events; a task starts ready unless blocked at 0,
    or as the scenario's `initial` says (done or in progress before the run opened)."""
    hist = defaultdict(list)
    for tid, st in initial.items():
        hist[tid].append((-1, st["state"]))
    for e in ev:
        if e["kind"] != "task":
            continue
        c = e["payload"].get("change")
        s = {"blocked": "blocked", "ready": "ready", "unblocked": "ready", "in_progress": "in_progress",
             "revision": "in_progress", "review": "review", "approved": "done", "done": "done"}.get(c)
        if s:
            hist[e["actor"]].append((e["tick"], s))
    return {t: sorted(hist.get(t, []), key=lambda x: x[0]) for t in tasks}  # stable: event order within a tick


def state_before(h, tick):
    s = "ready"
    for t, x in h:
        if t >= tick:
            break
        s = x
    return s


def analyse(d):
    ev, cfg, summary, judged = load(d)
    tpd = cfg["ticks_per_day"]
    half = tpd // 2
    team = workers_at(cfg, summary, ev)
    hist = states(ev, team, cfg["environment"]["org"].get("initial", {}))
    acts = [e for e in ev if e["kind"] == "action"]
    where = {}
    rows = []
    for e in acts:  # one action per agent per tick (a retry's last one wins)
        p = e["payload"]
        a, t = e["actor"], e["tick"]
        if p.get("kind") == "move" and p.get("place"):
            where[a] = p["place"]
        if t % (tpd + cfg.get("overtime_ticks_per_day", 0)) >= tpd:
            continue
        rows.append((a, t, p))
    last = {}
    for a, t, p in rows:
        last[(a, t)] = p
    total = len(last)
    kinds = Counter(p.get("kind") for p in last.values())
    rests = []
    loc = {}
    for (a, t), p in sorted(last.items(), key=lambda kv: kv[0][1]):
        if p.get("kind") == "move" and p.get("place"):
            loc[a] = p["place"]
        if p.get("kind") != "rest":
            continue
        place = p.get("place") or loc.get(a)
        mine = [tid for tid, (since, w) in team.items() if a in w and t >= since and state_before(hist[tid], t) in OPEN]
        lunch = half <= t % tpd < half + 4
        rests.append(dict(agent=a, tick=t, place=place, workable=bool(mine), lunch=lunch,
                          judged=(a, t) in judged, prepare="준비)" in (p.get("reflection") or "")[:40]
                          or "getting ready for" in (p.get("reflection") or "")[:40]))
    n = len(rests)
    c = lambda f: sum(1 for r in rests if f(r))
    work_hours = [r for r in rests if not r["lunch"]]
    print(f"{d.split('/')[1]}: actions {total}, rest {n} ({n / total:.0%}), work {kinds['work']} ({kinds['work'] / total:.0%})")
    print(f"   rest in lunch hour {c(lambda r: r['lunch'])}; outside lunch {len(work_hours)}:")
    print(f"     nothing workable {c(lambda r: not r['lunch'] and not r['workable'])}, "
          f"workable left idle {c(lambda r: not r['lunch'] and r['workable'])}")
    print(f"     at a break place {c(lambda r: not r['lunch'] and r['place'] in BREAK)}, at desk/elsewhere {c(lambda r: not r['lunch'] and r['place'] not in BREAK)}")
    print(f"     chosen by the model {c(lambda r: not r['lunch'] and r['judged'])}, by the plan {c(lambda r: not r['lunch'] and not r['judged'])}; "
          f"'prepare' {c(lambda r: r['prepare'])}")
    idle = [r for r in work_hours if r["workable"]]
    print(f"     workable-idle by source: model {sum(r['judged'] for r in idle)}, plan {sum(not r['judged'] for r in idle)}; "
          f"at desk {sum(r['place'] not in BREAK for r in idle)}")
    per = Counter(r["agent"] for r in work_hours)
    per_idle = Counter(r["agent"] for r in idle)
    print("     per agent (rest/idle-with-work):", " ".join(f"{a[-3:]}:{per[a]}/{per_idle[a]}" for a in sorted(per)))
    seq = defaultdict(list)
    for r in work_hours:
        seq[r["agent"]].append(r["tick"])
    streaks = []
    for a, ts in seq.items():
        run = [ts[0]]
        for x in ts[1:]:
            if x == run[-1] + 1:
                run.append(x)
            else:
                if len(run) >= 4:
                    streaks.append((a, run[0], len(run)))
                run = [x]
        if len(run) >= 4:
            streaks.append((a, run[0], len(run)))
    print(f"     rest streaks >=4 outside lunch: {len(streaks)} " + " ".join(f"{a[-3:]}@{s}x{k}" for a, s, k in sorted(streaks)))
    return rests


if __name__ == "__main__":
    for d in sys.argv[1:]:
        analyse(d)
