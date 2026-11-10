import asyncio
import builtins
import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pydantic import BaseModel

from conflict_sim.claude_backend import SYSTEM_PROMPT_FILE_CHARS, ClaudeAgentBackend
from conflict_sim.llm import LLMError, strict_schema

USAGE = {"input_tokens": 3, "output_tokens": 2, "cache_read_input_tokens": 0,
         "cache_creation_input_tokens": 0}  # fmt: skip


@dataclass
class ResultMessage:  # the SDK's message, matched by class name
    result: str | None = ""
    subtype: str = "success"
    is_error: bool = False
    structured_output: object = None
    stop_reason: str | None = "end_turn"
    usage: dict | None = field(default_factory=lambda: dict(USAGE))
    model_usage: dict | None = None


def result(text="", **fields):
    return ResultMessage(result=text, **fields)


def recording_backend(messages, **options):
    """A backend whose SDK call records what it was given and replays `messages`."""
    seen = []

    async def run_query(*, prompt, options):
        cwd = Path(options["cwd"])
        seen.append({"prompt": prompt, "options": options,
                     "cwd_empty": cwd.is_dir() and not any(cwd.iterdir())})
        for message in messages:
            yield message

    return seen, ClaudeAgentBackend(run_query=run_query, **options)


class Act(BaseModel):
    action: str


def ask(backend, **overrides):
    request = dict(system="S", prompt="P", model="m", temperature=0, json_mode=False) | overrides
    return backend.complete(**request)


def test_text_call_returns_the_result_and_is_isolated():
    seen, backend = recording_backend([result("안녕")])
    assert ask(backend, model="claude-haiku-5-5", temperature=0.8) == "안녕"
    o = seen[0]["options"]
    assert seen[0]["prompt"] == "P" and o["system_prompt"] == "S"
    assert o["model"] == "claude-haiku-5-5"
    assert o["tools"] == [] and o["setting_sources"] == [] and o["mcp_servers"] == {}
    assert o["permission_mode"] == "dontAsk"
    assert o["extra_args"] == {"restricted": None, "disable-slash-commands": None,
                               "strict-mcp-config": None, "no-session-persistence": None}
    assert seen[0]["cwd_empty"]
    assert "temperature" not in o and "max_turns" not in o


def test_a_schema_becomes_output_format_and_returns_json_text():
    seen, backend = recording_backend([result("", structured_output={"action": "말하기"})])
    text = ask(backend, json_mode=True, schema=Act)
    assert seen[0]["options"]["output_format"] == {
        "type": "json_schema", "schema": strict_schema(Act)}
    assert text == '{"action": "말하기"}'


def test_json_mode_without_a_schema_parses_the_text_reply():
    seen, backend = recording_backend([result('```json\n{"reply": "ok"}\n```')])
    assert json.loads(ask(backend, json_mode=True)) == {"reply": "ok"}
    assert "output_format" not in seen[0]["options"]


@pytest.mark.parametrize("text", ["네", "[1, 2]", "```json\n```"])
def test_json_mode_text_that_is_not_an_object_is_a_failure(text):
    _, backend = recording_backend([result(text)])
    with pytest.raises(LLMError, match="JSON object"):
        ask(backend, json_mode=True)


@pytest.mark.parametrize("effort, expected", [
    ("none", {"thinking": {"type": "disabled"}, "effort": "low"}),
    ("low", {"effort": "low"}),
    (None, {}),
])
def test_reasoning_effort_maps_to_thinking_or_effort(effort, expected):
    seen, backend = recording_backend([result("a")], reasoning_effort=effort)
    ask(backend)
    o = seen[0]["options"]
    assert {k: o[k] for k in ("thinking", "effort") if k in o} == expected


def test_usage_counts_by_role_and_the_cap_stops_the_next_call():
    usage = {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100,
             "cache_creation_input_tokens": 20}
    seen, backend = recording_backend([result("a", usage=usage)], max_total_tokens=135)
    ask(backend)
    assert backend.usage["speak"] == {
        "calls": 1, "prompt_tokens": 130, "completion_tokens": 5, "total_tokens": 135,
        "cached_tokens": 100, "reasoning_tokens": 0, "missing_usage": 0}
    with pytest.raises(LLMError, match="token budget"):
        ask(backend, json_mode=True)
    assert len(seen) == 1


