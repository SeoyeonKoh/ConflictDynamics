"""One completion interface for a local demo and the optional OpenAI SDK."""

import hashlib
import json
import logging
import math
import os
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from .models import EXPRESSION_VALENCE, Expression

if TYPE_CHECKING:
    from openai import OpenAI


class LLMError(RuntimeError):
    """A failed or incomplete API response; never interpreted as silence."""


def create_openai_client(env_file: Path) -> "OpenAI":
    """Read credentials outside Hydra config so they are not saved in run metadata."""
    try:
        from dotenv import load_dotenv
        from openai import OpenAI
    except ImportError as exc:
        raise LLMError("Install the LLM extra: uv sync --extra llm") from exc
    load_dotenv(env_file, override=False)
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise LLMError(f"Set OPENAI_API_KEY in {env_file} or your shell environment")
    return OpenAI(timeout=60.0, max_retries=2)


class LanguageModel(Protocol):
    def complete(
        self, *, system: str, prompt: str, model: str, temperature: float, json_mode: bool
    ) -> str: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def expression_for(stress: float, mood: float) -> Expression:
    """The demo's fixed bands from internal state to a face; the first matching row wins."""
    if stress >= 0.7:
        return "anxious"
    if mood <= -0.6:
        return "angry"
    if mood <= -0.3:
        return "annoyed"
    if stress >= 0.4:
        return "tired"
    if mood >= 0.5:
        return "amused"
    if mood >= 0.2:
        return "pleased"
    return "neutral"


class DemoBackend:
    """Rule-based smoke-test responses. These are not research observations.

    The prompt kind is read off the payload's top-level keys: `view` → act, `tasks` without
    `view` → daily plan, `utterances` → session decide (JSON mode) or speak (text).
    """

    EMBED_DIM = 32

    def __init__(self, *, blocked_nudge_ticks: int = 2, blocked_report_ticks: int = 4):
        self.blocked_nudge_ticks = blocked_nudge_ticks
        self.blocked_report_ticks = blocked_report_ticks

    def complete(
        self, *, system: str, prompt: str, model: str, temperature: float, json_mode: bool
    ) -> str:
        payload = json.loads(prompt)
        if "view" in payload:
            return json.dumps(self._act(payload["view"], payload.get("manager")))
        if "tasks" in payload:
            return json.dumps({"plan": self._plan(payload["tasks"])})
        if json_mode:
            return json.dumps(
                {
                    "urge": 0.6,
                    "reply_to": payload["utterances"][-1]["id"],
                    "reflection": "I still want to compare the cited passages. "
                    "I would like the discussion to resolve which source supports the claim.",
                    "expression": expression_for(payload.get("stress", 0), payload.get("mood", 0)),
                    "importance": 3,
                    "valence": 0,
                    "arousal": 0.1,
                }
            )
        return "Could we compare the cited passages before changing the article?"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()[: self.EMBED_DIM]
            raw = [byte / 127.5 - 1 for byte in digest]
            norm = math.sqrt(sum(x * x for x in raw))
            vectors.append([x / norm for x in raw])
        return vectors

    def _act(self, view: dict, manager: str | None) -> dict:
        expression = expression_for(view["stress"], view["mood"])
        valence = EXPRESSION_VALENCE[expression]
        action = {
            "expression": expression,
            "reflection": "Following the plan for now.",
            "importance": 3,
            "valence": valence,
            "arousal": abs(valence),
        }
        if view["phase"] == "lunch":
            if view["present"]:
                return action | {"kind": "talk", "text": "How is your morning going?"}
            return action | {"kind": "eat"}
        for blocked in view["blocked"]:
            waited = view["tick"] - blocked["since_tick"]
            if waited == self.blocked_report_ticks and manager is not None:
                text = f"{blocked['waiting_on']} has held up {blocked['task']} for {waited} ticks."
                return action | {"kind": "report", "target": manager, "text": text}
            if waited == self.blocked_nudge_ticks:
                text = f"Any update on {blocked['waiting_on']}? {blocked['task']} is waiting on it."
                return action | {"kind": "message", "target": blocked["owner"], "text": text}
        waiting = {blocked["task"] for blocked in view["blocked"]}
        open_tasks = [t for t in view["tasks"] if t["progress"] < 1 and t["id"] not in waiting]
        if open_tasks:
            return action | {"kind": "work", "task": min(open_tasks, key=lambda t: t["due"])["id"]}
        return action | {"kind": "rest"}

    def _plan(self, tasks: list[dict]) -> list[str]:
        items = ["Arrive and check messages."]
        items += [f"Work on {t['id']}: {t['description']}" for t in tasks if t["progress"] < 1]
        items += ["Lunch with whoever is in the cafeteria.", "Afternoon: continue the open tasks."]
        while len(items) < 5:
            items.append("Review progress and tidy up.")
        return items[:7] + ["Wrap up and leave."]


