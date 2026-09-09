"""Scheduling and probability gates, independent of configuration and storage."""

import random
import re
from dataclasses import dataclass, field

from .agent import Agent
from .models import Decision, Thread, Utterance


@dataclass
class RunResult:
    thread: Thread
    ticks: int = 0
    stop_reason: str = "max_ticks"
    decisions: list[dict] = field(default_factory=list)


def is_addressed(agent: Agent, thread: Thread) -> bool:
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


def run(
    agents: list[Agent],
    thread: Thread,
    *,
    rule: str,
    max_ticks: int,
    silence_limit: int,
    random_seed: int,
) -> RunResult:
    """Append posts in place. Each agent is evaluated at most once per tick.

    Agent count, name uniqueness, and availability are already validated by Config.
    """
    if not thread.utterances:
        raise ValueError("A simulation requires a seed thread")

    rng = random.Random(random_seed)
    result = RunResult(thread)
    first_tick = thread.utterances[-1].timestamp + 1
    silence = 0

    def post(agent: Agent, decision: Decision, event: dict, tick: int) -> bool:
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

    for step in range(max_ticks):
        tick = first_tick + step
        ordered = list(agents)
        if rule == "random":
            rng.shuffle(ordered)
        bids = []
        posted = False
        for agent in ordered:
            event = {"tick": tick, "agent": agent.name, "posted": False}
            result.decisions.append(event)
            if agent.last_seen == len(thread.utterances):
                event["reason"] = "no_new_posts"
                continue
            if rule == "event_driven" and agent.last_seen > 0 and not is_addressed(agent, thread):
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
            if rule == "bidding":
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
        if silence >= silence_limit:
            result.stop_reason = "silence"
            break
    return result
