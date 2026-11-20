import json

import pytest

httpx = pytest.importorskip("httpx")
openai = pytest.importorskip("openai")

from conflict_sim.llm import (  # noqa: E402
    LLMError,
    OpenAIBackend,
    create_openai_client,
    strict_schema,
)


def test_client_reads_dotenv_from_explicit_path_after_chdir(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=test-dotenv-key\n")
    output = tmp_path / "hydra-output"
    output.mkdir()
    monkeypatch.chdir(output)
    with create_openai_client(env_file) as client:
        assert client.api_key == "test-dotenv-key"


def test_existing_environment_takes_precedence_over_dotenv(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-shell-key")
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=test-dotenv-key\n")
    with create_openai_client(env_file) as client:
        assert client.api_key == "test-shell-key"


@pytest.mark.parametrize("contents", [None, "OPENAI_API_KEY=\n"])
def test_missing_key_explains_where_to_set_it(tmp_path, monkeypatch, contents):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    if contents is not None:
        env_file.write_text(contents)
    with pytest.raises(LLMError, match="OPENAI_API_KEY.*.env"):
        create_openai_client(env_file)


def client_for(handler):
    return openai.OpenAI(
        api_key="test-key",
        base_url="https://example.invalid/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def completion(content, finish_reason="stop"):
    return {
        "id": "test-completion",
        "object": "chat.completion",
        "created": 0,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": content, "refusal": None},
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def test_output_caps_usage_and_budget_apply_across_both_roles():
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=completion("done"))

    with client_for(respond) as client:
        backend = OpenAIBackend(
            client, max_tokens_decide=80, max_tokens_speak=40, max_total_tokens=25
        )
        for mode in (True, False):
            backend.complete(
                system="Editor", prompt="Reply", model="small", temperature=0.8, json_mode=mode
            )
        with pytest.raises(LLMError, match="token budget"):
            backend.complete(
                system="Editor", prompt="Reply", model="small", temperature=0.8, json_mode=True
            )
    assert [r["max_completion_tokens"] for r in requests] == [80, 40]
    assert backend.usage["decide"]["total_tokens"] == 15
    assert backend.usage["speak"]["total_tokens"] == 15
    assert backend.usage["speak"]["calls"] == 1


def test_oversized_full_memory_is_rejected_before_a_paid_call():
    requests = []
    with client_for(lambda r: requests.append(r)) as client:
        backend = OpenAIBackend(client, max_input_chars=20)
        with pytest.raises(LLMError, match="max_input_chars"):
            backend.complete(
                system="Editor", prompt="x" * 30, model="small", temperature=0.8, json_mode=True
            )
    assert requests == []


def test_truncated_responses_still_count_billed_tokens():
    with client_for(lambda r: httpx.Response(200, json=completion("cut off", "length"))) as client:
        backend = OpenAIBackend(client)
        with pytest.raises(LLMError):
            backend.complete(
                system="Editor", prompt="Reply", model="small", temperature=0.8, json_mode=False
            )
        assert backend.usage["speak"]["completion_tokens"] == 5


def test_missing_usage_stops_instead_of_silently_disabling_the_budget():
    response = completion("done")
    response["usage"] = None
    with client_for(lambda r: httpx.Response(200, json=response)) as client:
        backend = OpenAIBackend(client)
        with pytest.raises(LLMError, match="no usage"):
            backend.complete(
                system="Editor", prompt="Reply", model="small", temperature=0.8, json_mode=False
            )
        assert backend.usage["speak"]["missing_usage"] == 1


@pytest.mark.parametrize("effort", [None, "none"])
def test_real_sdk_serializes_json_mode_and_model_parameters(effort, caplog):
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=completion('{"urge": 0.5, "reply_to": null}'))

    with client_for(respond) as client, caplog.at_level("INFO", logger="conflict_sim.llm"):
        text = OpenAIBackend(client, reasoning_effort=effort).complete(
            system="Return JSON",
            prompt="Evaluate",
            model="small",
            temperature=0.8,
            json_mode=True,
        )
    assert json.loads(text)["urge"] == 0.5
    assert requests[0]["response_format"] == {"type": "json_object"}
    assert requests[0]["model"] == "small"
    assert requests[0]["temperature"] == 0.8
    if effort is None:
        assert "reasoning_effort" not in requests[0]
    else:
        assert requests[0]["reasoning_effort"] == effort
    record = next(record for record in caplog.records if record.name == "conflict_sim.llm")
    usage = json.loads(record.getMessage().removeprefix("LLM usage "))
    assert usage["kind"] == "decide"
    assert usage["usage"]["prompt_tokens"] == 10
    assert usage["usage"]["completion_tokens"] == 5
    assert "Evaluate" not in record.getMessage()


def test_a_schema_is_sent_as_a_strict_json_schema_response_format():
    from conflict_sim.models import Action

    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=completion('{"kind": "rest"}'))

    with client_for(respond) as client:
        OpenAIBackend(client).complete(
            system="Act", prompt="{}", model="m", temperature=0.8, json_mode=True, schema=Action
        )
    assert requests[0]["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "Action", "strict": True, "schema": strict_schema(Action)},
    }


def test_strict_schema_requires_every_field_and_drops_defaults_and_titles():
    from conflict_sim.models import Action, Insights

    def keys(node):
        if isinstance(node, dict):
            return set(node) | {k for v in node.values() for k in keys(v)}
        return {k for v in node for k in keys(v)} if isinstance(node, list) else set()

    action, insights = strict_schema(Action), strict_schema(Insights)
    assert action["additionalProperties"] is False
    assert action["required"] == list(action["properties"])  # the optional args too
    assert action["properties"]["target"] == {
        "anyOf": [{"type": "string", "pattern": "\\S"}, {"type": "null"}]
    }
    assert insights["required"] == ["insights"]
    assert "evidence" in insights["$defs"]["Insight"]["required"]  # `= []` on the model
    assert not (keys(action) | keys(insights)) & {"default", "title"}


@pytest.mark.parametrize("content,reason", [("partial", "length"), (None, "stop"), ("", "stop")])
def test_truncation_and_missing_content_are_not_used_as_generated_posts(content, reason):
    with client_for(
        lambda request: httpx.Response(200, json=completion(content, reason))
    ) as client:
        with pytest.raises(LLMError):
            OpenAIBackend(client).complete(
                system="Editor",
                prompt="Reply",
                model="large",
                temperature=0.8,
                json_mode=False,
            )


def rate_limited(code="rate_limit_exceeded", headers=None):
    return httpx.Response(
        429,
        headers=headers or {},
        json={"error": {"message": "Rate limited", "type": "rate_limit_error", "code": code}},
    )


def test_a_per_minute_rate_limit_is_waited_out_at_the_named_reset(monkeypatch):
    waits, replies = [], iter([rate_limited(headers={"x-ratelimit-reset-tokens": "42.4s"})] * 2)
    monkeypatch.setattr("conflict_sim.llm.time.sleep", waits.append)
    respond = lambda request: next(replies, httpx.Response(200, json=completion("done")))  # noqa: E731
    with client_for(respond) as client:
        reply = OpenAIBackend(client).complete(
            system="Editor", prompt="Reply", model="large", temperature=0.8, json_mode=False
        )
    assert reply == "done" and len(waits) == 2 and all(43.4 <= w <= 47.4 for w in waits)


def test_an_exhausted_quota_is_not_waited_for(monkeypatch):
    waits = []
    monkeypatch.setattr("conflict_sim.llm.time.sleep", waits.append)
    with client_for(lambda request: rate_limited("insufficient_quota")) as client:
        with pytest.raises(LLMError, match="429"):
            OpenAIBackend(client).complete(
                system="Editor", prompt="Reply", model="large", temperature=0.8, json_mode=False
            )
    assert waits == []


def test_api_failure_is_reported_as_failure(monkeypatch):
    waits = []
    monkeypatch.setattr("conflict_sim.llm.time.sleep", waits.append)  # waited out, then raised
    with client_for(
        lambda request: httpx.Response(
            429,
            json={
                "error": {
                    "message": "Rate limited",
                    "type": "rate_limit_error",
                    "code": "rate_limit_exceeded",
                }
            },
        )
    ) as client:
        with pytest.raises(LLMError, match="429"):
            OpenAIBackend(client).complete(
                system="Editor",
                prompt="Reply",
                model="large",
                temperature=0.8,
                json_mode=False,
            )
    assert len(waits) == 11


def test_api_error_does_not_echo_credentials_from_response_body():
    secret = "test-secret-echoed-by-provider"
    with client_for(
        lambda request: httpx.Response(
            401,
            json={
                "error": {
                    "message": f"Incorrect API key provided: {secret}",
                    "type": "invalid_request_error",
                    "code": "invalid_api_key",
                }
            },
        )
    ) as client:
        with pytest.raises(LLMError) as error:
            OpenAIBackend(client).complete(
                system="Editor",
                prompt="Reply",
                model="large",
                temperature=0.8,
                json_mode=False,
            )
    assert "401" in str(error.value)
    assert secret not in str(error.value)
    assert error.value.__suppress_context__


def embedding_response(count):
    return {
        "object": "list",
        "model": "embed-model",
        "data": [
            {"object": "embedding", "index": i, "embedding": [0.1 * i, 0.2, 0.3]}
            for i in range(count)
        ],
        "usage": {"prompt_tokens": 7, "total_tokens": 7},
    }


def test_embed_calls_the_embeddings_endpoint_and_counts_usage():
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=embedding_response(2))

    with client_for(respond) as client:
        backend = OpenAIBackend(client, model_embed="embed-model", max_total_tokens=7)
        vectors = backend.embed(["a", "b"])
        with pytest.raises(LLMError, match="token budget"):
            backend.embed(["c"])
    assert vectors == [[0.0, 0.2, 0.3], [0.1, 0.2, 0.3]]
    assert requests[0]["model"] == "embed-model"
    assert requests[0]["input"] == ["a", "b"]
    assert backend.usage["embed"] == {"calls": 1, "prompt_tokens": 7, "total_tokens": 7}


