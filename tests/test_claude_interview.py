"""Interviews on the Claude provider, and questions about Claude runs."""

import json
import threading

import pytest
from test_server import _call

import conflict_sim.server as server_module
from conflict_sim.experiment import run_scenario
from conflict_sim.interview import question_embedder, run_embedder
from conflict_sim.local_embed import LocalEmbedder
from conflict_sim.server import make_server


def as_claude_run(run_dir, embed_backend, model_embed):
    """Rewrite a demo run's config as a Claude run's (the stored vectors stay demo ones)."""
    path = run_dir / "resolved_config.json"
    config = json.loads(path.read_text())
    config |= {"backend": "claude", "model_decide": "claude-haiku-5-5",
               "model_speak": "claude-haiku-5-5", "embed_backend": embed_backend,
               "model_embed": model_embed}  # fmt: skip
    path.write_text(json.dumps(config))


@pytest.fixture
def run(tmp_path):
    path = tmp_path / "runs" / "one" / "s0_smoke" / "replicate-1"
    run_scenario("s0_smoke", path)
    return path


def test_a_question_about_a_claude_run_uses_that_runs_embedder(run, tmp_path):
    as_claude_run(run, "local", "모델-A")
    embed = run_embedder(run, tmp_path / ".env")
    assert isinstance(embed, LocalEmbedder) and embed.model == "모델-A"


def test_local_embeddings_answer_even_on_the_demo_provider(run, tmp_path):
    as_claude_run(run, "local", "모델-A")
    embed = question_embedder("claude", "demo", tmp_path / ".env", run)
    assert isinstance(embed, LocalEmbedder) and embed.model == "모델-A"


def test_openai_embeddings_of_a_claude_run_stay_unpaid_on_demo(run, tmp_path):
    as_claude_run(run, "openai", "text-embedding-3-small")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-test\n")
    assert question_embedder("claude", "demo", tmp_path / ".env", run) is None
    paid = question_embedder("claude", "claude", tmp_path / ".env", run)
    assert paid is not None and paid.model == "text-embedding-3-small"


def test_openai_embeddings_without_a_key_are_none(run, tmp_path):
    as_claude_run(run, "openai", "text-embedding-3-small")
    assert question_embedder("claude", "claude", tmp_path / ".env", run) is None


class FakeClaude:
    def __init__(self):
        self.asked = []
        self.auth = "subscription"

    def complete(self, **request):
        self.asked.append(request)
        return "네, 기억나요."


def test_interview_on_the_claude_provider_asks_claude(tmp_path, monkeypatch, run):
    monkeypatch.setattr(server_module, "installed", lambda module: True)
    fake, built = FakeClaude(), []

    def make(env_file, **options):
        built.append(options)
        return fake

    monkeypatch.setattr(server_module, "make_claude_backend", make)
    (tmp_path / ".env").write_text("")
    httpd = make_server(runs_root=tmp_path / "runs", settings_path=tmp_path / "s.json",
                        static_root=None, env_file=tmp_path / ".env", port=0)  # fmt: skip
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        assert _call(base, "/api/settings", "PUT", {"provider": "claude"})[0] == 200
        path = "one/s0_smoke/replicate-1"
        status, text = _call(base, f"/api/runs/{path}/interviews", "POST",
                             {"agent": "HDS-001", "tick": 5})  # fmt: skip
        iv = json.loads(text)
        assert status == 200 and iv["provider"] == "claude" and iv["model"] == "claude-haiku-5-5"
        status, text = _call(base, f"/api/runs/{path}/interviews/{iv['id']}/ask", "POST",
                             {"question": "안녕하세요?"})  # fmt: skip
        assert status == 200 and json.loads(text)["a"] == "네, 기억나요."
        assert fake.asked[0]["model"] == "claude-haiku-5-5"
        assert built[0]["max_total_tokens"] is None and built[0]["reasoning_effort"] == "none"
    finally:
        httpd.shutdown()
