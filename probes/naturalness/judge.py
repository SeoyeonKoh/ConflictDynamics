# ruff: noqa: E501, E731, E741, UP045  (research harness: long Korean prompt text)
"""Blind LLM judgements over result files.

pairwise: for each (case, agent, i) pair two variants' outputs, ask which is more like a real
          office worker (both orders, to cancel position bias); also flag machine-talk and
          knowledge a person could not have.
attribution: for persona-contrast cases, match each agent's line to a style-only persona card.
"""

import argparse
import json
import random
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))
import human  # noqa: E402
import run as R  # noqa: E402,F401  (cwd)

from conflict_sim.company_runtime import build_company_config  # noqa: E402
from conflict_sim.llm import OpenAIBackend, create_openai_client  # noqa: E402

KIND_DESC = {
    "work": "자기 일을 함",
    "rest": "쉬거나 자잘한 일",
    "move": "자리를 옮김",
    "eat": "밥을 먹음",
    "talk": "옆에 있는 사람에게 직접 말을 검",
    "message": "메신저를 보냄",
    "chat": "메신저 대화를 이어감",
    "report": "상사에게 보고",
    "approve": "검토 중인 일을 승인",
    "reject": "검토 중인 일을 반려",
    "assign": "일을 배정",
    "help": "남의 일을 도움",
    "ask_help": "도움을 요청",
    "leave": "퇴근",
    "gossip": "뒷얘기를 전함",
    "request": "마감 연장 요청",
}

PAIR_SYS = """너는 한국 회사 조직 행동을 연구하는 관찰자다. 사내 시뮬레이션에서 한 사람이 어떤 상황에서 다음 15분 동안 한
행동(과 한 말)을 두 가지 후보로 보여 준다. 실제 한국 회사에서 그 사람이 그 상황에서 했을 법한 행동·말에 더 가까운 쪽을
골라라. 일을 더 잘 처리하는 쪽이 아니라, 실제 사람다운 쪽이다. 사람은 이름으로 부르고, 업무를 코드로 부르지 않으며,
보고서처럼 말하지 않고, 같은 걸 계속 되묻지 않고, 기분과 성격이 드러나며, 자기가 들은 것만 안다.
JSON으로만 답한다: {"winner": "A" 또는 "B" 또는 "tie", "why": 한 문장,
"machine_A": A가 시스템·보고서 같은 말투인지(true/false), "machine_B": 같은 판단,
"impossible_A": A가 이 사람이 알 수 없었을 정보를 아는 듯 말하는지(true/false), "impossible_B": 같은 판단}"""


class Pair(BaseModel):
    winner: str
    why: str
    machine_A: bool
    machine_B: bool
    impossible_A: bool
    impossible_B: bool


ATTR_SYS = """사내 시뮬레이션의 여러 사람이 같은 상황에서 한 말을 보여 준다. 말투와 태도만 보고 각 말(A, B, ...)이 어느
성격 설명(1, 2, ...)의 사람인지 맞혀라. 각 번호는 한 번씩만 쓴다.
JSON으로만 답한다: {"match": [{"line": "A", "persona": 3}, ...]}"""


class Match(BaseModel):
    line: str
    persona: int


class Matches(BaseModel):
    match: list[Match]


def describe(r, w_names):
    if r.get("kind") == "talk" and not r.get("task") and "reflection" not in r:  # a speech row
        return f'말: "{r["text"]}"'
    what = KIND_DESC.get(r["kind"], r["kind"])
    obj = (
        r.get("task_title")
        or w_names.get(r.get("target") or "", "")
        or human.PLACE_KO.get(r.get("place") or "", "")
    )
    s = f"행동: {what}" + (f" ({obj})" if obj else "")
    if r.get("targets"):
        s += f", 상대: {', '.join(w_names.get(t, t) for t in r['targets'])}"
    if r.get("text"):
        s += f'\n말: "{r["text"]}"'
    if r.get("refused"):
        s += "\n(이 행동은 실제로는 되지 않았다)"
    return s


