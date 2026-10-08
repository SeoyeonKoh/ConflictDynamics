# ruff: noqa: E501, E731, E741, UP045  (research harness: long Korean prompt text)
"""Speech variants: one turn in a conversation, current prompt vs the human rendering.

A case names a world, speakers, the conversation kind and the posts so far:
    speak: {kind: message|talk|meeting, root: {speaker, text}, before: [{speaker, text}]}
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import human  # noqa: E402
import run as R  # noqa: E402  (sets cwd, imports)

from conflict_sim.company_runtime import build_company_config, load_c15_scenario  # noqa: E402
from conflict_sim.conversation import MEETING, MESSAGE, TALK  # noqa: E402
from conflict_sim.llm import OpenAIBackend, create_openai_client  # noqa: E402
from conflict_sim.models import Thread, Utterance  # noqa: E402
from conflict_sim.probe import build, names  # noqa: E402

KINDS = {"meeting": MEETING, "talk": TALK, "message": MESSAGE}
SETTING = {
    "message": "회사 메신저로 {others}와(과) 1:1 대화 중이다.",
    "talk": "{place}에서 {others}와(과) 직접 얼굴을 보고 이야기하는 중이다.",
    "meeting": "회의실에서 정해진 안건으로 회의 중이다. 참석자: {others}.",
}
SPEAK_HEAD = """대화에서 네 차례다. 이 사람이 지금 실제로 할 말 한마디를 써라. 말만 쓰고, 이름표나 따옴표, 설명은 붙이지 않는다.
꼭 일 얘기만 할 필요는 없다. 상대가 한 말에 반응하고, 할 말이 별로 없으면 짧게 말한다."""


def thread_of(case, me):
    spec = case["speak"]
    root = spec["root"]
    posts = [
        Utterance(id="root", speaker=root["speaker"], text=root["text"], reply_to=None, timestamp=0)
    ]
    for i, p in enumerate(spec.get("before", [])):
        posts.append(
            Utterance(
                id=f"u{i}", speaker=p["speaker"], text=p["text"], reply_to="root", timestamp=0
            )
        )
    return Thread(posts)


def speak_base(agent, thread, kind, tick):
    agent._recall(thread.utterances[-1].text, tick)  # as decide() leaves it before speak()
    return agent.speak(thread, thread.utterances[-1].id, KINDS[kind].speak, seen=0)


def speak_human(
    w,
    agent,
    view,
    tick,
    thread,
    kind,
    llm,
    rich=True,
    brief=True,
    voice=False,
    candor=False,
    life=False,
):
    me = agent.name
    people = sorted({u.speaker for u in thread.utterances} - {me})
    others = ", ".join(w.name.get(p, p) for p in people)
    place = human.PLACE_KO.get(view.place, view.place)
    head = SPEAK_HEAD + ("\n" + human.CANDOR.lstrip("- ").replace("\n  ", " ") if candor else "")
    system = "\n\n".join([head, human.SPEECH, human.persona_card(w, me, rich, voice)])
    lines = [SETTING[kind].format(others=others, place=place)]
    if life and me in human.LIFE:
        lines.append(f"오늘 네 개인적인 사정: {human.LIFE[me]}")
    feel = human._feel(w, agent, people)
    if feel:
        lines.append("이 사람들에 대한 네 감정:\n" + "\n".join(feel))
    if brief:  # what I am busy with, in a line each, as I know it
        mine = [
            t
            for t in view.tasks
            if t.role in ("owner", "contributor", "helper") and t.lifecycle != "done"
        ]
        if mine:
            lines.append(
                "요즘 네가 맡은 일: "
                + ", ".join(
                    f"'{w.title[t.id]}'" + (" (검토 대기)" if t.lifecycle == "review" else "")
                    for t in mine
                )
            )
    mem = agent._recall(thread.utterances[-1].text, tick)
    if mem:
        lines.append("떠오르는 기억:\n" + "\n".join(f"- {w.humanize(m)}" for m in mem[:6]))
    lines.append("대화:")
    for u in thread.utterances:
        who = "나" if u.speaker == me else w.name.get(u.speaker, u.speaker)
        lines.append(f"{who}: {w.humanize(u.text)}")
    lines.append(f"\n이제 {w.name[me]}로서 할 말:")
    text = llm.complete(
        system=system,
        prompt="\n".join(lines),
        model=agent.config.model_speak,
        temperature=agent.config.temperature,
        json_mode=False,
        schema=None,
    )
    return text.strip().strip('"')


def one(case, variant, prepared, real, preset):
    loop, llm, agent, view, tick = prepared
    w = human.World(loop, preset)
    kind = case["speak"]["kind"]
    thread = thread_of(case, agent.name)
    if variant == "base":
        text = speak_base(agent, thread, kind, tick)
    else:
        opts = {
            "human": {},
            "human_thin": {"rich": False},
            "human_nobrief": {"brief": False},
            "human_voice": {"voice": True},
            "human_v2": {"voice": True, "candor": True},
            "human_life": {"life": True},
        }[variant]
        text = speak_human(w, agent, view, tick, thread, kind, real, **opts)
    return {
        "case": case["name"],
        "variant": variant,
        "agent": agent.name,
        "name": w.name[agent.name],
        "kind": "talk",
        "text": text,
        "refused": None,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cases", nargs="+", type=Path)
    p.add_argument("--variants", default="base,human")
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--out", type=Path, required=True)
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
        preset = load_c15_scenario(R.scenario_of(case)).preset
        loop, _ = build(case, real)
        whos = names(case, loop)
        for variant in args.variants.split(","):
            jobs = [R.prepare(case, real, who) for who in whos for _ in range(args.k)]
            with ThreadPoolExecutor(args.workers) as pool:
                res = list(pool.map(lambda j: _safe(case, variant, j, real, preset), jobs))
            rows += res
            print(f"## {case['name']} [{variant}]")
            for r in res:
                print(f"   {r.get('name', r['agent'])}: {r.get('text') or r.get('error')}"[:260])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("usage:", json.dumps(real.usage, ensure_ascii=False)[:200])


def _safe(case, variant, prepared, real, preset):
    try:
        return one(case, variant, prepared, real, preset)
    except Exception as exc:
        return {
            "case": case["name"],
            "variant": variant,
            "agent": prepared[2].name,
            "error": repr(exc)[:300],
        }


if __name__ == "__main__":
    main()
