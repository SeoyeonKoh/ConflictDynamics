# ruff: noqa: E501, E731, E741, UP045  (research harness: long Korean prompt text)
"""Text and action metrics per variant over result JSON lines."""

import json
import re
import sys
from collections import Counter, defaultdict

TASK_ID = re.compile(r"(?<![A-Za-z0-9])(T\d{2}|P\d{1,2}-[a-z]+)(?![A-Za-z0-9])")
AGENT_ID = re.compile(r"HDS-\d{3}")
TICK = re.compile(r"\d+\s*틱|틱\(|재문의 가능|ready|in_progress|lifecycle|review로|\d+(\.\d+)?%")
JARGON = re.compile(
    r"완료 통지|착수 가능|착수할 수 없|선행 (조건|작업|입력|산출물)|차단 (상태|위험)|산출물|확인 부탁드립니다|공유해 주세요"
)
HUMAN = re.compile(r"님[,\s]|요[.?!]|요$|네요|어요|아요|죠|거든요|더라고요|ㅎㅎ|ㅠ")


def load(paths):
    rows = []
    for p in paths:
        rows += [json.loads(l) for l in open(p) if l.strip()]
    return [r for r in rows if "error" not in r]


def summarize(rows, by=("variant",)):
    groups = defaultdict(list)
    for r in rows:
        groups[tuple(r[k] for k in by)].append(r)
    print(
        f"{'group':40} {'n':>3} {'refused':>7} {'spoke':>5} {'taskID':>6} {'agentID':>7} {'tick/sys':>8} "
        f"{'jargon':>6} {'colloq':>6} {'len':>4}  kinds"
    )
    for key, rs in sorted(groups.items()):
        n = len(rs)
        texts = [
            r["text"]
            for r in rs
            if r.get("text") and r["kind"] in ("talk", "message", "report", "gossip")
        ]
        t = len(texts) or 1
        rate = lambda rx: sum(bool(rx.search(x)) for x in texts) / t
        kinds = Counter(r["kind"] for r in rs)
        print(
            f"{' / '.join(key)[:40]:40} {n:3d} {sum(bool(r['refused']) for r in rs) / n:7.0%} {len(texts) / n:5.0%} "
            f"{rate(TASK_ID):6.0%} {rate(AGENT_ID):7.0%} {rate(TICK):8.0%} {rate(JARGON):6.0%} {rate(HUMAN):6.0%} "
            f"{sum(map(len, texts)) / t:4.0f}  {dict(kinds.most_common(5))}"
        )


if __name__ == "__main__":
    rows = load(sys.argv[1:])
    summarize(rows)
    print()
    summarize(rows, by=("case", "variant"))
