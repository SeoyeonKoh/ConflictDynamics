"""Completions through the Claude Agent SDK: the Claude Code CLI on the user's subscription login.

Each `complete` is one `query()`: one CLI process with no tools, no settings, no MCP servers, no
skills or saved session, in an empty temporary directory. The SDK has no embeddings; an embedding
function is injected instead (`local_embed.LocalEmbedder` or an OpenAI backend's `embed`).
Findings behind the choices here: docs/superpowers/specs/2026-11-10-claude-subscription-route/
spike-results.md.
"""

import asyncio
import json
import os
import re
import shutil
import tempfile
import threading
import time
from collections.abc import AsyncIterator, Callable, Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .llm import LLMError, strict_schema
from .usage_audit import completion_metadata, log_call, traced

Embed = Callable[[list[str]], list[list[float]]]
RunQuery = Callable[..., AsyncIterator[Any]]  # run_query(prompt=str, options=dict)

SYSTEM_PROMPT_FILE_CHARS = 60_000  # longer prompts go by file: Linux caps one argv at ~128 KB
INSTALL = "Install the Claude extra: uv sync --extra claude"
# Without these the CLI loads the user's skills and slash commands and saves every call as a
# session under ~/.claude/projects (spike results 2 and 3).
CLI_FLAGS = {"restricted": None, "disable-slash-commands": None, "strict-mcp-config": None,
             "no-session-persistence": None}  # fmt: skip
# Credentials the CLI prefers to the subscription login (its authentication precedence).
SUBSCRIPTION_BLOCKERS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK",
                         "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")  # fmt: skip
TRANSIENT = ("ProcessError", "CLIConnectionError", "CLIJSONDecodeError")
TRANSIENT_RETRIES = 2
FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def subscription_env(environ: Mapping[str, str] = os.environ) -> dict[str, str]:
    """`options.env` overrides that blank every credential outranking the subscription login.
    An empty value hides the parent's key from the CLI (spike S2); the process is left alone."""
    return {name: "" for name in SUBSCRIPTION_BLOCKERS if environ.get(name)}


class _Transient(LLMError):
    """A CLI failure worth one more try."""


def _resets(info) -> str:
    at = getattr(info, "resets_at", None)
    return f"; {time.strftime('%Y-%m-%d %H:%M', time.localtime(at))}에 풀립니다" if at else ""


def _sdk_query(*, prompt: str, options: dict) -> AsyncIterator[Any]:
    try:
        from claude_agent_sdk import ClaudeAgentOptions, query
    except ImportError as exc:
        raise LLMError(INSTALL) from exc
    return query(prompt=prompt, options=ClaudeAgentOptions(**options))


def _tokens(message) -> dict[str, int] | None:
    """Tokens of every request the CLI made for this call; `model_usage` counts them all,
    `usage` only the main one (spike result 5)."""
    if message.model_usage:
        rows = message.model_usage.values()
        get = {"input": "inputTokens", "output": "outputTokens",
               "read": "cacheReadInputTokens", "write": "cacheCreationInputTokens"}  # fmt: skip
    elif message.usage:
        rows = [message.usage]
        get = {"input": "input_tokens", "output": "output_tokens",
               "read": "cache_read_input_tokens",
               "write": "cache_creation_input_tokens"}  # fmt: skip
    else:
        return None
    total = {k: sum(int(row.get(name) or 0) for row in rows) for k, name in get.items()}
    return {"prompt": total["input"] + total["read"] + total["write"],
            "completion": total["output"], "cached": total["read"]}  # fmt: skip


