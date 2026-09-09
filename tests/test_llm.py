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


def test_real_sdk_serializes_json_mode_and_model_parameters():
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=completion('{"urge": 0.5, "reply_to": null}'))

    with client_for(respond) as client:
        text = OpenAIBackend(client).complete(
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
    with client_for(lambda request: httpx.Response(401, json={"error": {
        "message": f"Incorrect API key provided: {secret}",
        "type": "invalid_request_error", "code": "invalid_api_key",
    }})) as client:
        with pytest.raises(LLMError) as error:
            OpenAIBackend(client).complete(
                system="Editor", prompt="Reply", model="large", temperature=0.8, json_mode=False,
            )
    assert "401" in str(error.value)
    assert secret not in str(error.value)
    assert error.value.__suppress_context__
