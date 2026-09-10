"""One completion interface for a local demo and the optional OpenAI SDK."""

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

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


class DemoBackend:
    """Scripted smoke-test responses. These are not research observations."""

    def complete(
        self, *, system: str, prompt: str, model: str, temperature: float, json_mode: bool
    ) -> str:
        payload = json.loads(prompt)
        if json_mode:
            return json.dumps(
                {
                    "urge": 0.6,
                    "reply_to": payload["utterances"][-1]["id"],
                    "reflection": "I still want to compare the cited passages. "
                    "I would like the discussion to resolve which source supports the claim.",
                }
            )
        return "Could we compare the cited passages before changing the article?"


class OpenAIBackend:
    def __init__(self, client: "OpenAI", *, reasoning_effort: str | None = None):
        self.client = client
        self.reasoning_effort = reasoning_effort

    def complete(
        self, *, system: str, prompt: str, model: str, temperature: float, json_mode: bool
    ) -> str:
        from openai import APIError

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
                **options,
            )
        except APIError as exc:
            # Provider error bodies can echo credentials; report only type and status.
            status = getattr(exc, "status_code", None)
            detail = f", HTTP {status}" if status is not None else ""
            raise LLMError(f"LLM request failed: {type(exc).__name__}{detail}") from None
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
        if not response.choices:
            raise LLMError("LLM returned no choices")
        choice = response.choices[0]
        if choice.finish_reason != "stop" or choice.message.refusal:
            raise LLMError(f"LLM did not complete a reply (finish_reason={choice.finish_reason})")
        if not choice.message.content or not choice.message.content.strip():
            raise LLMError("LLM returned empty content")
        return choice.message.content
