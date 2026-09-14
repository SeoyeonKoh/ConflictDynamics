import json

import pytest

httpx = pytest.importorskip("httpx")
openai = pytest.importorskip("openai")

from conflict_sim.llm import LLMError, OpenAIBackend, create_openai_client  # noqa: E402


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


def test_api_failure_is_reported_as_failure():
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