class OpenAIBackend:
    def __init__(
        self,
        client: "OpenAI",
        *,
        model_embed: str | None = None,
        reasoning_effort: str | None = None,
        max_tokens_decide: int = 512,
        max_tokens_speak: int = 384,
        max_total_tokens: int = 100_000,
        max_input_chars: int = 64_000,
    ):
        self.client = client
        self.model_embed = model_embed
        self.reasoning_effort = reasoning_effort
        self.output_limits = {True: max_tokens_decide, False: max_tokens_speak}
        self.max_total_tokens = max_total_tokens
        self.max_input_chars = max_input_chars
        self.usage = {
            kind: dict(
                calls=0,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cached_tokens=0,
                reasoning_tokens=0,
                missing_usage=0,
            )
            for kind in ("decide", "speak")
        }
        self.usage["embed"] = dict(calls=0, prompt_tokens=0, total_tokens=0)

    def _spent(self) -> int:
        return sum(row["total_tokens"] for row in self.usage.values())

    def complete(
        self, *, system: str, prompt: str, model: str, temperature: float, json_mode: bool
    ) -> str:
        from openai import APIError

        if self._spent() >= self.max_total_tokens:
            raise LLMError("Run token budget reached; no further API calls")
        if len(system) + len(prompt) > self.max_input_chars:
            raise LLMError(
                "Input exceeds max_input_chars; reduce context or memory before retrying"
            )
        options = {"response_format": {"type": "json_object"}} if json_mode else {}
        if self.reasoning_effort is not None:
            options["reasoning_effort"] = self.reasoning_effort
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_completion_tokens=self.output_limits[json_mode],
                **options,
            )
        except APIError as exc:
            # Provider error bodies can echo credentials; report only type and status.
            status = getattr(exc, "status_code", None)
            detail = f", HTTP {status}" if status is not None else ""
            raise LLMError(f"LLM request failed: {type(exc).__name__}{detail}") from None
        counters = self.usage["decide" if json_mode else "speak"]
        counters["calls"] += 1
        if response.usage:
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                counters[key] += getattr(response.usage, key)
            counters["cached_tokens"] += (
                getattr(response.usage.prompt_tokens_details, "cached_tokens", 0) or 0
            )
            counters["reasoning_tokens"] += (
                getattr(response.usage.completion_tokens_details, "reasoning_tokens", 0) or 0
            )
        else:
            counters["missing_usage"] += 1
        logging.getLogger(__name__).info(
            "LLM usage %s",
            json.dumps(
                {
                    "model": response.model,
                    "kind": "decide" if json_mode else "speak",
                    "usage": response.usage.model_dump() if response.usage else None,
                }
            ),
        )
        if response.usage is None:
            raise LLMError("LLM returned no usage; cannot enforce the run token budget")
        if not response.choices:
            raise LLMError("LLM returned no choices")
        choice = response.choices[0]
        if choice.finish_reason != "stop" or choice.message.refusal:
            raise LLMError(f"LLM did not complete a reply (finish_reason={choice.finish_reason})")
        if not choice.message.content or not choice.message.content.strip():
            raise LLMError("LLM returned empty content")
        return choice.message.content

    def embed(self, texts: list[str]) -> list[list[float]]:
        from openai import APIError

        if self.model_embed is None:
            raise LLMError("Set model_embed before embedding with the openai backend")
        if self._spent() >= self.max_total_tokens:
            raise LLMError("Run token budget reached; no further API calls")
        if not texts:
            return []
        try:
            response = self.client.embeddings.create(model=self.model_embed, input=texts)
        except APIError as exc:
            status = getattr(exc, "status_code", None)
            detail = f", HTTP {status}" if status is not None else ""
            raise LLMError(f"Embedding request failed: {type(exc).__name__}{detail}") from None
        counters = self.usage["embed"]
        counters["calls"] += 1
        if response.usage is None:
            raise LLMError("LLM returned no usage; cannot enforce the run token budget")
        counters["prompt_tokens"] += response.usage.prompt_tokens
        counters["total_tokens"] += response.usage.total_tokens
        if len(response.data) != len(texts):
            raise LLMError("Embedding response count does not match the input")
        return [row.embedding for row in sorted(response.data, key=lambda row: row.index)]