def situation_of(case_file):
    text = Path(case_file).read_text(encoding="utf-8")
    comment = " ".join(l.lstrip("# ") for l in text.splitlines() if l.startswith("#"))
    case = yaml.safe_load(text)
    extra = ""
    ctx = case.get("context", {})
    if ctx.get("inbox"):
        extra += " 방금 받은 메시지: " + " / ".join(
            f"{m['sender']}: {m['text']}" for m in ctx["inbox"]
        )
    if case.get("speak"):
        sp = case["speak"]
        extra += " 대화: " + " / ".join(
            f"{p['speaker']}: {p['text']}" for p in [sp["root"], *sp.get("before", [])]
        )
    return case["name"], comment + extra


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["pairwise", "attribution"])
    p.add_argument("--results", nargs="+", type=Path, required=True)
    p.add_argument("--cases", type=Path, required=True, help="case directory")
    p.add_argument("--a", default="base")
    p.add_argument("--b", default="human")
    p.add_argument("--variants", default="base,human")
    p.add_argument("--only", default="", help="comma list of case-name prefixes")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    cfg = build_company_config(backend="openai")
    real = OpenAIBackend(
        create_openai_client(Path.cwd() / ".env"),
        max_tokens_decide=600,
        reasoning_effort=cfg.reasoning_effort,
        max_total_tokens=4_000_000,
        max_input_chars=cfg.max_input_chars,
    )
    rows = [json.loads(l) for f in args.results for l in open(f) if l.strip()]
    rows = [r for r in rows if "error" not in r]
    if args.only:
        rows = [r for r in rows if any(r["case"].startswith(x) for x in args.only.split(","))]
    situations = dict(situation_of(f) for f in sorted(args.cases.glob("*.yaml")))
    names = {r["agent"]: r["name"] for r in rows}
    ids = {}  # id → name for the judge's descriptions
    for pid, name in names.items():
        ids[pid] = name
    out = []
    if args.mode == "pairwise":
        grouped = defaultdict(lambda: defaultdict(list))
        for r in rows:
            grouped[(r["case"], r["agent"])][r["variant"]].append(r)
        jobs = []
        for (case, agent), by in grouped.items():
            for ra, rb in zip(by.get(args.a, []), by.get(args.b, [])):
                for flip in (False, True):
                    jobs.append((case, agent, ra, rb, flip))

        def judge(job):
            case, agent, ra, rb, flip = job
            first, second = (rb, ra) if flip else (ra, rb)
            situ = situations.get(case, case)
            situ = situ.replace("HDS-", "HDS-")
            for pid, nm in ids.items():
                situ = situ.replace(pid, nm)
            known = ra.get("situation") or rb.get("situation")
            if known:  # what the person legitimately knew, so acting on it is not "impossible"
                situ += "\n\n이 사람이 이 시점에 알고 있던 것:\n" + known[:3500]
            prompt = (
                f"상황: {situ}\n이 사람: {names[agent]}\n\n[A]\n{describe(first, ids)}\n\n"
                f"[B]\n{describe(second, ids)}"
            )
            raw = real.complete(
                system=PAIR_SYS,
                prompt=prompt,
                model="gpt-6-luna",
                temperature=0,
                json_mode=True,
                schema=Pair,
            )
            v = Pair.model_validate_json(raw)
            win = {"A": args.b if flip else args.a, "B": args.a if flip else args.b}.get(
                v.winner, "tie"
            )
            mach = {
                args.a: v.machine_B if flip else v.machine_A,
                args.b: v.machine_A if flip else v.machine_B,
            }
            imp = {
                args.a: v.impossible_B if flip else v.impossible_A,
                args.b: v.impossible_A if flip else v.impossible_B,
            }
            return {
                "case": case,
                "agent": agent,
                "winner": win,
                "machine": mach,
                "impossible": imp,
                "why": v.why,
            }

        with ThreadPoolExecutor(10) as pool:
            out = list(pool.map(judge, jobs))
        report_pairwise(out, args.a, args.b)
    else:
        personas = {p_["id"]: p_ for p_ in human._personas("korean_enterprise_10_ko")}

        def card(pid):
            p_ = personas[pid]
            return (
                f"말투: {p_['communication_style']} {human.DISC_KO[p_['disc']]} 압박을 받으면: {p_['pressure_response']} "
                f"갈등이 생기면: {p_['conflict_engagement_style']} 취미: {', '.join(p_['hobbies'])}"
            )

        jobs = []
        for variant in args.variants.split(","):
            grouped = defaultdict(lambda: defaultdict(list))
            for r in rows:
                if r["variant"] == variant:
                    grouped[r["case"]][r["agent"]].append(r)
            for case, by in grouped.items():
                agents = sorted(by)
                k = min(len(v) for v in by.values())
                for i in range(k):
                    jobs.append((variant, case, agents, [by[a][i] for a in agents]))

        def attribute(job):
            variant, case, agents, lines = job
            order = agents[:]
            rng_local = random.Random(hash((variant, case, lines[0]["text"])) & 0xFFFF)
            rng_local.shuffle(order)
            cards = agents[:]
            rng_local.shuffle(cards)
            text = {a: l["text"] or describe(l, ids) for a, l in zip(agents, lines)}
            letters = "ABCDEFGH"
            prompt = "성격 설명:\n" + "\n".join(f"{i + 1}. {card(a)}" for i, a in enumerate(cards))
            prompt += "\n\n말:\n" + "\n".join(
                f"{letters[i]}. {text[a]}" for i, a in enumerate(order)
            )
            for pid, nm in ids.items():  # names would give it away
                prompt = prompt.replace(nm + "님", "OO님")
            raw = real.complete(
                system=ATTR_SYS,
                prompt=prompt,
                model="gpt-6-luna",
                temperature=0,
                json_mode=True,
                schema=Matches,
            )
            m = Matches.model_validate_json(raw)
            correct = 0
            for row in m.match:
                li = letters.index(row.line) if row.line in letters else -1
                if (
                    0 <= li < len(order)
                    and 1 <= row.persona <= len(cards)
                    and cards[row.persona - 1] == order[li]
                ):
                    correct += 1
            return {"variant": variant, "case": case, "correct": correct, "n": len(agents)}

        with ThreadPoolExecutor(10) as pool:
            out = list(pool.map(attribute, jobs))
        agg = defaultdict(lambda: [0, 0])
        for o in out:
            agg[(o["case"], o["variant"])][0] += o["correct"]
            agg[(o["case"], o["variant"])][1] += o["n"]
        for (case, v), (c, n) in sorted(agg.items()):
            print(f"{case:30} {v:12} attribution {c}/{n} = {c / n:.0%} (chance {1 / 6:.0%})")
    with args.out.open("a") as f:
        for o in out:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    print("usage:", json.dumps(real.usage, ensure_ascii=False)[:160])


def report_pairwise(out, a, b):
    by = defaultdict(list)
    for o in out:
        by[o["case"]].append(o)
    print(
        f"{'case':42} {'n':>3} {a + ' win':>9} {b + ' win':>10} {'tie':>4}  machine {a}/{b}  impossible {a}/{b}"
    )
    for case, os_ in sorted(by.items()) + [("ALL", out)]:
        n = len(os_)
        w = lambda v: sum(o["winner"] == v for o in os_)  # noqa: E731
        m = lambda v: sum(o["machine"][v] for o in os_)  # noqa: E731
        i = lambda v: sum(o["impossible"][v] for o in os_)  # noqa: E731
        print(
            f"{case[:42]:42} {n:3d} {w(a):9d} {w(b):10d} {w('tie'):4d}  {m(a):3d}/{m(b):<3d}         {i(a):3d}/{i(b):<3d}"
        )


if __name__ == "__main__":
    main()
