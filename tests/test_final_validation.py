"""No network: verify paid gates, replay isolation, comparison diagnostics and budget stop."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import token_efficiency_final_validation as validation

from conflict_sim.llm import DemoBackend, LLMError
from conflict_sim.usage_audit import audit_context


@pytest.mark.parametrize("ticks", [5, 8, 32])
def test_demo_pair_and_metadata(tmp_path, ticks):
    result = validation.paired(tmp_path / "run", ticks=ticks)
    assert result["success"]
    assert result["off"]["behavior"] == result["on"]["behavior"]
    assert (
        result["off"]["efficiency"]["logical_completion_calls"]
        == result["on"]["efficiency"]["logical_completion_calls"]
    )
    if ticks >= 8:
        assert result["on"]["efficiency"]["cache_hits"] > 0
    saved = validation.rows(tmp_path / "run/on/audit.jsonl")
    retrieval = [r for r in saved if r["event"] == "retrieval_result"]
    assert all(r["cache_status"] in {"hit", "miss"} for r in retrieval)
    assert all("query" not in r and "description" not in r for r in retrieval)
    prompt = next(r for r in saved if r["event"] == "completion_replay")
    corrupted = dict(prompt, combined_prompt_sha256="changed")
    comparison = validation.compare_metadata(
        saved, [corrupted if r is prompt else r for r in saved]
    )
    assert not comparison["prompt"]["identical"]


@pytest.mark.parametrize("approval,gate", [(False, "1"), (True, "0"), (False, "0")])
def test_paid_approval_before_client_or_output(tmp_path, monkeypatch, approval, gate):
    monkeypatch.setenv("ALLOW_PAID_API_EXPERIMENTS", gate)
    monkeypatch.setattr(
        validation, "create_openai_client", lambda _: pytest.fail("client constructed")
    )
    with pytest.raises(PermissionError):
        validation.paired(tmp_path / "paid", backend="openai", approved=approval)
    assert not (tmp_path / "paid").exists()


def test_replay_refuses_changed_prompt(tmp_path):
    tape = {}
    request = dict(
        system="instructions",
        prompt='{"tasks":[],"tick":0,"last_tick":31,"places":{},"place":"desk"}',
        model="demo",
        temperature=0.8,
        json_mode=True,
        schema=None,
    )
    off = validation.TapeBackend(DemoBackend(), tmp_path / "off", tape, False)
    on = validation.TapeBackend(DemoBackend(), tmp_path / "on", tape, True)
    with audit_context(agent="A", tick=0, call_type="plan_day"):
        off.complete(**request)
        with pytest.raises(LLMError, match="diverged"):
            on.complete(**(request | {"system": "changed"}))


class FakeClient:
    """Local SDK-shaped fixture, never constructs a real client or opens a socket."""

    def __init__(self):
        self.demo = DemoBackend()
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.complete))
        self.embeddings = SimpleNamespace(create=self.embed)

    def with_options(self, **options):
        assert options == {"max_retries": 0}
        return self

    def complete(self, **request):
        self.calls += 1
        system, prompt = [m["content"] for m in request["messages"]]
        output = self.demo.complete(
            system=system,
            prompt=prompt,
            model=request["model"],
            temperature=request["temperature"],
            json_mode="response_format" in request,
        )
        usage = SimpleNamespace(
            prompt_tokens=100,
            completion_tokens=20,
            total_tokens=120,
            prompt_tokens_details=SimpleNamespace(cached_tokens=0),
            completion_tokens_details=SimpleNamespace(reasoning_tokens=0),
            model_dump=lambda: {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        )
        return SimpleNamespace(
            model=request["model"],
            usage=usage,
            choices=[
                SimpleNamespace(
                    finish_reason="stop", message=SimpleNamespace(refusal=None, content=output)
                )
            ],
        )

    def embed(self, **request):
        self.calls += 1
        vectors = self.demo.embed(request["input"])
        return SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=50, total_tokens=50),
            data=[SimpleNamespace(index=i, embedding=v) for i, v in enumerate(vectors)],
        )


def test_mocked_sdk_usage_and_graceful_budget_stop(tmp_path, monkeypatch):
    fake = FakeClient()
    monkeypatch.setenv("ALLOW_PAID_API_EXPERIMENTS", "1")
    monkeypatch.setattr(validation, "create_openai_client", lambda _: fake)
    stopped = validation.paired(tmp_path / "stop", backend="openai", approved=True, cost_cap=1e-8)
    assert stopped["off"]["error_type"] == "BudgetStop"
    assert stopped["on"] is None and not stopped["success"] and fake.calls == 0
    result = validation.paired(tmp_path / "mock", backend="openai", approved=True, cost_cap=1)
    assert result["success"]
    assert result["off"]["efficiency"]["total_tokens"] > 0
    assert result["on"]["efficiency"]["completion_input_tokens"] == 0
    assert (
        result["counterfactual_on_efficiency"]["total_tokens"]
        < result["off"]["efficiency"]["total_tokens"]
    )
    assert result["reserved_usd"] <= 1


@pytest.mark.parametrize("cap", [float("nan"), float("inf"), 0, -1])
def test_invalid_budget(tmp_path, cap):
    with pytest.raises(ValueError):
        validation.paired(tmp_path / "run", cost_cap=cap)
