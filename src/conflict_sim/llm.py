"""One completion interface for a local demo and the optional OpenAI SDK."""

import hashlib
import json
import logging
import math
import os
import sqlite3
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import numpy as np
from pydantic import BaseModel

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
        if "view" in payload:
            return json.dumps(self._act(payload["view"], payload.get("manager")))
        if "tasks" in payload:
            return json.dumps({"plan": self._plan(payload)})
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
        desk, food = _desk_and_food(view.get("places", {}), view["place"])
        if view["phase"] == "lunch":
            if view["present"] and view.get("places", {}).get(view["place"]) in EAT_KINDS:
                return action | {
                    "kind": "talk",
                    "targets": list(view["present"]),
                    "text": "How is your morning going?",
                }
            return action | {"kind": "eat", "place": food}
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
            task = min(open_tasks, key=lambda t: t["due"])["id"]
            return action | {"kind": "work", "task": task, "place": desk}
        return action | {"kind": "rest"}

    def _plan(self, payload: dict) -> list[dict]:
        """Move to a desk, work the two most urgent tasks around lunch, chat over lunch, and leave
        the closing tick unplanned — what to do at the end of the day is a judgement."""
        first, last = payload["tick"], payload["last_tick"]
        desk, food = _desk_and_food(payload["places"], payload["place"])
        lunch = first + (last + 1 - first) // 2  # the loop's lunch phase starts mid-day
        tasks = sorted((t for t in payload["tasks"] if t["progress"] < 1), key=lambda t: t["due"])
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


WORK_KINDS = ("desk", "office")
EAT_KINDS = ("pantry", "cafeteria")


def _desk_and_food(places: dict, here: str) -> tuple[str, str]:
    desk = next((p for p, k in places.items() if k in WORK_KINDS), here)
    food = next((p for p, k in places.items() if k in EAT_KINDS), desk)
    return desk, food


def _block(kind: str, until: int, text: str, **arguments: str) -> dict:
    return {"kind": kind, "until": until, "text": text} | arguments


class EmbedCache:
    """`embed` answered from an on-disk table when the model and text were seen before.

    Only embeddings are cached (plan §1-10): a `temperature 0.8` completion cached across runs
    would turn "3 runs per condition" into one run.
    """

    def __init__(self, backend: LanguageModel, path: Path):
        self.backend = backend
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

    def embed(self, texts: list[str]) -> list[list[float]]:
        keys = [hashlib.sha256(f"{self.model}\n{text}".encode()).hexdigest() for text in texts]
        marks = ",".join("?" * len(keys))
        with self.lock:
            rows = self.db.execute(
                f"select key, vector from embeddings where key in ({marks})", keys
            )
            found = {key: np.frombuffer(blob, dtype=np.float64).tolist() for key, blob in rows}
        missing = [(key, text) for key, text in zip(keys, texts) if key not in found]
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
        self.lock = threading.Lock()  # judgements run in threads; the counters must not race

    def _spent(self) -> int:
        with self.lock:
            return sum(row["total_tokens"] for row in self.usage.values())

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
        if response.usage is None:
            raise LLMError("LLM returned no usage; cannot enforce the run token budget")
        with self.lock:
            counters = self.usage["embed"]
            counters["calls"] += 1
            counters["prompt_tokens"] += response.usage.prompt_tokens
            counters["total_tokens"] += response.usage.total_tokens
        if len(response.data) != len(texts):
            raise LLMError("Embedding response count does not match the input")
        return [row.embedding for row in sorted(response.data, key=lambda row: row.index)]
