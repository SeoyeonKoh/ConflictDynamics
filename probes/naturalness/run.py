# ruff: noqa: E501, E731, E741, UP045  (research harness: long Korean prompt text)
"""Run act-call variants on probe cases K times each; write every result as JSON lines.

uv run python run.py cases/*.yaml --variants base,human --k 4 --out results/x.jsonl
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
os.chdir(Path(__file__).resolve().parents[2])  # the repo root: cases name runs/ paths

import human  # noqa: E402

import conflict_sim.agent.agent as agent_mod  # noqa: E402
from conflict_sim.company_runtime import build_company_config, load_c15_scenario  # noqa: E402
from conflict_sim.llm import OpenAIBackend, create_openai_client  # noqa: E402
from conflict_sim.probe import ask, build, names, situation  # noqa: E402

BASE_ACT = agent_mod.ACT_INSTRUCTIONS
NAMES_RULE = """
In anything you say ("text"), talk as a person in this office does: call colleagues by name (the
directory below gives each id's name), and call work by its name, never by a task id or any field
name from the payload (tick, lifecycle, can_work, notice...). Say times as clock times."""


def scenario_of(case):
    base = case["base"]
    if "scenario" in base:
        return base["scenario"]
    return json.loads((Path(base["run"]) / "manifest.json").read_text())["scenario"]


def prepare(case, real, who):
    loop, llm = build(case, real)
    ctx = case.get("context", {})
    here = ctx.get("place", "office")
    for pid in loop.env.office.location:  # who is where: the case's list, else everyone away
        loop.env.office.location[pid] = "lobby" if pid != who else here
    for pid, place in ctx.get("others", {}).items():
        loop.env.office.location[pid] = place
    agent, view, tick = situation(case, loop, who)
    ctx = case.get("context", {})
    for a in ctx.get("asked", []):  # what I already asked whom: {to, about, tick, said, reply}
        agent._asked.append(
            {
                "to": a["to"],
                "about": a.get("about", []),
                "tick": a["tick"],
                "said": a["said"],
                "reply": a.get("reply"),
            }
        )
    llm.live = True
    return loop, llm, agent, view, tick


def one(case, variant, prepared, real, preset):
    loop, llm, agent, view, tick = prepared
    who = agent.name
    w = human.World(loop, preset)
    meta = {}
    if variant.startswith("base"):
        action = ask(agent, view, tick, "judge")
        call = llm.calls[0] if llm.calls else {}
        meta = {
            "system_len": len(call.get("system", "")),
            "prompt_len": len(call.get("prompt", "")),
        }
    else:
        opts = {
            "human": {},
            "human_thin": {"rich": False},
            "human_nonorms": {"norms": False},
            "human_voice": {"voice": True},
            "human_v2": {"voice": True, "candor": True},
            "human_life": {},
        }[variant]
        human.OPEN_ONLY = variant in ("human_v2", "human_life")
        human.LIFE_ON = variant == "human_life"
        action, info = human.act_human(w, agent, view, tick, real, **opts)
        meta = {
            "system_len": len(info["system"]),
            "prompt_len": len(info["prompt"]),
            "raw": info["raw"],
        }
    q = " ".join(
        [f"{view.phase} at {view.place}."] + [f"{m.sender} wrote: {m.text}" for m in view.inbox]
    )
    meta["situation"] = human.situation_text(
        w, agent, view, tick, agent._recalled or agent._recall(q, tick)
    )
    refusal = loop.env.apply(agent.name, action, tick)
    return {
        "case": case["name"],
        "variant": variant,
        "agent": who,
        "name": w.name[who],
        "kind": action.kind,
        "task": action.task,
        "task_title": w.title.get(action.task or ""),
        "target": action.target,
        "targets": action.targets,
        "place": action.place,
        "text": action.text,
        "reflection": action.reflection,
        "expression": action.expression,
        "refused": refusal.reason if refusal else None,
        **meta,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cases", nargs="+", type=Path)
    p.add_argument("--variants", default="base,human")
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--dry", action="store_true", help="print the human prompt for the first agent")
    args = p.parse_args()
    cfg = build_company_config(backend="openai")
    real = OpenAIBackend(
        create_openai_client(Path.cwd() / ".env"),
        model_embed=cfg.model_embed,
        reasoning_effort=cfg.reasoning_effort,
        max_tokens_decide=1024,
        max_tokens_speak=cfg.max_tokens_speak,
        max_total_tokens=6_000_000,
        max_input_chars=cfg.max_input_chars,
    )
    rows = []
    for path in args.cases:
        case = yaml.safe_load(path.read_text(encoding="utf-8"))
        preset = load_c15_scenario(scenario_of(case)).preset
        loop, _ = build(case, real)
        whos = names(case, loop)
        if args.dry:
            loop, llm, agent, view, tick = prepare(case, real, whos[0])
            w = human.World(loop, preset)
            print(human.act_system(w, agent.name))
            print("=====")
            q = " ".join(
                [f"{view.phase} at {view.place}."]
                + [f"{m.sender} wrote: {m.text}" for m in view.inbox]
            )
            print(human.situation_text(w, agent, view, tick, agent._recall(q, tick)))
            continue
        for variant in args.variants.split(","):
            agent_mod.ACT_INSTRUCTIONS = BASE_ACT + (NAMES_RULE if variant == "base_names" else "")
            if variant == "base_names":  # the directory the rule points to
                loop0 = loop
                directory = "\n".join(f"{a.name}: {a.spec.display_name}" for a in loop0.agents)
                agent_mod.ACT_INSTRUCTIONS += "\nDirectory:\n" + directory
            jobs = [
                prepare(case, real, who) for who in whos for _ in range(args.k)
            ]  # serial: hydra
            with ThreadPoolExecutor(args.workers) as pool:
                res = list(pool.map(lambda j: _safe(case, variant, j, real, preset), jobs))
            rows += res
            ok = [r for r in res if "error" not in r]
            print(f"## {case['name']} [{variant}] n={len(res)} errors={len(res) - len(ok)}")
            for r in ok:
                said = f" | {r['text'][:110]}" if r.get("text") else ""
                ref = f" ✗{r['refused'][:50]}" if r["refused"] else ""
                print(
                    f"   {r['name']} {r['kind']} {r.get('task_title') or r.get('target') or r.get('place') or ''}{ref}{said}"
                )
        agent_mod.ACT_INSTRUCTIONS = BASE_ACT
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("usage:", json.dumps(real.usage, ensure_ascii=False)[:200])


def _safe(case, variant, prepared, real, preset):
    try:
        return one(case, variant, prepared, real, preset)
    except Exception as exc:  # keep the batch going; report it
        return {
            "case": case["name"],
            "variant": variant,
            "agent": prepared[2].name,
            "error": repr(exc)[:300],
        }


if __name__ == "__main__":
    main()