def test_model_usage_is_preferred_because_it_counts_every_request():
    model_usage = {"claude-haiku-5-5": {"inputTokens": 1000, "outputTokens": 70,
                                         "cacheReadInputTokens": 50,
                                         "cacheCreationInputTokens": 600},
                   "other": {"inputTokens": 1, "outputTokens": 1, "cacheReadInputTokens": 0,
                             "cacheCreationInputTokens": 0}}
    _, backend = recording_backend([result("a", model_usage=model_usage)])
    ask(backend)
    row = backend.usage["speak"]
    assert (row["prompt_tokens"], row["completion_tokens"], row["cached_tokens"]) == (1651, 71, 50)
    assert row["total_tokens"] == 1722


@pytest.mark.parametrize("message, schema, pattern", [
    (result("x", subtype="error_max_structured_output_retries", is_error=True), None,
     "error_max_structured_output_retries"),
    (result("x", is_error=True), None, "error"),
    (result("", structured_output=None), Act, "structured output"),
    (result("x", stop_reason="refusal"), None, "refusal"),
    (result("x", usage=None), None, "no usage"),
    (result("  "), None, "empty"),
])
def test_incomplete_results_are_failures_not_replies(message, schema, pattern):
    _, backend = recording_backend([message])
    with pytest.raises(LLMError, match=pattern):
        ask(backend, json_mode=schema is not None, schema=schema)


def test_a_stream_without_a_result_is_a_failure():
    _, backend = recording_backend([])
    with pytest.raises(LLMError, match="no result"):
        ask(backend)


def test_an_error_after_a_failed_result_reports_the_result():
    async def run_query(*, prompt, options):
        yield result("Invalid API key", is_error=True)
        raise RuntimeError("Command failed with exit code 1")

    with pytest.raises(LLMError, match="Invalid API key"):
        ask(ClaudeAgentBackend(run_query=run_query))


def test_the_stream_is_read_to_its_end_after_the_result():
    read = []

    async def run_query(*, prompt, options):
        yield result("a")
        read.append("after")

    assert ask(ClaudeAgentBackend(run_query=run_query)) == "a" and read == ["after"]


def test_oversized_input_is_rejected_before_any_call():
    seen, backend = recording_backend([result("a")], max_input_chars=10)
    with pytest.raises(LLMError, match="max_input_chars"):
        ask(backend, prompt="x" * 20)
    assert seen == []


def test_a_long_system_prompt_goes_by_file_and_the_file_is_removed():
    system = "가" * (SYSTEM_PROMPT_FILE_CHARS + 1)
    during = []

    async def run_query(*, prompt, options):
        spec = options["system_prompt"]
        during.append((spec, Path(spec["path"]).read_text(encoding="utf-8")))
        yield result("a")

    ask(ClaudeAgentBackend(run_query=run_query), system=system)
    spec, text = during[0]
    assert spec["type"] == "file" and text == system
    assert not Path(spec["path"]).exists()


def test_the_working_directory_is_removed_after_the_call():
    seen, backend = recording_backend([result("a")])
    ask(backend)
    assert not Path(seen[0]["options"]["cwd"]).exists()


def test_missing_sdk_explains_the_install(monkeypatch):
    real = builtins.__import__

    def refuse(name, *args, **kwargs):
        if name.startswith("claude_agent_sdk"):
            raise ImportError(name)
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", refuse)
    with pytest.raises(LLMError, match="uv sync --extra claude"):
        ask(ClaudeAgentBackend())


# ---- Task 2: limits, failures, concurrency, credentials ----
import os  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from conflict_sim.claude_backend import TRANSIENT_RETRIES, subscription_env  # noqa: E402


@dataclass
class RateLimitEvent:
    rate_limit_info: object


@dataclass
class SystemMessage:
    subtype: str
    data: dict


def limit(status, window, resets_at=None):
    return RateLimitEvent(SimpleNamespace(status=status, rate_limit_type=window,
                                          resets_at=resets_at))  # fmt: skip


def init(api_key_source):
    return SystemMessage("init", {"apiKeySource": api_key_source})


