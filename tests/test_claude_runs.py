"""Claude runs: the run config, the backend factory and the experiment path."""

import json

import pytest
from pydantic import ValidationError

import conflict_sim.experiment as experiment
from conflict_sim.claude_backend import ClaudeAgentBackend
from conflict_sim.company_runtime import build_company_config
from conflict_sim.experiment import run_scenario
from conflict_sim.llm import DemoBackend, LLMError, OpenAIBackend, is_paid, make_backend
from conflict_sim.local_embed import DEFAULT_LOCAL_EMBED_MODEL, LocalEmbedder
from conflict_sim.models import Config

LIMIT = "Claude 구독 한도에 닿았습니다 (five_hour). 그 뒤에 이어서 실행하세요."


def variant(cfg: Config, **changes) -> Config:
    return Config.model_validate(cfg.model_dump() | changes)


def test_a_company_claude_run_defaults_to_haiku_and_local_embeddings():
    cfg = build_company_config("s0_smoke", backend="claude")
    assert (cfg.backend, cfg.model_decide, cfg.model_speak) == (
        "claude", "claude-haiku-5-5", "claude-haiku-5-5")
    assert cfg.embed_backend == "local" and cfg.model_embed == DEFAULT_LOCAL_EMBED_MODEL
    assert cfg.reasoning_effort == "none" and cfg.claude_max_concurrent == 4
    assert cfg.max_total_tokens == 30_000_000


@pytest.mark.parametrize("changes, message", [
    ({"model_decide": None}, "model_decide"),
    ({"embed_backend": None}, "embed_backend"),
    ({"embed_backend": "openai", "model_embed": None}, "model_embed"),
])
def test_a_claude_run_needs_models_and_an_embedding_choice(changes, message):
    cfg = build_company_config("s0_smoke", backend="claude")
    with pytest.raises(ValidationError, match=message):
        variant(cfg, **changes)


def test_openai_and_demo_runs_are_unchanged():
    assert build_company_config("s0_smoke").embed_backend is None
    openai = build_company_config("s0_smoke", backend="openai")
    assert openai.embed_backend is None and openai.model_decide == "gpt-6-luna"


def test_is_paid():
    assert [is_paid("demo", None), is_paid("openai", None), is_paid("claude", "local"),
            is_paid("claude", "openai")] == [False, True, False, True]  # fmt: skip


def test_make_backend_builds_each_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    env = tmp_path / ".env"
    assert isinstance(make_backend(build_company_config("s0_smoke"), env), DemoBackend)
    openai = make_backend(build_company_config("s0_smoke", backend="openai"), env)
    assert isinstance(openai, OpenAIBackend) and openai.max_total_tokens == 500_000
    claude_cfg = variant(build_company_config("s0_smoke", backend="claude"),
                         claude_max_concurrent=2)  # fmt: skip
    claude = make_backend(claude_cfg, env, audit_path=tmp_path / "audit.jsonl")
    assert isinstance(claude, ClaudeAgentBackend)
    assert claude.gate._initial_value == 2 and claude.reasoning_effort == "none"
    assert claude.model_embed == DEFAULT_LOCAL_EMBED_MODEL
    assert claude.audit_path == tmp_path / "audit.jsonl"