class ClaudeAgentBackend:
    def __init__(
        self,
        *,
        embed: Embed | None = None,
        reasoning_effort: str | None = None,
        max_total_tokens: int | None = 100_000,
        max_input_chars: int = 64_000,
        max_concurrent: int = 4,
        timeout: float = 180.0,
        audit_path: Path | None = None,
        run_query: RunQuery | None = None,
    ):
        self._embed = embed
        self.model_embed = getattr(embed, "model", None)  # EmbedCache keys on it
        self.reasoning_effort = reasoning_effort
        self.max_total_tokens = max_total_tokens
        self.max_input_chars = max_input_chars
        self.timeout = timeout
        self.audit_path = audit_path
        self.run_query = run_query or _sdk_query
        self.gate = threading.BoundedSemaphore(max_concurrent)
        self.auth: str | None = None
        self.cli_version: str | None = None
        self.warnings: list[str] = []
        self.usage = {
            kind: dict(calls=0, prompt_tokens=0, completion_tokens=0, total_tokens=0,
                       cached_tokens=0, reasoning_tokens=0, missing_usage=0)  # fmt: skip
            for kind in ("decide", "speak")
        }
        # OpenAI embeddings bring their own counters (calls and tokens); local ones only calls.
        self.usage["embed"] = getattr(embed, "usage", None) or dict(
            calls=0, prompt_tokens=0, total_tokens=0
        )
        self._counts_embeds = not hasattr(embed, "usage")
        self.lock = threading.Lock()

    def _spent(self) -> int:
        with self.lock:
            return sum(row["total_tokens"] for row in self.usage.values())

    def _check_budget(self) -> None:
        if self.max_total_tokens is not None and self._spent() >= self.max_total_tokens:
            raise LLMError("Run token budget reached; no further API calls")

    def _options(self, model: str, cwd: str, schema: type[BaseModel] | None) -> dict:
        options = {"model": model, "tools": [], "setting_sources": [], "mcp_servers": {},
                   "permission_mode": "dontAsk", "cwd": cwd, "env": subscription_env(),
                   "extra_args": dict(CLI_FLAGS)}  # fmt: skip
        if schema is not None:
            options["output_format"] = {"type": "json_schema", "schema": strict_schema(schema)}
        if self.reasoning_effort == "none":  # "disabled" alone is ignored on structured calls
            options["thinking"] = {"type": "disabled"}
            options["effort"] = "low"
        elif self.reasoning_effort is not None:
            options["effort"] = self.reasoning_effort
        return options

    def _note(self, message, stop: list[str]) -> None:
        """Limit events and the session's credentials, noted while the stream is read."""
        name = type(message).__name__
        if name == "RateLimitEvent":
            info = message.rate_limit_info
            window = getattr(info, "rate_limit_type", None) or "unknown"
            if info.status == "rejected":
                stop.append(f"Claude 구독 한도에 닿았습니다 ({window}){_resets(info)}. "
                            "그 뒤에 이어서 실행하세요.")  # fmt: skip
            elif info.status == "allowed_warning":
                warning = f"Claude 구독 한도에 가까워졌습니다 ({window})."
                with self.lock:
                    if warning not in self.warnings:
                        self.warnings.append(warning)
        elif name == "SystemMessage" and message.subtype == "init":
            source = message.data.get("apiKeySource")
            self.cli_version = message.data.get("claude_code_version") or self.cli_version
            if source == "none":
                self.auth = "subscription"
            else:
                stop.append(f"Claude가 구독 로그인이 아니라 {source}로 호출됐습니다; "
                            "구독으로만 실행합니다.")  # fmt: skip

    async def _result(self, prompt: str, options: dict):
        """The stream's result message. The stream is read to its end (stopping early breaks
        the SDK, spike result 6); a refusal noted on the way is raised after it."""
        found, stop = None, []
        try:
            async for message in self.run_query(prompt=prompt, options=options):
                if type(message).__name__ == "ResultMessage":
                    found = message
                else:
                    self._note(message, stop)
        except LLMError:
            raise
        except Exception as exc:  # after a failed result the SDK raises too (spike result 7)
            if not (found is not None and found.is_error) and not stop:
                kind = type(exc).__name__
                if kind == "CLINotFoundError":
                    raise LLMError(f"Claude Code was not found. {INSTALL}") from None
                code = getattr(exc, "exit_code", None)
                detail = f", exit {code}" if code is not None else ""
                error = _Transient if kind in TRANSIENT else LLMError
                raise error(f"Claude call failed: {kind}{detail}") from None
        if stop:
            raise LLMError(stop[0])
        return found

    async def _timed(self, prompt: str, options: dict):
        try:
            return await asyncio.wait_for(self._result(prompt, options), self.timeout)
        except TimeoutError:
            raise LLMError(f"Claude call timed out after {self.timeout:g}s") from None

    def _call(self, system: str, prompt: str, model: str, schema):
        cwd = tempfile.mkdtemp(prefix="conflict-claude-")
        try:
            options = self._options(model, cwd, schema)
            if len(system) > SYSTEM_PROMPT_FILE_CHARS:
                path = Path(tempfile.mkdtemp(prefix="conflict-claude-system-")) / "system.md"
                path.write_text(system, encoding="utf-8")
                options["system_prompt"] = {"type": "file", "path": str(path)}
            else:
                path = None
                options["system_prompt"] = system
            try:
                return asyncio.run(self._timed(prompt, options))
            finally:
                if path is not None:
                    shutil.rmtree(path.parent, ignore_errors=True)
        finally:
            shutil.rmtree(cwd, ignore_errors=True)

    @traced(None)
    def complete(
        self,
        *,
        system: str,
        prompt: str,
        model: str,
        temperature: float,  # the CLI takes no temperature; the run manifest records that
        json_mode: bool,
        schema: type[BaseModel] | None = None,
    ) -> str:
        self._check_budget()
        if len(system) + len(prompt) > self.max_input_chars:
            raise LLMError(
                "Input exceeds max_input_chars; reduce context or memory before retrying"
            )
        for attempt in range(TRANSIENT_RETRIES + 1):
            try:
                with self.gate:
                    message = self._call(system, prompt, model, schema)
                break
            except _Transient:
                if attempt == TRANSIENT_RETRIES:
                    raise
                time.sleep(1.0 + attempt)
        if message is None:
            raise LLMError("Claude returned no result")
        kind = "decide" if json_mode else "speak"
        tokens = _tokens(message)
        counters = self.usage[kind]
        with self.lock:
            counters["calls"] += 1
            if tokens is None:
                counters["missing_usage"] += 1
            else:
                counters["prompt_tokens"] += tokens["prompt"]
                counters["completion_tokens"] += tokens["completion"]
                counters["total_tokens"] += tokens["prompt"] + tokens["completion"]
                counters["cached_tokens"] += tokens["cached"]
        log_call(
            "completion",
            call_count=1,
            provider="claude",
            model=model,
            input_tokens=tokens and tokens["prompt"],
            output_tokens=tokens and tokens["completion"],
            total_tokens=tokens and tokens["prompt"] + tokens["completion"],
            cached_tokens=tokens and tokens["cached"],
            **completion_metadata(system, prompt),
            finish_reason=message.stop_reason,
        )
        if message.is_error or message.subtype != "success":
            detail = message.subtype if message.subtype != "success" else (message.result or "")
            raise LLMError(f"Claude did not complete a reply: error {detail[:200]}")
        if message.stop_reason == "refusal":
            raise LLMError("Claude did not complete a reply (stop_reason=refusal)")
        if tokens is None:
            raise LLMError("Claude returned no usage; cannot enforce the run token budget")
        if schema is not None:
            if message.structured_output is None:
                raise LLMError("Claude returned no structured output")
            return json.dumps(message.structured_output, ensure_ascii=False)
        text = message.result or ""
        if not text.strip():
            raise LLMError("Claude returned empty content")
        if json_mode:  # no schema: the reply is text that must hold one JSON object (spike S5)
            fenced = FENCE.match(text)
            try:
                answer = json.loads(fenced.group(1) if fenced else text)
            except ValueError:
                answer = None
            if not isinstance(answer, dict):
                raise LLMError("Claude's reply is not a JSON object")
            return json.dumps(answer, ensure_ascii=False)
        return text

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._embed is None:
            raise LLMError("Choose an embedding backend before embedding with the claude backend")
        if self._counts_embeds:
            with self.lock:
                self.usage["embed"]["calls"] += 1
        return self._embed(texts)