def test_embed_without_a_model_fails_before_any_call():
    requests = []
    with client_for(lambda r: requests.append(r)) as client:
        with pytest.raises(LLMError, match="model_embed"):
            OpenAIBackend(client).embed(["a"])
    assert requests == []


# --- embedding cache (B-8) ---


class CountingEmbeds:
    model_embed = "text-embedding-3-small"

    def __init__(self):
        self.calls = []
        self.usage = {"embed": {"calls": 0}}

    def complete(self, **request):
        return "ok"

    def embed(self, texts):
        self.calls.append(list(texts))
        return [[float(len(t)), 1.0] for t in texts]


def test_embed_cache_answers_repeats_from_disk_and_only_embeds_new_texts(tmp_path):
    from conflict_sim.llm import EmbedCache

    backend = CountingEmbeds()
    cached = EmbedCache(backend, tmp_path / "embed-cache.sqlite")
    first = cached.embed(["deadline moved", "lunch"])
    assert first == [[14.0, 1.0], [5.0, 1.0]] and backend.calls == [["deadline moved", "lunch"]]
    second = cached.embed(["lunch", "deadline moved", "new text"])
    assert second == [[5.0, 1.0], [14.0, 1.0], [8.0, 1.0]]
    assert backend.calls[-1] == ["new text"]  # only the miss reached the backend
    assert cached.complete(system="", prompt="", model="", temperature=0, json_mode=False) == "ok"
    assert cached.usage is backend.usage

    reopened = EmbedCache(CountingEmbeds(), tmp_path / "embed-cache.sqlite")
    assert reopened.embed(["lunch"]) == [[5.0, 1.0]] and reopened.backend.calls == []


