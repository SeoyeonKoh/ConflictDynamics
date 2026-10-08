"""conflict-probe: put one agent in a tick you describe and ask the real model, K times.

A case file (YAML) names a world (a run's day-end checkpoint, or a scenario fast-forwarded with
the demo backend), one agent, a tick, and what to change in that agent's context: messages,
a refusal, task notes, the plan, recent actions, relations, stress. The probe then asks for the
same judgement K times and reports what the agent chose, against the case's expectations. Only
the judged call goes to the paid model; the world is built without one (embeddings excepted, so
memory retrieval matches a real run).

    ALLOW_PAID_API_EXPERIMENTS=1 uv run conflict-probe cases/blocked_plan.yaml --repeat 5
    uv run conflict-probe cases/blocked_plan.yaml --dry   # print the exact prompt, no call
"""

import argparse
import functools
import json
import os
import random
import re
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from .agent import Agent
from .company_runtime import apply_initial_relationships, build_company_config
from .conversation import MEETING, MESSAGE, TALK
from .environment import Environment
from .llm import DemoBackend, OpenAIBackend, create_openai_client
from .loop import Loop
from .models import Action, Message, PlanItem, Rejected, Thread, Utterance, View
from .storage import RunWriter, read_memory


class Switch(DemoBackend):
    """Completions from the demo while the world is built, from the real model once it is
    probed; embeddings from the real model throughout, so retrieval matches a real run."""

    def __init__(self, real, **kwargs):
        super().__init__(**kwargs)
        self.real, self.live, self.calls = real, False, []

    def complete(self, **request):
        if not self.live:
            return super().complete(**request)
        reply = self.real.complete(**request)
        self.calls.append({k: request[k] for k in ("system", "prompt")} | {"reply": reply})
        return reply

    def embed(self, texts):
        return self.real.embed(texts) if self.real is not None else super().embed(texts)


@functools.cache
def _memory(run: Path) -> dict:
    return read_memory(run)  # read once per run, shared by every world built from it


def build(case: dict, real) -> tuple[Loop, Switch]:
    """The world the case starts from, with the probed agent's model still the demo."""
    base = case["base"]
    run = Path(base["run"]) if "run" in base else None
    scenario = base.get("scenario") or json.loads((run / "manifest.json").read_text())["scenario"]
    cfg = build_company_config(scenario, backend="openai")
    llm = Switch(real, blocked_nudge_ticks=cfg.blocked_nudge_ticks,
                 blocked_report_ticks=cfg.blocked_report_ticks)  # fmt: skip
    agents = [Agent(spec, cfg, llm) for spec in cfg.agents]
    apply_initial_relationships(agents)
    env = Environment(cfg.environment, cfg.agents)
    loop = Loop(
        cfg, agents, env, llm, random.Random(cfg.random_seed), RunWriter(Path(tempfile.mkdtemp()))
    )
    if run is not None:
        checkpoint = json.loads(
            (run / "checkpoints" / f"day-{base.get('day', 0)}.json").read_text()
        )
        before = checkpoint["tick"]
        memory = {
            name: ([r for r in records if r.created_tick < before],
                   {k: v for k, v in vectors.items()
                    if any(r.id == k and r.created_tick < before for r in records)})
            for name, (records, vectors) in _memory(run).items()
        }  # fmt: skip
        loop.restore(checkpoint, memory)
    for tick in range(loop.tick_now, loop.tick_now + base.get("warmup", 0)):
        loop.tick(tick)  # fast-forward with the demo answering
        loop.tick_now = tick + 1
    return loop, llm


def situation(case: dict, loop: Loop, name: str) -> tuple[Agent, View, int]:
    """The probed agent's view at the case's tick, with the case's context laid over it."""
    agent = loop.agent(name)
    tick = case.get("tick", loop.tick_now)
    for task_id, fields in case.get("world", {}).get("tasks", {}).items():
        task = loop.env.org.tasks[task_id]  # e.g. {owner: HDS-011, assigned: [...], worked: 2}
        for key, value in fields.items():
            setattr(task, key, value)
    loop.env.org.advance(tick)  # blocked/unblocked as the changed world now stands
    day = tick // loop.day_span
    view = loop._view(agent, tick, day, loop._phase(tick))
    ctx = case.get("context", {})
    update = {}
    if "inbox" in ctx:
        update["inbox"] = [
            Message(
                sender=m["sender"],
                text=m["text"],
                tick=m.get("tick", tick - 1),
                session_id=f"dm:{m['sender']}:{agent.name}:probe",
            )  # fmt: skip
            for m in ctx["inbox"]
        ]
    if "rejected" in ctx:
        r = ctx["rejected"]
        action = {"expression": "neutral", "reflection": "-", "importance": 1, "valence": 0,
                  "arousal": 0} | r["action"]  # fmt: skip
        update["rejected"] = Rejected(action=Action.model_validate(action), reason=r["reason"])
    for key in ("place", "phase", "present"):
        if key in ctx:
            update[key] = ctx[key]
    if "place" in ctx:
        loop.env.office.location[agent.name] = ctx["place"]  # where the office sees them too
    view = view.model_copy(update=update)
    if "notes" in ctx:
        agent._notes.update({task: {"task": task} | note for task, note in ctx["notes"].items()})
    if "plan" in ctx:
        agent.plan = [PlanItem.model_validate(item) for item in ctx["plan"]]
    if "recent_actions" in ctx:
        agent._recent = list(ctx["recent_actions"])
    for other, value in ctx.get("relations", {}).items():
        agent.state.relation(other).relation = value
    if "stress" in ctx:
        agent.state.stress = ctx["stress"]
    for memory in ctx.get("memories", []):  # records the agent has, as of the tick before
        agent.observe(memory["text"], tick=tick - 1, type="observation",
                      importance=memory.get("importance"), valence=memory.get("valence", 0),
                      subjects=[agent.name])  # fmt: skip
    if ctx.get("memories"):
        loop._embed()  # so they are retrieved by relevance like any other record
    return agent, view, tick


