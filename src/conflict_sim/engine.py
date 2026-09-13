"""Scheduling and probability gates, independent of configuration and storage."""

import random
import re
from collections.abc import Callable
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
    on_update: Callable[[RunResult, str], None] | None = None,
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
    pending: dict[str, tuple[Decision, int]] = {}

    def update(message: str) -> None:
        if on_update is not None:
            on_update(result, message)

    update("Seed loaded · ready to begin")

    def post(agent: Agent, decision: Decision, event: dict, tick: int) -> bool:
        if rng.random() >= decision.urge * agent.availability:
            event["reason"] = "probability_gate"
            return False
        target = decision.reply_to if decision.reply_to is not None else thread.utterances[0].id
        # A namespace based on the root prevents collisions across different seed conversations.
        utterance_id = f"{thread.utterances[0].id}:sim:{len(thread.utterances)}"
        while any(u.id == utterance_id for u in thread.utterances):
            utterance_id += ":next"
        update(f"Tick {tick} · {agent.name} is writing a reply")
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
        pending.pop(agent.name, None)
        event.update(posted=True, reason="posted", utterance_id=utterance_id)
        update(f"Tick {tick} · {agent.name} posted a reply")
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
            if agent.availability == 0:
                # Unavailable agents have not read the new posts.
                event["reason"] = "unavailable"
                continue
            if agent.last_seen < len(thread.utterances):
                if (
                    rule == "event_driven"
                    and agent.last_seen > 0
                    and agent.name not in pending
                    and not is_addressed(agent, thread)
                ):
                    agent.last_seen = len(thread.utterances)
                    event["reason"] = "no_event"
                    continue
                update(f"Tick {tick} · {agent.name} is considering the conversation")
                decision = agent.decide(thread)
                if decision.reply_to is not None:
                    thread.get(decision.reply_to)
                agent.last_seen = len(thread.utterances)
                decision_tick, source = tick, "new"
            elif agent.name in pending:
                decision, decision_tick = pending[agent.name]
                source = "retry"
            else:
                event["reason"] = "no_new_posts"
                continue
            event.update(
                decision.model_dump(),
                decision_source=source,
                decision_tick=decision_tick,
                probability=decision.urge * agent.availability,
                reason="no_urge" if decision.urge == 0 else "not_selected",
            )
            update(f"Tick {tick} · {agent.name}'s decision is ready")
            if decision.urge == 0:
                pending.pop(agent.name, None)
                continue
            pending[agent.name] = (decision, decision_tick)
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
            update(f"Tick {tick} finished · silence limit reached")
            break
        update(f"Tick {tick} finished")
    return result