def test_embed_cache_keys_on_the_embedding_model(tmp_path):
    from conflict_sim.llm import EmbedCache

    small = EmbedCache(CountingEmbeds(), tmp_path / "cache.sqlite")
    small.embed(["lunch"])
    other = CountingEmbeds()
    other.model_embed = "text-embedding-3-large"
    large = EmbedCache(other, tmp_path / "cache.sqlite")
    large.embed(["lunch"])
    assert other.calls == [["lunch"]]


def test_openai_usage_counters_survive_concurrent_calls():
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace

    from conflict_sim.llm import OpenAIBackend

    def create(**_):
        message = SimpleNamespace(content="ok", refusal=None)
        usage = SimpleNamespace(
            prompt_tokens=1, completion_tokens=1, total_tokens=2,
            prompt_tokens_details=None, completion_tokens_details=None, model_dump=dict,
        )  # fmt: skip
        choice = SimpleNamespace(message=message, finish_reason="stop")
        return SimpleNamespace(choices=[choice], usage=usage, model="m")

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    backend = OpenAIBackend(client, max_total_tokens=10_000_000)
    with ThreadPoolExecutor(8) as pool:
        list(
            pool.map(
                lambda _: backend.complete(
                    system="", prompt="", model="m", temperature=0, json_mode=False
                ),
                range(400),
            )
        )
    assert backend.usage["speak"]["calls"] == 400 and backend.usage["speak"]["total_tokens"] == 800


