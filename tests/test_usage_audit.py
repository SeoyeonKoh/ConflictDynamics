"""No-network checks for attribution, retries, persistence and unchanged requests/results."""

import json
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from types import SimpleNamespace

import httpx
import openai
import pytest

from conflict_sim.llm import EmbedCache, LLMError, OpenAIBackend
from conflict_sim.usage_audit import audit_context, log_call, traced


def backend(tmp_path, responses=None):
    replies = iter(responses or ["ok"])
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        if request.url.path.endswith("embeddings"):
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "model": "embed-test",
                    "data": [
                        {"object": "embedding", "index": i, "embedding": [1.0, 0.0]}
                        for i in range(len(body["input"]))
                    ],
                    "usage": {"prompt_tokens": 7, "total_tokens": 7},
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "c",
                "object": "chat.completion",
                "created": 0,
                "model": "test",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": next(replies)},
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                    "prompt_tokens_details": {"cached_tokens": 3},
                },
            },
        )

    client = openai.OpenAI(
        api_key="test",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    return OpenAIBackend(
        client, model_embed="embed-test", audit_path=tmp_path / "audit.jsonl"
    ), requests


def rows(tmp_path, event):
    return [
        row
        for line in (tmp_path / "audit.jsonl").read_text().splitlines()
        if (row := json.loads(line))["event"] == event
    ]


def complete(llm):
    return llm.complete(
        system="system", prompt="private payload", model="test", temperature=0.8, json_mode=True
    )


def test_tokens_context_and_no_raw_prompts(tmp_path):
    llm, requests = backend(tmp_path)
    with audit_context(tick=5, agent="A", call_type="act", caller="Agent._ask"):
        assert complete(llm) == "ok"
    (row,) = rows(tmp_path, "completion")
    assert (row["tick"], row["agent"], row["call_type"], row["caller"]) == (
        5,
        "A",
        "act",
        "Agent._ask",
    )
    assert [row[k] for k in ("input_tokens", "output_tokens", "total_tokens", "cached_tokens")] == [
        10,
        5,
        15,
        3,
    ]
    assert not row["retry"] and "private payload" not in json.dumps(row)
    assert requests[0]["messages"][1]["content"] == "private payload"
    assert llm.usage["decide"]["total_tokens"] == 15


def test_thread_context_isolation_and_cleanup(tmp_path):
    llm, _ = backend(tmp_path, ["ok"] * 3)
    with ThreadPoolExecutor(2) as pool:
        jobs = []
        for agent in ("A", "B"):
            with audit_context(tick=2, agent=agent, call_type="act"):
                jobs.append(pool.submit(copy_context().run, complete, llm))
        assert [f.result() for f in jobs] == ["ok", "ok"]
    complete(llm)
    calls = rows(tmp_path, "completion")
    assert {r["agent"] for r in calls[:2]} == {"A", "B"}
    assert calls[2]["agent"] is None and calls[2]["tick"] is None


def test_embedding_cache_hits_misses_and_batch_count(tmp_path):
    llm, requests = backend(tmp_path)
    cache = EmbedCache(llm, tmp_path / "cache.sqlite")
    with audit_context(tick=3, agent="A", call_type="memory_retrieval_embedding"):
        first = cache.embed(["a", "b"])
        assert cache.embed(["a", "b"]) == first
    assert len(requests) == 1
    assert [
        (r["text_count"], r["cache_hits"], r["cache_misses"])
        for r in rows(tmp_path, "embedding_cache")
    ] == [(2, 0, 2), (2, 2, 0)]
    (call,) = rows(tmp_path, "embedding")
    assert call["agent"] == "A" and call["text_count"] == 2 and call["call_count"] == 1
    assert call["total_tokens"] == 7


def test_validation_and_action_retries_are_separate(tmp_path):
    from test_agent import make_agent, view

    bad = json.dumps({"plan": [{"kind": "work", "until": 16, "text": "Lead."}]})
    good = json.dumps({"plan": [{"kind": "rest", "until": 16, "text": "Wait."}]})
    llm, _ = backend(tmp_path, [bad, good])
    agent = make_agent(llm)
    with audit_context(action_retry=True, rejection_attempt=1):
        assert agent.plan_day(view(tick=0), 0)[0].kind == "rest"
    calls = rows(tmp_path, "completion")
    assert [r["validation_retry"] for r in calls] == [False, True]
    assert all(
        r["action_retry"] and r["agent"] == "B" and r["call_type"] == "plan_day" for r in calls
    )


def test_rate_limit_retry_attribution(tmp_path, monkeypatch):
    llm, _ = backend(tmp_path)
    real = llm.client.chat.completions.create
    attempts = []

    def respond(**kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise openai.RateLimitError(
                "rate",
                response=httpx.Response(
                    429, request=httpx.Request("POST", "https://example.invalid")
                ),
                body={},
            )
        return real(**kwargs)

    monkeypatch.setattr(llm.client.chat.completions, "create", respond)
    monkeypatch.setattr("conflict_sim.llm.time.sleep", lambda _: None)
    assert complete(llm) == "ok"
    (row,) = rows(tmp_path, "completion")
    assert row["transport_retry"] and row["retry"] and row["rate_limit_attempt"] == 1


def test_missing_usage_logged_before_existing_error(tmp_path, monkeypatch):
    llm, _ = backend(tmp_path)
    monkeypatch.setattr(
        llm.client.chat.completions,
        "create",
        lambda **kw: SimpleNamespace(usage=None, model="test", choices=[]),
    )
    with pytest.raises(LLMError, match="no usage"):
        complete(llm)
    assert rows(tmp_path, "completion")[0]["input_tokens"] is None


def test_decorator_preserves_result_and_cleans_up_exception(caplog):
    class Actor:
        name = "A"

        @traced("act")
        def act(self, tick):
            log_call("probe")
            raise ValueError("same exception")

    with caplog.at_level("INFO", logger="conflict_sim.llm"):
        with pytest.raises(ValueError, match="same exception"):
            Actor().act(7)
        log_call("probe")
    calls = [json.loads(r.message.split("LLM audit ")[1]) for r in caplog.records]
    assert calls[0]["tick"] == 7 and calls[0]["agent"] == "A"
    assert calls[1]["tick"] is None and calls[1]["agent"] is None


def test_meeting_speech_inherits_tick_without_changing_speak_signature(tmp_path):
    from test_agent import make_agent
    from test_conversation import session

    llm, _ = backend(tmp_path)
    conversation = session([make_agent(llm)], kind="meeting", rule="everyone")
    conversation.step(8)
    (call,) = rows(tmp_path, "completion")
    assert (call["tick"], call["agent"], call["call_type"], call["session_kind"]) == (
        8,
        "B",
        "speech",
        "meeting",
    )


def test_reflection_embeddings_and_insights_keep_distinct_types(tmp_path):
    from test_memory import record, store

    llm, _ = backend(tmp_path, ['{"questions": ["What changed?"]}', '{"insights": []}'])
    memory = store(llm, reflect_questions=1)
    item = record(memory, "A task changed.", 1)
    memory.set_embeddings({item.id: [1.0, 0.0]})
    memory.reflect(6, 0)
    calls = rows(tmp_path, "completion")
    assert [(r["call_type"], r["schema"], r["reflection_scope"]) for r in calls] == [
        ("reflection", "Questions", "periodic"),
        ("reflection", "Insights", "periodic"),
    ]
    (query,) = rows(tmp_path, "embedding")
    assert query["embedding_purpose"] == "reflection_retrieval"
    assert query["call_type"] == "reflection_retrieval_embedding"
    assert query["tick"] == 6 and query["agent"] == "Alex"


def test_section_hashes_sizes_and_whitespace_fingerprints():
    from conflict_sim.usage_audit import completion_metadata, text_metric

    payload = {"task_board": ["SECRET_BOARD_92"], "view": {"tasks": [], "tick": 4}}
    prompt = json.dumps(payload)
    data = completion_metadata("SECRET_SYSTEM_93", prompt)
    assert data["section_metrics"]["task_board"]["chars"] == len(json.dumps(payload["task_board"]))
    assert "view.tasks" in data["section_metrics"] and "view" not in data["section_metrics"]
    assert "SECRET_BOARD_92" not in json.dumps(data)
    assert "SECRET_SYSTEM_93" not in json.dumps(data)
    first, second = text_metric("phase   at office"), text_metric("phase at office")
    assert first["sha256"] != second["sha256"]
    assert first["whitespace_sha256"] == second["whitespace_sha256"]
    payload["view"]["tick"] = 5
    changed = completion_metadata("SECRET_SYSTEM_93", json.dumps(payload))
    assert changed["section_metrics"]["task_board"] == data["section_metrics"]["task_board"]
    assert changed["section_metrics"]["view.tick"] != data["section_metrics"]["view.tick"]


def test_agent_sections_embedding_hashes_and_no_raw_log(tmp_path):
    from test_agent import make_agent, view

    good = json.dumps({"plan": [{"kind": "rest", "until": 16, "text": "SECRET_PLAN_94"}]})
    llm, _ = backend(tmp_path, [good])
    actor = make_agent(llm, persona_placement="system")
    actor.plan_day(view(tick=0), 0)
    (call,) = rows(tmp_path, "completion")
    assert call["section_metrics"]["fixed_instructions"]["chars"] > 0
    assert call["section_metrics"]["system_persona"]["chars"] > 0
    assert "system_section_metrics" not in call
    with audit_context(tick=3, agent="A", call_type="memory_retrieval_embedding"):
        llm.embed(["SECRET_QUERY_95"])
    (query,) = rows(tmp_path, "embedding")
    assert query["text_metrics"][0]["chars"] == len("SECRET_QUERY_95")
    assert "SECRET_QUERY_95" not in (tmp_path / "audit.jsonl").read_text()
    assert "SECRET_PLAN_94" not in (tmp_path / "audit.jsonl").read_text()


def test_invalid_reply_diagnostics_are_hashes_not_error_body(tmp_path):
    from test_agent import make_agent, view

    good = json.dumps({"plan": [{"kind": "rest", "until": 16, "text": "Wait."}]})
    llm, _ = backend(tmp_path, ['{"SECRET_BAD_INPUT_96": true}', good])
    make_agent(llm).plan_day(view(tick=0), 0)
    (failure,) = rows(tmp_path, "validation_failure")
    assert failure["agent"] == "B" and failure["tick"] == 0
    assert failure["issues"] and failure["failure_hash"]
    assert "SECRET_BAD_INPUT_96" not in (tmp_path / "audit.jsonl").read_text()


def test_hash_metadata_in_parallel_keeps_system_sections_separate(tmp_path):
    from conflict_sim.usage_audit import text_metric

    llm, _ = backend(tmp_path, ["ok", "ok"])
    with ThreadPoolExecutor(2) as pool:
        jobs = []
        for name in ("A", "B"):
            with audit_context(agent=name, system_section_metrics={"persona": text_metric(name)}):
                jobs.append(pool.submit(copy_context().run, complete, llm))
        assert [f.result() for f in jobs] == ["ok", "ok"]
    calls = rows(tmp_path, "completion")
    assert all(r["section_metrics"]["persona"] == text_metric(r["agent"]) for r in calls)


def test_theoretical_nested_action_retry_bound_without_paid_api(tmp_path, monkeypatch):
    import random

    from test_loop import Recorder

    from conflict_sim.agent import Agent
    from conflict_sim.company_runtime import apply_initial_relationships, build_company_config
    from conflict_sim.environment import Environment
    from conflict_sim.llm import DemoBackend
    from conflict_sim.loop import Loop
    from conflict_sim.models import Action, Rejected
    from conflict_sim.usage_audit import completion_metadata

    target = "HDS-002"
    seen = []
    cfg = build_company_config("s0_smoke")

    class Forced:
        audit_path = tmp_path / "audit.jsonl"

        def __init__(self):
            self.backend = DemoBackend()

        def complete(self, **request):
            payload = json.loads(request["prompt"])
            if request["schema"] is Action and payload["speaker"] == target:
                with audit_context(audit_path=self.audit_path):
                    log_call(
                        "completion", **completion_metadata(request["system"], request["prompt"])
                    )
                seen.append(1)
                return (
                    "{}"
                    if len(seen) % 2
                    else Action(
                        kind="rest",
                        reflection="Wait.",
                        expression="neutral",
                        importance=1,
                        valence=0,
                        arousal=0,
                    ).model_dump_json()
                )
            return self.backend.complete(**request)

        def embed(self, texts):
            return self.backend.embed(texts)

    llm = Forced()
    agents = [Agent(spec, cfg, llm) for spec in cfg.agents]
    apply_initial_relationships(agents)
    env = Environment(cfg.environment, cfg.agents)
    original = env.apply

    def refuse(actor, action, tick, *rest):
        if actor == target:
            return Rejected(action=action, reason="forced rejection for bound test")
        return original(actor, action, tick, *rest)

    monkeypatch.setattr(env, "apply", refuse)
    world = Loop(cfg, agents, env, llm, random.Random(cfg.random_seed), Recorder())
    try:
        world.tick(1)
    finally:
        world.close()
    calls = rows(tmp_path, "completion")
    assert len(calls) == 6
    assert [r["action_retry"] for r in calls] == [False, False, True, True, True, True]
    assert [r["validation_retry"] for r in calls] == [False, True] * 3
