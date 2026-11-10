import builtins

import numpy as np
import pytest

from conflict_sim.claude_backend import ClaudeAgentBackend
from conflict_sim.llm import EmbedCache, LLMError
from conflict_sim.local_embed import DEFAULT_LOCAL_EMBED_MODEL, LocalEmbedder


def lengths(texts):
    return (np.array([len(t), 1.0]) for t in texts)


def test_vectors_come_back_as_lists_in_input_order():
    embed = LocalEmbedder("m", encoder=lengths)
    assert embed(["가", "가나다"]) == [[1.0, 1.0], [3.0, 1.0]]
    assert embed([]) == [] and embed.model == "m"


def test_the_default_model_is_the_small_multilingual_one():
    assert LocalEmbedder().model == DEFAULT_LOCAL_EMBED_MODEL
    assert DEFAULT_LOCAL_EMBED_MODEL == (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")


def test_a_count_mismatch_is_a_failure():
    embed = LocalEmbedder("m", encoder=lambda texts: [np.zeros(2)])
    with pytest.raises(LLMError, match="count"):
        embed(["a", "b"])


def test_a_load_failure_names_the_model(monkeypatch):
    class Broken:
        def __init__(self, model):
            raise OSError("no network")

    monkeypatch.setattr("conflict_sim.local_embed._text_embedding", lambda: Broken)
    with pytest.raises(LLMError, match="m-unreachable"):
        LocalEmbedder("m-unreachable")(["a"])


def test_missing_package_explains_the_install(monkeypatch):
    real = builtins.__import__

    def refuse(name, *args, **kwargs):
        if name.startswith("fastembed"):
            raise ImportError(name)
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", refuse)
    with pytest.raises(LLMError, match="uv sync --extra embed"):
        LocalEmbedder("m")(["a"])


def test_the_model_loads_once_for_many_calls(monkeypatch):
    made = []

    class Model:
        def __init__(self, model):
            made.append(model)

        def embed(self, texts):
            return lengths(texts)

    monkeypatch.setattr("conflict_sim.local_embed._text_embedding", lambda: Model)
    embed = LocalEmbedder("m")
    embed(["a"]), embed(["b"])
    assert made == ["m"]


def test_the_claude_backend_embeds_through_it_and_the_cache_keys_on_its_model(tmp_path):
    backend = ClaudeAgentBackend(embed=LocalEmbedder("모델-A", encoder=lengths))
    assert backend.embed(["가나"]) == [[2.0, 1.0]] and backend.usage["embed"]["calls"] == 1
    assert EmbedCache(backend, tmp_path / "a.sqlite").model == "모델-A"


def test_an_inference_failure_is_an_llm_error_naming_the_model():
    """An LLMError pauses a run (resumable); any other exception fails it."""
    def broken(texts):
        raise RuntimeError("onnxruntime: invalid input")

    with pytest.raises(LLMError, match="m-broken") as error:
        LocalEmbedder("m-broken", encoder=broken)(["a"])
    assert "RuntimeError" in str(error.value)


def test_a_failure_while_reading_the_vectors_is_an_llm_error():
    def lazy(texts):
        yield np.zeros(2)
        raise ValueError("bad batch")

    with pytest.raises(LLMError, match="m-lazy"):
        LocalEmbedder("m-lazy", encoder=lazy)(["a", "b"])
