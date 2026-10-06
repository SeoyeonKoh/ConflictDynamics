"""One completion interface for a local demo and the optional OpenAI SDK."""

import hashlib
import json
import logging
import math
import os
import random
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import numpy as np
from pydantic import BaseModel

from .models import EXPRESSION_VALENCE, Expression
from .usage_audit import (
    annotate,
    completion_metadata,
    current_call_type,
    embedding_metadata,
    log_call,
    traced,
)

if TYPE_CHECKING:
    from openai import OpenAI


class LLMError(RuntimeError):
    """A failed or incomplete API response; never interpreted as silence."""


# C-16 (2026-10-02): 20 agents ran over the 200k tokens/minute limit for minutes at a time.
RATE_LIMIT_WAITS = 12  # attempts after the SDK's own retries, about ten minutes in all
RATE_LIMIT_SECONDS = 30.0  # when the response names no reset time


def _retry_after(headers) -> float | None:
    """Seconds until the limit resets, from `retry-after(-ms)` or `x-ratelimit-reset-*`
    ("42.396s", "1m2s", "120ms"), with jitter so waiting threads do not return together."""
    if (ms := headers.get("retry-after-ms")) is not None:
        seconds = float(ms) / 1000
    elif (after := headers.get("retry-after")) is not None and after.replace(".", "").isdigit():
        seconds = float(after)
    else:
        resets = [
            headers.get("x-ratelimit-reset-tokens"),
            headers.get("x-ratelimit-reset-requests"),
        ]
        parsed = [_duration(value) for value in resets if value]
        if not parsed:
            return None
        seconds = max(parsed)
    return min(seconds, 60.0) + random.uniform(1.0, 5.0)


def _duration(text: str) -> float:
    units = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}
    parts = re.findall(r"([\d.]+)(ms|s|m|h)", text)
    return sum(float(number) * units[unit] for number, unit in parts)


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
    return OpenAI(timeout=60.0, max_retries=8)  # 20 agents in parallel meet 429s; the SDK backs off


class LanguageModel(Protocol):
    def complete(
        self,
        *,
        system: str,
        prompt: str,
        model: str,
        temperature: float,
        json_mode: bool,
        schema: type[BaseModel] | None = None,
    ) -> str: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def strict_schema(model: type[BaseModel]) -> dict:
    """The model's JSON schema as OpenAI structured outputs accept it: every property required
    (an optional field stays nullable), no extra keys, and no `default` or `title` keywords."""

    def walk(node):
        if isinstance(node, list):
            return [walk(item) for item in node]
        if not isinstance(node, dict):
            return node
        node = {k: walk(v) for k, v in node.items() if k not in ("default", "title")}
        if "properties" in node:
            node["additionalProperties"] = False
            node["required"] = list(node["properties"])
        return node

    return walk(model.model_json_schema())


