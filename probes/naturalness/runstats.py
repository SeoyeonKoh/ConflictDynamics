# ruff: noqa: E501, E731, E741, UP045  (research harness: long Korean prompt text)
"""Unnaturalness metrics over a run's utterances and actions."""

import json
import re
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher

TASK_ID = re.compile(r"\b(T\d{2}|P\d{1,2}-[a-z]+)\b")
AGENT_ID = re.compile(r"HDS-\d{3}")
JARGON = re.compile(
    r"lifecycle|ready|in_progress|틱|재문의|완료 통지|통지|착수 가능|착수할 수 없|선행 (조건|작업|입력|산출물)|차단|작업 가능 목록|검토 대기|산출물"
)
BOILER = re.compile(
    r"(확인|도착|준비되는|받는) ?(즉시|대로)|확정하지 않|반복하지 않|공유해 주(세요|시면)|알려 주(세요|시면)"
)


def load(d):
    utt = [json.loads(l) for l in open(f"{d}/corpus/utterances.jsonl")]
    ev = [json.loads(l) for l in open(f"{d}/events.jsonl")]
    return utt, ev


def stats(d):
    utt, ev = load(d)
    utt = [
        u
        for u in utt
        if not (u.get("reply_to") is None and "meeting" in (u.get("conversation_id") or ""))
    ]
    n = len(utt)
    texts = [u["text"] for u in utt]
    r = lambda rx: sum(bool(rx.search(t)) for t in texts) / n
    # repeats: same speaker, same conversation, similarity > .6 to an earlier own line
    rep = 0
    by = defaultdict(list)
    for u in utt:
        key = u["speaker"]
        if any(
            SequenceMatcher(None, u["text"], p).ratio() > 0.5
            for t, p in by[key]
            if u["timestamp"] - t <= 8
        ):
            rep += 1
        by[key].append((u["timestamp"], u["text"]))
    acts = [e for e in ev if e["kind"] == "action"]
    kinds = Counter(e["payload"].get("kind") for e in acts)
    # rest streaks at work places
    seq = defaultdict(list)
    for e in acts:
        seq[e["actor"]].append(e["payload"].get("kind"))
    streak = 0
    for a, ks in seq.items():
        run = 0
        for k in ks:
            run = run + 1 if k == "rest" else 0
            if run >= 4:
                streak += 1
    print(
        f"{d.split('/')[1]}: utterances {n}, task-id {r(TASK_ID):.0%}, agent-id {r(AGENT_ID):.0%}, "
        f"jargon {r(JARGON):.0%}, boilerplate {r(BOILER):.0%}, self-repeat {rep / n:.0%}, "
        f"mean len {sum(map(len, texts)) / n:.0f} chars"
    )
    tot = sum(kinds.values())
    print(
        "   actions:",
        {k: f"{v / tot:.0%}" for k, v in kinds.most_common(9)},
        f"rest-streak ticks(>=4) {streak}",
    )


for d in sys.argv[1:]:
    stats(d)