class ProcessError(Exception):  # the SDK's, matched by class name
    def __init__(self, message, exit_code=None, stderr=None):
        super().__init__(message)
        self.exit_code, self.stderr = exit_code, stderr


class CLINotFoundError(Exception):
    pass


def test_a_rejected_limit_stops_at_once_and_names_the_window():
    seen, backend = recording_backend([limit("rejected", "five_hour", 1_800_000_000),
                                       result("x")])  # fmt: skip
    with pytest.raises(LLMError, match="five_hour") as error:
        ask(backend)
    assert "구독 한도" in str(error.value) and "에 풀립니다" in str(error.value)
    assert len(seen) == 1


def test_a_limit_warning_is_kept_once_and_the_call_succeeds():
    warning = limit("allowed_warning", "seven_day")
    _, backend = recording_backend([warning, warning, result("x")])
    assert ask(backend) == "x"
    ask(backend)
    assert len(backend.warnings) == 1 and "seven_day" in backend.warnings[0]


def test_an_allowed_limit_event_is_quiet():
    _, backend = recording_backend([limit("allowed", "five_hour"), result("x")])
    assert ask(backend) == "x" and backend.warnings == []


def test_transient_failures_retry_twice_then_fail_without_stderr():
    calls = []

    async def run_query(*, prompt, options):
        calls.append(1)
        raise ProcessError("Command failed", exit_code=1, stderr="sk-ant-secret")
        yield  # an async generator

    with pytest.raises(LLMError, match="ProcessError, exit 1") as error:
        ask(ClaudeAgentBackend(run_query=run_query))
    assert len(calls) == 1 + TRANSIENT_RETRIES and "sk-ant-secret" not in str(error.value)


def test_a_transient_failure_then_success_returns_the_reply():
    calls = []

    async def run_query(*, prompt, options):
        calls.append(1)
        if len(calls) == 1:
            raise ProcessError("Command failed", exit_code=1)
        yield result("ok")

    assert ask(ClaudeAgentBackend(run_query=run_query)) == "ok" and len(calls) == 2


def test_a_missing_cli_is_not_retried_and_explains_the_install():
    calls = []

    async def run_query(*, prompt, options):
        calls.append(1)
        raise CLINotFoundError("Claude Code not found")
        yield

    with pytest.raises(LLMError, match="uv sync --extra claude"):
        ask(ClaudeAgentBackend(run_query=run_query))
    assert len(calls) == 1


def test_a_hung_call_times_out():
    async def run_query(*, prompt, options):
        await asyncio.sleep(10)
        yield result("late")

    started = time.monotonic()
    with pytest.raises(LLMError, match="timed out"):
        ask(ClaudeAgentBackend(run_query=run_query, timeout=0.05))
    assert time.monotonic() - started < 2


def test_at_most_max_concurrent_calls_run_together():
    active, peak, lock = [0], [0], threading.Lock()

    async def run_query(*, prompt, options):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        await asyncio.sleep(0.05)
        with lock:
            active[0] -= 1
        yield result("x")

    backend = ClaudeAgentBackend(run_query=run_query, max_concurrent=2)
    threads = [threading.Thread(target=ask, args=(backend,)) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert peak[0] == 2 and backend.usage["speak"]["calls"] == 8


def test_stronger_credentials_are_blanked_and_the_oauth_token_kept():
    env = {"ANTHROPIC_API_KEY": "k", "CLAUDE_CODE_USE_BEDROCK": "1",
           "CLAUDE_CODE_OAUTH_TOKEN": "t", "PATH": "/bin"}  # fmt: skip
    assert subscription_env(env) == {"ANTHROPIC_API_KEY": "", "CLAUDE_CODE_USE_BEDROCK": ""}


def test_every_call_blanks_the_api_key_without_touching_the_process(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-real")
    seen, backend = recording_backend([result("x")])
    ask(backend)
    assert seen[0]["options"]["env"]["ANTHROPIC_API_KEY"] == ""
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-real"


def test_a_call_that_is_not_on_the_subscription_is_refused():
    _, backend = recording_backend([init("ANTHROPIC_API_KEY"), result("x")])
    with pytest.raises(LLMError, match="구독"):
        ask(backend)
    _, backend = recording_backend([init("none"), result("x")])
    assert ask(backend) == "x" and backend.auth == "subscription"