def test_openai_embeddings_on_a_claude_run_count_in_its_usage(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    cfg = variant(build_company_config("s0_smoke", backend="claude"),
                  embed_backend="openai", model_embed="text-embedding-3-small")  # fmt: skip
    claude = make_backend(cfg, tmp_path / ".env")
    assert claude.model_embed == "text-embedding-3-small"
    claude._embed.usage["total_tokens"] += 7  # what an OpenAI embedding call would add
    assert claude.usage["embed"]["total_tokens"] == 7


class FakeClaude(DemoBackend):
    """Demo replies, Claude bookkeeping; trips a subscription limit at a given tick."""

    def __init__(self, trip_at=None, embed_fails=False):
        super().__init__()
        self.trip_at, self.embed_fails = trip_at, embed_fails
        self.usage = {"decide": {"total_tokens": 0}, "speak": {"total_tokens": 0}}
        self.auth, self.cli_version, self.warnings = "subscription", "2.1.321", []

    def complete(self, **request):
        payload = json.loads(request["prompt"]) if request["prompt"].startswith("{") else {}
        tick = payload.get("view", {}).get("tick") or payload.get("tick")
        if self.trip_at is not None and tick is not None and tick >= self.trip_at:
            raise LLMError(LIMIT)
        return super().complete(**request)

    def embed(self, texts):
        if self.embed_fails:
            raise LLMError("Local embedding model m could not be loaded: OSError")
        return super().embed(texts)


def claude_run(monkeypatch, fake):
    monkeypatch.setattr(experiment, "make_backend", lambda cfg, env_file, **_: fake)


def test_a_keyless_claude_run_needs_no_cost_approval(tmp_path, monkeypatch):
    monkeypatch.delenv("ALLOW_PAID_API_EXPERIMENTS", raising=False)
    claude_run(monkeypatch, FakeClaude())
    summary = run_scenario("s0_smoke", tmp_path / "run", backend="claude", pilot=True)
    assert summary["run_status"] == "completed"


def test_a_claude_run_with_openai_embeddings_needs_cost_approval(tmp_path, monkeypatch):
    monkeypatch.delenv("ALLOW_PAID_API_EXPERIMENTS", raising=False)
    claude_run(monkeypatch, FakeClaude())
    with pytest.raises(PermissionError, match="user cost approval"):
        run_scenario("s0_smoke", tmp_path / "run", backend="claude", pilot=True,
                     embed_backend="openai", model_embed="text-embedding-3-small")  # fmt: skip


def test_a_claude_run_needs_pilot(tmp_path, monkeypatch):
    claude_run(monkeypatch, FakeClaude())
    with pytest.raises(PermissionError, match="--pilot"):
        run_scenario("s0_smoke", tmp_path / "run", backend="claude")


def test_the_manifest_records_how_the_run_called_the_model(tmp_path, monkeypatch):
    claude_run(monkeypatch, FakeClaude())
    run_scenario("s0_smoke", tmp_path / "run", backend="claude", pilot=True)
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    assert manifest["backend"] == "claude" and manifest["model_id"] == "claude-haiku-5-5"
    llm = manifest["llm"]
    assert llm["provider"] == "claude" and llm["embed_backend"] == "local"
    assert llm["embed_model"] == DEFAULT_LOCAL_EMBED_MODEL
    assert llm["temperature_sent"] is False and llm["injected_context"] is True
    assert llm["auth"] == "subscription" and llm["cli_version"] == "2.1.321"
    resolved = json.loads((tmp_path / "run" / "resolved_config.json").read_text())
    assert resolved["embed_backend"] == "local"


def test_a_limit_mid_run_pauses_and_resume_does_not_repeat_ticks(tmp_path, monkeypatch):
    output = tmp_path / "run"
    claude_run(monkeypatch, FakeClaude(trip_at=34))
    paused = run_scenario("s0_baseline", output, backend="claude", pilot=True)
    assert paused["run_status"] == "paused" and paused["checkpoint"] == 0
    assert json.loads((output / "paused.json").read_text())["reason"] == LIMIT
    claude_run(monkeypatch, FakeClaude())
    summary = run_scenario("s0_baseline", output, backend="claude", pilot=True, resume=True)
    assert summary["run_status"] == "completed"
    rows = [json.loads(line) for line in (output / "frames.jsonl").read_text().splitlines()]
    ticks = [row["tick"] for row in rows if row["type"] == "frame"]
    assert ticks == list(range(68))


def test_an_unusable_embedder_pauses_before_the_first_tick_and_says_why(tmp_path, monkeypatch):
    claude_run(monkeypatch, FakeClaude(embed_fails=True))
    summary = run_scenario("s0_smoke", tmp_path / "run", backend="claude", pilot=True)
    assert summary["run_status"] == "paused" and "could not be loaded" in summary["reason"]
    journal = (tmp_path / "run" / "frames.jsonl").read_text().splitlines()
    rows = [json.loads(line) for line in journal]
    assert not any(row["type"] == "frame" for row in rows)
    said = [row["message"] for row in rows if row["type"] == "status"]
    assert any("임베딩 모델" in message for message in said)  # the download notice came first
    assert "could not be loaded" in said[-1]


def test_a_failed_embedder_on_resume_keeps_the_run_paused_and_resumable(tmp_path, monkeypatch):
    from conflict_sim.runs import discover_company_runs

    root = tmp_path / "root"
    output = root / "x" / "s0_baseline" / "replicate-1"
    claude_run(monkeypatch, FakeClaude(trip_at=34))
    run_scenario("s0_baseline", output, backend="claude", pilot=True)
    claude_run(monkeypatch, FakeClaude(embed_fails=True))
    again = run_scenario("s0_baseline", output, backend="claude", pilot=True, resume=True)
    assert again["run_status"] == "paused" and "could not be loaded" in again["reason"]
    rows, _ = discover_company_runs(root)
    assert [(r["status"], r["resumable"]) for r in rows] == [("paused", True)]
    claude_run(monkeypatch, FakeClaude())
    summary = run_scenario("s0_baseline", output, backend="claude", pilot=True, resume=True)
    assert summary["run_status"] == "completed"
    journal = (output / "frames.jsonl").read_text().splitlines()
    assert [json.loads(line)["tick"] for line in journal
            if json.loads(line)["type"] == "frame"] == list(range(68))  # fmt: skip


def paused_openai_embedding_run(tmp_path, monkeypatch):
    output = tmp_path / "run"
    monkeypatch.setenv("ALLOW_PAID_API_EXPERIMENTS", "1")
    claude_run(monkeypatch, FakeClaude(trip_at=34))
    run_scenario("s0_baseline", output, backend="claude", pilot=True, embed_backend="openai",
                 model_embed="text-embedding-3-small")  # fmt: skip
    monkeypatch.delenv("ALLOW_PAID_API_EXPERIMENTS")
    return output


def test_a_hand_resume_of_a_paid_claude_run_still_needs_approval(tmp_path, monkeypatch):
    output = paused_openai_embedding_run(tmp_path, monkeypatch)
    before = (output / "paused.json").read_text()
    with pytest.raises(PermissionError, match="user cost approval"):
        run_scenario("s0_baseline", output, backend="claude", pilot=True, resume=True)
    assert (output / "paused.json").read_text() == before
    assert not (output / ".before-replay").exists()  # refused before anything moved


def test_a_resume_keeps_the_runs_own_embeddings(tmp_path, monkeypatch):
    output = paused_openai_embedding_run(tmp_path, monkeypatch)
    monkeypatch.setenv("ALLOW_PAID_API_EXPERIMENTS", "1")
    seen = []

    def make(cfg, env_file, **_):
        seen.append((cfg.embed_backend, cfg.model_embed))
        return FakeClaude()

    monkeypatch.setattr(experiment, "make_backend", make)
    run_scenario("s0_baseline", output, backend="claude", pilot=True, resume=True)
    assert seen == [("openai", "text-embedding-3-small")]


def test_a_run_works_with_vectors_of_another_size(tmp_path, monkeypatch):
    class Small(FakeClaude):
        def embed(self, texts):
            return [[float(len(t)), 1.0, 0.5] for t in texts]

    claude_run(monkeypatch, Small())
    summary = run_scenario("p0_documents_ko", tmp_path / "run", backend="claude", pilot=True,
                           max_days=1)  # fmt: skip
    assert summary["run_status"] == "completed"


def test_a_limit_warning_reaches_the_live_status_once(tmp_path, monkeypatch):
    fake = FakeClaude()
    original = fake.complete

    def warn_then_complete(**request):
        if not fake.warnings:
            fake.warnings.append("Claude 구독 한도에 가까워졌습니다 (seven_day).")
        return original(**request)

    fake.complete = warn_then_complete
    claude_run(monkeypatch, fake)
    run_scenario("s0_smoke", tmp_path / "run", backend="claude", pilot=True)
    journal = (tmp_path / "run" / "frames.jsonl").read_text().splitlines()
    rows = [json.loads(line) for line in journal]
    said = [r for r in rows if r["type"] == "status" and "seven_day" in r.get("message", "")]
    assert len(said) == 1


def test_a_local_embedder_has_its_model_name():
    assert LocalEmbedder().model == DEFAULT_LOCAL_EMBED_MODEL


def test_the_viewer_port_opens_before_the_embedder_loads(tmp_path, monkeypatch, capsys):
    """live._launch waits ~30 s for the port line; a first-use model download must not hold it."""
    claude_run(monkeypatch, FakeClaude(embed_fails=True))
    summary = run_scenario("s0_smoke", tmp_path / "run", backend="claude", pilot=True,
                           live_port=0)  # fmt: skip
    assert summary["run_status"] == "paused"
    assert "Viewer WebSocket: ws://127.0.0.1:" in capsys.readouterr().out


def test_openai_embeddings_alone_name_the_openai_model(tmp_path, monkeypatch):
    """`--embed-backend openai` without `--model-embed` must not keep the local model's name."""
    monkeypatch.setenv("ALLOW_PAID_API_EXPERIMENTS", "1")
    seen = []

    def make(cfg, env_file, **_):
        seen.append((cfg.embed_backend, cfg.model_embed))
        return FakeClaude()

    monkeypatch.setattr(experiment, "make_backend", make)
    run_scenario("s0_smoke", tmp_path / "run", backend="claude", pilot=True,
                 embed_backend="openai")  # fmt: skip
    assert seen == [("openai", "text-embedding-3-small")]