def test_openai_backend_without_a_cap_never_stops_on_budget():
    backend = OpenAIBackend(object(), max_total_tokens=None)
    backend.usage["decide"]["total_tokens"] = 10**12
    backend._check_budget()  # no LLMError


def test_a_prompt_cache_key_routes_every_call_of_a_run_to_one_cache():
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=completion("done"))

    with client_for(respond) as client:
        keyed = OpenAIBackend(client, prompt_cache_key="conflict-sim:r10")
        for model in ("small", "small", "large"):
            keyed.complete(system="S", prompt="P", model=model, temperature=0, json_mode=False)
        OpenAIBackend(client).complete(
            system="S", prompt="P", model="small", temperature=0, json_mode=False
        )
    assert [r.get("prompt_cache_key") for r in requests] == [
        "conflict-sim:r10:small", "conflict-sim:r10:small", "conflict-sim:r10:large", None
    ]  # fmt: skip


def test_the_cache_key_names_the_scenario():
    from conflict_sim.company_runtime import build_company_config
    from conflict_sim.llm import cache_key

    assert cache_key(build_company_config("r10_human")) == "conflict-sim:r10_human"
    assert cache_key(object()) == "conflict-sim:run"


def test_flex_processing_is_asked_for_only_when_on():
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=completion("done"))

    with client_for(respond) as client:
        for flex in (True, False):
            OpenAIBackend(client, flex=flex).complete(
                system="S", prompt="P", model="m", temperature=0, json_mode=False
            )
    assert [r.get("service_tier") for r in requests] == ["flex", None]
    assert all("timeout" not in r for r in requests)  # a client option, not a body field


def test_a_flex_refusal_falls_back_to_standard_processing(monkeypatch):
    """Flex may answer 429 Resource Unavailable (not billed): after FLEX_ATTEMPTS refusals the
    same call goes again at once without the tier, and a run never waits on Flex for long."""
    from conflict_sim.llm import FLEX_ATTEMPTS

    waits, tiers = [], []
    monkeypatch.setattr("conflict_sim.llm.time.sleep", waits.append)

    def respond(request):
        tier = json.loads(request.content).get("service_tier")
        tiers.append(tier)
        if tier == "flex":
            return rate_limited("resource_unavailable", {"retry-after-ms": "10"})
        return httpx.Response(200, json=completion("done"))

    with client_for(respond) as client:
        reply = OpenAIBackend(client, flex=True).complete(
            system="S", prompt="P", model="m", temperature=0, json_mode=False
        )
    assert reply == "done"
    assert tiers == ["flex"] * FLEX_ATTEMPTS + [None]
    assert len(waits) == FLEX_ATTEMPTS - 1  # waited between Flex tries, not before standard


def test_runs_use_flex_unless_turned_off():
    from conflict_sim.company_runtime import build_company_config
    from conflict_sim.models import Config

    cfg = build_company_config("r10_human")
    assert cfg.flex is True
    for off in (0, "false", False):  # Hydra's flex=0 and flex=false, or a JSON false
        assert Config.model_validate(cfg.model_dump() | {"flex": off}).flex is False