SPEECH = {"meeting": MEETING, "talk": TALK, "message": MESSAGE}


def thread_for(case: dict, loop: Loop, tick: int) -> Thread:
    """A conversation to speak in: a scheduled meeting's agenda (or the case's own), then the
    case's earlier posts, in order."""
    spec = case["speak"]
    meeting = next((m for m in loop.cfg.scenario.meetings if m.id == spec.get("meeting")), None)
    root_id = f"meeting:{meeting.id}:probe" if meeting else "probe:thread"
    organizer = spec.get("organizer", meeting.organizer if meeting else "HDS-001")
    agenda = spec.get("agenda", meeting.agenda if meeting else "-")
    posts = [Utterance(id=root_id, speaker=organizer, text=agenda, reply_to=None, timestamp=tick)]
    for i, post in enumerate(spec.get("before", [])):
        posts.append(Utterance(id=f"{root_id}:{i}", speaker=post["speaker"], text=post["text"],
                               reply_to=root_id, timestamp=tick))  # fmt: skip
    return Thread(posts)


def ask(agent: Agent, view: View, tick: int, call: str, case: dict | None = None, loop=None):
    """One judgement as the loop would make it: `act` may follow the plan without the model,
    `judge` always asks it (the act path up to the judgement, then the judgement)."""
    if call == "act":
        return agent.act(view, tick)
    if call == "speak":  # one turn in a conversation, as an everyone-speaks meeting takes it
        thread = thread_for(case, loop, tick)
        kind = case["speak"].get("kind", "meeting")
        text = agent.speak(thread, None, SPEECH[kind].speak, seen=0)
        return Action(kind="talk", targets=["meeting"], text=text, expression="neutral",
                      reflection="-", importance=1, valence=0, arousal=0)  # fmt: skip
    agent._note_replies(view)
    agent._note_refusal(view, tick)
    known = agent._known(view)
    waiting = {b.task for b in known.blocked}
    item = agent._block(known, waiting, tick)
    return agent._judge(item, known, tick)


def check(action: Action, expect: list[dict]) -> list[str]:
    """The expectations this action fails, each as a short reason. A rule with "when" applies
    only to an action matching it, e.g. {when: {kind: work}, field: task, not_in: [T04]}."""
    failed = []
    for rule in expect:
        if any(getattr(action, key) != value for key, value in rule.get("when", {}).items()):
            continue
        value = getattr(action, rule["field"]) or ""
        if "in" in rule and value not in rule["in"]:
            failed.append(f"{rule['field']}={value!r} not in {rule['in']}")
        if "not_in" in rule and value in rule["not_in"]:
            failed.append(f"{rule['field']}={value!r} in {rule['not_in']}")
        if "matches" in rule and not re.search(rule["matches"], str(value)):
            failed.append(f"{rule['field']} does not match {rule['matches']!r}")
    return failed


def names(case: dict, loop: Loop) -> list[str]:
    """`agent: HDS-011`, a list, or `all`."""
    agent = case["agent"]
    if agent == "all":
        return [a.name for a in loop.agents]
    return agent if isinstance(agent, list) else [agent]


def prepare(case: dict, real) -> list[tuple]:
    """Fresh worlds and situations for one round (built serially: config loading is not
    thread-safe), one per probed agent, ready to be asked in parallel."""
    loop, _ = build(case, real)
    rounds = []
    for name in names(case, loop):
        world, llm = build(case, real)  # each agent gets its own world: asking changes it
        agent, view, tick = situation(case, world, name)
        llm.live = True
        rounds.append((world, agent, view, tick, llm))
    return rounds