# A conversation payload carries a stress band, not the number: each band at its lower edge.
STRESS_BAND_FLOOR = {"medium": 0.4, "high": 0.7}


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
        self,
        *,
        system: str,
        prompt: str,
        model: str,
        temperature: float,
        json_mode: bool,
        schema: type[BaseModel] | None = None,
    ) -> str:
        payload = json.loads(prompt)
        if "finished_task" in payload:
            task = payload["finished_task"]
            text = f"{task['id']} ({task['description']}) is finished and ready for review."
            if task.get("deliverable"):
                cited = [i["id"] for i in task.get("inputs", [])]
                document = (
                    f"{task['id']}-1: {task['description']}, building on {cited or 'nothing'}."
                )
                return json.dumps({"document": document, "summary": text})
            return json.dumps({"summary": text})
        if "view" in payload:
            return json.dumps(
                self._act(payload["view"], payload.get("manager"), payload.get("task_notes", []))
            )
        if "tasks" in payload:
            return json.dumps({"plan": self._plan(payload)})
        if "appraise" in payload:
            return json.dumps({"appraisals": [
                {"person": p, "valence": 0.0, "arousal": 0.1, "reason": "They stayed on topic."}
                for p in payload["appraise"]
            ]})  # fmt: skip
        if "question" in payload:
            return json.dumps({"insights": self._insights(payload)})
        if "records" in payload:
            return json.dumps({"questions": self._questions(payload["records"])})
        if json_mode:
            return json.dumps(
                {
                    "urge": 0.6,
                    "reply_to": payload["utterances"][-1]["id"],
                    "reflection": "I still want to compare the cited passages. "
                    "I would like the discussion to resolve which source supports the claim.",
                    "expression": expression_for(
                        STRESS_BAND_FLOOR.get(payload.get("stress"), 0), payload.get("mood", 0)
                    ),
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

    def _act(self, view: dict, manager: str | None, notes: list[dict]) -> dict:
        expression = expression_for(view["stress"], view["mood"])
        valence = EXPRESSION_VALENCE[expression]
        action = {
            "expression": expression,
            "reflection": "Following the plan for now.",
            "importance": 3,
            "valence": valence,
            "arousal": abs(valence),
        }
        desk, food = _desk_and_food(
            view.get("places", {}), view["place"], view.get("resources", {})
        )
        if view["phase"] == "lunch":
            if view["present"] and view.get("places", {}).get(view["place"]) in EAT_KINDS:
                return action | {
                    "kind": "talk",
                    "targets": list(view["present"]),
                    "text": "How is your morning going?",
                }
            return action | {"kind": "eat", "place": food}
        # What the agent knows is blocked, from its own notes (the office's list is not shown).
        blocked_list = [
            {"task": n["task"], "waiting_on": w["task"], "owner": w.get("owner") or "nobody",
             "since_tick": n.get("since", view["tick"])}
            for n in notes
            if n.get("can_work") == "no"
            for w in n.get("waits_on", [])
        ]  # fmt: skip
        for blocked in blocked_list:
            waited = view["tick"] - blocked["since_tick"]
            if waited == self.blocked_report_ticks and manager is not None:
                text = f"{blocked['waiting_on']} has held up {blocked['task']} for {waited} ticks."
                return action | {"kind": "report", "target": manager, "text": text}
            if waited == self.blocked_nudge_ticks:
                text = f"Any update on {blocked['waiting_on']}? {blocked['task']} is waiting on it."
                return action | {"kind": "message", "target": blocked["owner"], "text": text}
        review = next(
            (
                task
                for task in view["tasks"]
                if task.get("lifecycle") == "review" and task.get("can_approve", False)
            ),
            None,
        )
        if review is not None:
            return action | {"kind": "approve", "task": review["id"]}
        unowned = next((task for task in view["tasks"] if task.get("role") == "assigner"), None)
        if unowned is not None:  # the demo manager hands it to whoever is nearby, else keeps it
            present = list(view["present"])
            target = present[0] if present else view["agent"]
            return action | {"kind": "assign", "task": unowned["id"], "target": target,
                             "targets": present[1:2]}  # fmt: skip
        waiting = {n["task"] for n in notes if n.get("can_work") == "no"}
        open_tasks = [
            task
            for task in view["tasks"]
            if task["progress"] < 1
            and task["id"] not in waiting
            and task.get("role", "owner") in ("owner", "contributor", "helper")
            and task.get("lifecycle", "ready") not in ("review", "done")
        ]
        if open_tasks:
            task = min(open_tasks, key=lambda t: t["due"])
            if task.get("role") == "owner" and task["remaining_ticks"] >= 3:
                if not task.get("help_wanted"):  # a long task asks for hands once
                    text = f"{task['id']} has {task['remaining_ticks']} ticks left; can you help?"
                    return action | {"kind": "ask_help", "task": task["id"], "text": text}
            return action | {"kind": "work", "task": task["id"], "place": desk}
        if view.get("help_wanted"):
            return action | {"kind": "help", "task": view["help_wanted"][0]["task"]}
        return action | {"kind": "rest"}

    def _plan(self, payload: dict) -> list[dict]:
        """Move to a desk, work the two most urgent tasks around lunch, chat over lunch, and leave
        the closing tick unplanned — what to do at the end of the day is a judgement."""
        first, last = payload["tick"], payload["last_tick"]
        desk, food = _desk_and_food(
            payload["places"], payload["place"], payload.get("resources", {})
        )
        if "replan" in payload:  # the rest of the day: work the most urgent tasks to the end
            tasks = sorted(
                (t for t in payload["tasks"] if t["progress"] < 1
                 and t.get("role", "owner") in ("owner", "contributor", "helper")),
                key=lambda task: task["due"],
            )  # fmt: skip
            return self._work(tasks[:2], first, last)
        lunch = first + (last + 1 - first) // 2  # the loop's lunch phase starts mid-day
        tasks = sorted(
            (
                task
                for task in payload["tasks"]
                if task["progress"] < 1
                and task.get("role", "owner") in ("owner", "contributor", "helper")
            ),
            key=lambda task: task["due"],
        )
        blocks = [_block("move", first + 1, f"Settle in at the {desk}.", place=desk)]
        blocks += self._work(tasks[:2], first + 1, lunch)
        blocks.append(_block("eat", lunch + 1, f"Lunch at the {food}.", place=food))
        blocks.append(_block("talk", lunch + 4, "How is everyone's morning going?", place=food))
        blocks += self._work(tasks[:2], lunch + 4, last)
        return blocks

    @staticmethod
    def _work(tasks: list[dict], start: int, end: int) -> list[dict]:
        if not tasks:
            return [_block("rest", end, "Nothing assigned; stay available.")]
        ends = [start + (end - start) // 2, end] if len(tasks) == 2 else [end]
        return [
            _block("work", until, f"Work on {t['id']}: {t['description']}", task=t["id"])
            for t, until in zip(tasks, ends)
        ]

    @staticmethod
    def _questions(records: list[dict]) -> list[str]:
        """One question per person seen, most negative first; then a routine question."""
        by_subject: dict[str, float] = {}
        for record in records:
            for subject in record.get("subjects", []):
                by_subject[subject] = by_subject.get(subject, 0.0) + record.get("valence", 0.0)
        people = sorted(by_subject, key=lambda name: by_subject[name])
        return [f"How is working with {name} going?" for name in people[:2]] + [
            "What did I get done?"
        ]

    @staticmethod
    def _insights(payload: dict) -> list[dict]:
        question, records = payload["question"], payload["records"]
        subject = next((s for r in records for s in r.get("subjects", []) if s in question), None)
        cited = [r for r in records if subject is None or subject in r.get("subjects", [])][:3]
        valence = sum(r.get("valence", 0.0) for r in cited) / len(cited) if cited else 0.0
        text = (
            f"{subject} has been {'hard' if valence < 0 else 'fine'} to work with today."
            if subject
            else "The day went roughly as planned."
        )
        return [
            {
                "text": text,
                "evidence": [r["id"] for r in cited],
                "importance": 6 if subject else 4,
                "valence": round(valence, 2),
                "arousal": round(abs(valence), 2),
                "subjects": [subject] if subject else [],
            }
        ]


WORK_KINDS = ("desk", "office", "focus_room")
EAT_KINDS = ("pantry", "cafeteria")


def _desk_and_food(places: dict, here: str, resources: dict | None = None) -> tuple[str, str]:
    resources = resources or {}
    desk = next(
        (
            place
            for place, kind in places.items()
            if kind in WORK_KINDS and resources.get(place, 1) > 0
        ),
        here,
    )
    food_places = [place for place, kind in places.items() if kind in EAT_KINDS]
    food = max(food_places, key=lambda place: resources.get(place, 1), default=desk)
    return desk, food


def _block(kind: str, until: int, text: str, **arguments: str) -> dict:
    return {"kind": kind, "until": until, "text": text} | arguments


class EmbedCache:
    """`embed` answered from an on-disk table when the model and text were seen before.

    Only embeddings are cached (plan §1-10): a `temperature 0.8` completion cached across runs
    would turn "3 runs per condition" into one run.
    """

    def __init__(
        self, backend: LanguageModel, path: Path, *, call_types: frozenset[str] | None = None
    ):
        self.backend = backend
        self.call_types = call_types  # None preserves the CLI's existing all-embedding cache.
        self.model = getattr(backend, "model_embed", None) or type(backend).__name__
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)  # judgements run in threads
        self.lock = threading.Lock()
        self.db.execute("create table if not exists embeddings (key text primary key, vector blob)")

    @property
    def usage(self):
        return self.backend.usage

    def complete(self, **request) -> str:
        return self.backend.complete(**request)

    @property
    def audit_path(self):
        return getattr(self.backend, "audit_path", None)

    @traced(None)
    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.call_types is not None and current_call_type() not in self.call_types:
            return self.backend.embed(texts)
        keys = [hashlib.sha256(f"{self.model}\n{text}".encode()).hexdigest() for text in texts]
        marks = ",".join("?" * len(keys))
        with self.lock:
            rows = self.db.execute(
                f"select key, vector from embeddings where key in ({marks})", keys
            )
            found = {key: np.frombuffer(blob, dtype=np.float64).tolist() for key, blob in rows}
        missing = [(key, text) for key, text in zip(keys, texts) if key not in found]
        log_call(
            "embedding_cache",
            purpose="embedding",
            call_count=0,
            text_count=len(texts),
            cache_hits=len(texts) - len(missing),
            cache_misses=len(missing),
            lookup_text_metrics=embedding_metadata(texts)["text_metrics"],
        )
        if missing:
            vectors = self.backend.embed([text for _, text in missing])
            for (key, _), vector in zip(missing, vectors):
                found[key] = vector
            with self.lock:
                rows = [
                    (k, np.asarray(v, dtype=np.float64).tobytes())
                    for (k, _), v in zip(missing, vectors)
                ]
                self.db.executemany("insert or replace into embeddings values (?, ?)", rows)
                self.db.commit()
        return [found[key] for key in keys]

    def close(self):
        """Close only our database, after the caller has joined judgement threads."""
        with self.lock:
            self.db.close()


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
        audit_path: Path | None = None,
    ):
        self.audit_path = audit_path
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
        self.lock = threading.Lock()  # judgements run in threads; the counters must not race

    def _waiting_out_rate_limits(self, request):
        """A per-minute limit (HTTP 429) is waited out instead of pausing the run: the SDK's
        own retries back off for seconds, but a 20-agent day can stay over a token-per-minute
        limit for longer. An exhausted quota is also a 429 and is raised at once."""
        from openai import RateLimitError

        for attempt in range(RATE_LIMIT_WAITS):
            try:
                annotate(transport_retry=attempt > 0, rate_limit_attempt=attempt)
                log_call("transport_attempt", call_count=1)
                response = request()
                log_call(
                    "transport_response",
                    transport_retry=attempt > 0,
                    call_count=0,
                    rate_limit_attempt=attempt,
                )
                return response
            except RateLimitError as exc:
                if getattr(exc, "code", None) == "insufficient_quota":
                    raise
                if attempt == RATE_LIMIT_WAITS - 1:
                    raise
                time.sleep(_retry_after(exc.response.headers) or RATE_LIMIT_SECONDS)

    def _spent(self) -> int:
        with self.lock:
            return sum(row["total_tokens"] for row in self.usage.values())

    @traced(None)
    def complete(
        self,
        *,
        system: str,
        prompt: str,
        model: str,
        temperature: float,
        json_mode: bool,
        schema: type[BaseModel] | None = None,
    ) -> str:
        from openai import APIError

        if self._spent() >= self.max_total_tokens:
            raise LLMError("Run token budget reached; no further API calls")
        if len(system) + len(prompt) > self.max_input_chars:
            raise LLMError(
                "Input exceeds max_input_chars; reduce context or memory before retrying"
            )
        options = {}
        if schema is not None:  # decoding constrained to the schema; the reply is still text
            spec = {"name": schema.__name__, "strict": True, "schema": strict_schema(schema)}
            options["response_format"] = {"type": "json_schema", "json_schema": spec}
        elif json_mode:
            options["response_format"] = {"type": "json_object"}
        if self.reasoning_effort is not None:
            options["reasoning_effort"] = self.reasoning_effort
        try:
            response = self._waiting_out_rate_limits(
                lambda: self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=temperature,
                    max_completion_tokens=self.output_limits[json_mode],
                    **options,
                )
            )
        except APIError as exc:
            # Provider error bodies can echo credentials; report only type and status.
            status = getattr(exc, "status_code", None)
            detail = f", HTTP {status}" if status is not None else ""
            raise LLMError(f"LLM request failed: {type(exc).__name__}{detail}") from None
        counters = self.usage["decide" if json_mode else "speak"]
        with self.lock:
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
        usage = response.usage
        log_call(
            "completion",
            call_count=1,
            model=response.model,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
            cached_tokens=(
                getattr(usage.prompt_tokens_details, "cached_tokens", None) if usage else None
            ),
            schema_chars=len(json.dumps(options.get("response_format", {}))),
            **completion_metadata(system, prompt),
            finish_reason=response.choices[0].finish_reason if response.choices else None,
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

    @traced(None)
    def embed(self, texts: list[str]) -> list[list[float]]:
        from openai import APIError

        if self.model_embed is None:
            raise LLMError("Set model_embed before embedding with the openai backend")
        if self._spent() >= self.max_total_tokens:
            raise LLMError("Run token budget reached; no further API calls")
        if not texts:
            return []
        try:
            response = self._waiting_out_rate_limits(
                lambda: self.client.embeddings.create(model=self.model_embed, input=texts)
            )
        except APIError as exc:
            status = getattr(exc, "status_code", None)
            detail = f", HTTP {status}" if status is not None else ""
            raise LLMError(f"Embedding request failed: {type(exc).__name__}{detail}") from None
        if response.usage is None:
            raise LLMError("LLM returned no usage; cannot enforce the run token budget")
        with self.lock:
            counters = self.usage["embed"]
            counters["calls"] += 1
            counters["prompt_tokens"] += response.usage.prompt_tokens
            counters["total_tokens"] += response.usage.total_tokens
        log_call(
            "embedding",
            call_count=1,
            **embedding_metadata(texts),
            purpose="embedding",
            model=self.model_embed,
            input_tokens=response.usage.prompt_tokens,
            total_tokens=response.usage.total_tokens,
        )
        if len(response.data) != len(texts):
            raise LLMError("Embedding response count does not match the input")
        return [row.embedding for row in sorted(response.data, key=lambda row: row.index)]