def _flex_client_for(handler, max_retries=3):
    """A client with the SDK's own retries on, as create_openai_client makes it (8 there)."""
    return openai.OpenAI(
        api_key="test-key",
        base_url="https://example.invalid/v1",
        max_retries=max_retries,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def _flex_call(backend):
    return backend.complete(system="S", prompt="P", model="m", temperature=0, json_mode=False)


def test_flex_calls_go_without_the_sdks_retries_and_standard_calls_keep_them(monkeypatch):
    """Each Flex refusal reaches our loop at once (one request per attempt, not the SDK's
    retries stacked under ours); the standard fallback keeps the SDK's retries."""
    from conflict_sim.llm import FLEX_ATTEMPTS

    ours = []
    monkeypatch.setattr("conflict_sim.llm.time.sleep", ours.append)
    tiers, standard = [], iter([rate_limited("rate_limit_exceeded", {"retry-after-ms": "1"})])

    def respond(request):
        tier = json.loads(request.content).get("service_tier")
        tiers.append(tier)
        if tier == "flex":
            return rate_limited("resource_unavailable", {"retry-after-ms": "1"})
        return next(standard, httpx.Response(200, json=completion("done")))

    with _flex_client_for(respond, max_retries=3) as client:
        assert _flex_call(OpenAIBackend(client, flex=True)) == "done"
    # Flex: exactly FLEX_ATTEMPTS requests; standard: a 429 the SDK retried by itself.
    assert tiers == ["flex"] * FLEX_ATTEMPTS + [None, None]
    # `time.sleep` is the module's, shared with the SDK: our backoff between the Flex attempts
    # (a second or more), then the SDK's own short wait before retrying the standard call.
    assert len(ours) == FLEX_ATTEMPTS and ours[0] >= 1 and ours[-1] < 0.5


def test_a_per_minute_limit_on_flex_is_waited_out_on_flex_never_sent_to_standard(monkeypatch):
    """Over tokens per minute is the account's limit, not Flex's capacity: standard processing
    would hit the same limit at twice the price, so the call waits and stays on Flex."""
    waits, tiers = [], []
    monkeypatch.setattr("conflict_sim.llm.time.sleep", waits.append)
    replies = iter([rate_limited("rate_limit_exceeded",
                                 {"x-ratelimit-remaining-tokens": "0",
                                  "x-ratelimit-reset-tokens": "2s"})] * 4)  # fmt: skip

    def respond(request):
        tiers.append(json.loads(request.content).get("service_tier"))
        return next(replies, httpx.Response(200, json=completion("done")))

    with client_for(respond) as client:
        assert _flex_call(OpenAIBackend(client, flex=True, flex_fallback=True)) == "done"
    assert tiers == ["flex"] * 5 and len(waits) == 4


def test_without_fallback_flex_out_of_capacity_is_waited_for_with_backoff(monkeypatch):
    """flex_fallback off: never standard rates; exponential backoff (with jitter, capped at
    FLEX_BACKOFF_CAP) until Flex answers."""
    from conflict_sim.llm import FLEX_BACKOFF_CAP

    waits, tiers = [], []
    monkeypatch.setattr("conflict_sim.llm.time.sleep", waits.append)
    busy = {"error": {"message": "Resource Unavailable", "type": "rate_limit_error"}}
    replies = iter([httpx.Response(429, json=busy)] * 8)

    def respond(request):
        tiers.append(json.loads(request.content).get("service_tier"))
        return next(replies, httpx.Response(200, json=completion("done")))

    with client_for(respond) as client:
        assert _flex_call(OpenAIBackend(client, flex=True, flex_fallback=False)) == "done"
    assert tiers == ["flex"] * 9  # eight refusals, then Flex answered; never standard
    assert len(waits) == 8 and waits[0] < 2 and waits[3] >= 8
    assert max(waits) <= FLEX_BACKOFF_CAP + 1


def test_which_429_is_flex_capacity():
    from conflict_sim.llm import _flex_capacity

    def error(code=None, message="Rate limited", headers=None):
        response = httpx.Response(429, headers=headers or {},
                                  request=httpx.Request("POST", "https://x.invalid"))  # fmt: skip
        body = {"error": {"message": message, "type": "rate_limit_error", "code": code}}
        return openai.RateLimitError(message, response=response, body=body["error"])

    assert _flex_capacity(error("resource_unavailable"))
    assert _flex_capacity(error(message="Resource Unavailable, try again later"))
    assert not _flex_capacity(error("rate_limit_exceeded", "Rate limit reached for tokens per min"))
    assert not _flex_capacity(error(message="Resource Unavailable",
                                    headers={"x-ratelimit-remaining-tokens": "0"}))  # fmt: skip