def probe_once(prepared, case: dict, call: str) -> dict:
    world, agent, view, tick, llm = prepared
    call = case.get("call", call)
    action = ask(agent, view, tick, call, case, world)
    failed = check(action, case.get("expect", []))
    refusal = None if call == "speak" else world.env.apply(agent.name, action, tick)
    if refusal is not None and case.get("refused") is False:
        failed.append(f"refused: {refusal.reason}")
    return {
        "agent": agent.name, "kind": action.kind, "task": action.task, "target": action.target,
        "text": action.text, "reflection": action.reflection, "failed": failed,
        "refused": refusal.reason if refusal else None,
        "called": bool(llm.calls), "prompt": llm.calls[0] if llm.calls else None,
    }  # fmt: skip


def _reflect_first() -> None:
    """The action's reasoning before its kind: the model writes "reflection" first, then picks
    what to do (a probe showed "T04 waits on T03, so I cannot work on it" with kind work T04)."""
    from . import llm

    plain = llm.strict_schema

    def ordered(model):
        schema = plain(model)
        if model is Action:
            first = ("reflection",)
            props = schema["properties"]
            schema["properties"] = {k: props[k] for k in first} | {
                k: v for k, v in props.items() if k not in first
            }
            schema["required"] = list(schema["properties"])
        return schema

    llm.strict_schema = ordered


VARIANTS = {"reflect-first": _reflect_first}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("cases", nargs="+", type=Path, help="case files (YAML)")
    parser.add_argument(
        "--repeat", type=int, help="judgements per case (default: the case's, or 3)"
    )
    parser.add_argument("--call", choices=("judge", "act"), default="judge")
    parser.add_argument("--workers", type=int, default=5, help="judgements in parallel")
    parser.add_argument("--dry", action="store_true", help="print the exact prompt; no paid call")
    parser.add_argument("--out", type=Path, help="write every result as JSON lines here")
    parser.add_argument(
        "--variant", choices=sorted(VARIANTS), action="append", default=[],
        help="try a change without editing the engine (repeatable)",
    )  # fmt: skip
    args = parser.parse_args()
    for name in args.variant:
        VARIANTS[name]()
    if not args.dry and os.environ.get("ALLOW_PAID_API_EXPERIMENTS") != "1":
        raise SystemExit("BLOCKED: paid probes need ALLOW_PAID_API_EXPERIMENTS=1 (or use --dry)")
    cfg = build_company_config(backend="openai")  # model settings as an experiment run has them
    real = OpenAIBackend(
        create_openai_client(Path.cwd() / ".env"),
        model_embed=cfg.model_embed,
        reasoning_effort=cfg.reasoning_effort,
        max_tokens_decide=cfg.max_tokens_decide,
        max_tokens_speak=cfg.max_tokens_speak,
        max_total_tokens=2_000_000,
        max_input_chars=cfg.max_input_chars,
    )
    rows = []
    for path in args.cases:
        case = yaml.safe_load(path.read_text(encoding="utf-8"))
        if args.dry:
            loop, llm = build(case, real)
            agent, view, tick = situation(case, loop, names(case, loop)[0])
            capture = []
            llm.real = type("Echo", (), {"complete": lambda self, **r: capture.append(r) or
                            json.dumps({"kind": "rest", "expression": "neutral",
                                        "reflection": "-", "importance": 1, "valence": 0,
                                        "arousal": 0}),
                            "embed": real.embed})()  # fmt: skip
            llm.live = True
            ask(agent, view, tick, args.call)
            for request in capture[:1]:
                print(f"=== {path.name}: SYSTEM ===\n{request['system']}\n=== USER ===")
                try:
                    print(json.dumps(json.loads(request["prompt"]), ensure_ascii=False, indent=2))
                except ValueError:  # the human prompt style's narrative
                    print(request["prompt"])
            continue
        k = args.repeat or case.get("repeat", 3)
        prepared = [one for _ in range(k) for one in prepare(case, real)]
        with ThreadPoolExecutor(args.workers) as pool:
            results = list(pool.map(lambda p: probe_once(p, case, args.call), prepared))
        k = len(results)
        passed = sum(not r["failed"] for r in results)
        choices = Counter(f"{r['kind']} {r['task'] or r['target'] or ''}".strip() for r in results)
        print(f"\n## {case.get('name', path.stem)}  ({path.name})  pass {passed}/{k}")
        print("   choices:", dict(choices.most_common()))
        for r in results:
            mark = "ok " if not r["failed"] else "FAIL"
            said = f" | {r['text'][:120]}" if r["text"] else ""
            who = f"{r['agent']} " if case["agent"] != results[0]["agent"] else ""
            print(f"   {mark} {who}{r['kind']} {r['task'] or r['target'] or ''}{said}")
            print(f"        {r['reflection'][:160]}")
            for reason in r["failed"]:
                print(f"        ✗ {reason}")
        rows += [{"case": path.name} | {k2: v for k2, v in r.items() if k2 != "prompt"}
                 for r in results]  # fmt: skip
    usage = real.usage
    if not args.dry:
        print(f"\ntokens: {json.dumps(usage, ensure_ascii=False)[:300]}")
    if args.out:
        args.out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows))


if __name__ == "__main__":
    sys.exit(main())
