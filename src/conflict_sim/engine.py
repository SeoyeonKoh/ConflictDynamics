"""Scheduling and probability gates, independent of LLMs and scoring."""

import random
import re
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import TypeAdapter

from .config import RunConfig
from .models import Decision, Probability, Thread, Utterance


class Participant(Protocol):
    name: str
    availability: float
    last_seen: int

    def decide(self, thread: Thread) -> Decision: ...

    def speak(self, thread: Thread, target: str | None) -> str: ...


@dataclass
class RunResult:
    thread: Thread
    ticks: int = 0
    stop_reason: str = "max_ticks"
    decisions: list[dict] = field(default_factory=list)


def is_addressed(agent: Participant, thread: Thread) -> bool:
    """A reply or an @name mention in unread posts can wake an editor."""
    mention = re.compile(r"(?<!\w)@" + re.escape(agent.name) + r"(?![\w-])", re.IGNORECASE)
    for utterance in thread.utterances[agent.last_seen :]:
        if utterance.speaker == agent.name:
            continue
        if mention.search(utterance.text):
            return True
        if utterance.reply_to is not None:
            if thread.get(utterance.reply_to).speaker == agent.name:
                return True
    return False


def run(agents: list[Participant], thread: Thread, cfg: RunConfig) -> RunResult:
    """Append posts in place. Each agent is evaluated at most once per tick."""
    if not thread.utterances:
        raise ValueError("A simulation requires a seed thread")
    if not 3 <= len(agents) <= 6 or len({a.name for a in agents}) != len(agents):
        raise ValueError("Use 3 to 6 agents with unique names")
    for agent in agents:
        TypeAdapter(Probability).validate_python(agent.availability, strict=True)
        if not 0 <= agent.last_seen <= len(thread.utterances):
            raise ValueError("last_seen must be an index into the thread")

    rng = random.Random(cfg.random_seed)
    result = RunResult(thread)
    first_tick = thread.utterances[-1].timestamp + 1
    silence = 0

    def post(agent: Participant, decision: Decision, event: dict, tick: int) -> bool:
        if rng.random() >= decision.urge * agent.availability:
            event["reason"] = "probability_gate"
            return False
        target = decision.reply_to if decision.reply_to is not None else thread.utterances[0].id
        # A namespace based on the root prevents collisions across different seed conversations.
        utterance_id = f"{thread.utterances[0].id}:sim:{len(thread.utterances)}"
        while any(u.id == utterance_id for u in thread.utterances):
            utterance_id += ":next"
        thread.add(
            Utterance(
                id=utterance_id,
                speaker=agent.name,
                text=agent.speak(thread, target),
                reply_to=target,
                timestamp=tick,
            )
        )
        agent.last_seen = len(thread.utterances)
        event.update(posted=True, reason="posted", utterance_id=utterance_id)
        return True

    for step in range(cfg.max_ticks):
        tick = first_tick + step
        ordered = list(agents)
        if cfg.rule == "random":
            rng.shuffle(ordered)
        bids = []
        posted = False
        for agent in ordered:
            event = {"tick": tick, "agent": agent.name, "posted": False}
            result.decisions.append(event)
            if agent.last_seen == len(thread.utterances):
                event["reason"] = "no_new_posts"
                continue
            if (
                cfg.rule == "event_driven"
                and agent.last_seen > 0
                and not is_addressed(agent, thread)
            ):
                agent.last_seen = len(thread.utterances)
                event["reason"] = "no_event"
                continue
            if agent.availability == 0:
                # Unavailable agents have not read the new posts.
                event["reason"] = "unavailable"
                continue
            decision = agent.decide(thread)
            if decision.reply_to is not None:
                thread.get(decision.reply_to)
            event.update(
                urge=decision.urge,
                reply_to=decision.reply_to,
                probability=decision.urge * agent.availability,
                reason="not_selected",
            )
            agent.last_seen = len(thread.utterances)
            if cfg.rule == "bidding":
                bids.append((agent, decision, event))
            elif post(agent, decision, event, tick):
                posted = True

        if bids:
            highest = max(decision.urge for _, decision, _ in bids)
            finalists = [bid for bid in bids if bid[1].urge == highest]
            winner, decision, event = rng.choice(finalists)
            posted = post(winner, decision, event, tick)
        result.ticks = step + 1
        silence = 0 if posted else silence + 1
        if silence >= cfg.silence_limit:
            result.stop_reason = "silence"
            break
    return result
