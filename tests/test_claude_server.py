"""The Claude provider in conflict-server: settings, the paid-run rule and live starts."""

import json
import threading

import pytest
from test_server import _call

import conflict_sim.server as server_module
from conflict_sim import live
from conflict_sim.experiment import run_scenario
from conflict_sim.llm import LLMError
from conflict_sim.runs import discover_company_runs
from conflict_sim.server import make_server

SECRET = "sk-ant-oat01-secret-token"


@pytest.fixture
def claude_server(tmp_path, monkeypatch):
    monkeypatch.setattr(server_module, "installed", lambda module: True)
    runs = tmp_path / "runs"
    run_scenario("s0_smoke", runs / "one" / "s0_smoke" / "replicate-1")
    (tmp_path / ".env").write_text(
        f"OPENAI_API_KEY=sk-secret-value\nCLAUDE_CODE_OAUTH_TOKEN={SECRET}\n")
    httpd = make_server(runs_root=runs, settings_path=tmp_path / "settings.json",
                        static_root=None, env_file=tmp_path / ".env", port=0)  # fmt: skip
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", httpd
    httpd.shutdown()


def settings(base):
    return json.loads(_call(base, "/api/settings")[1])


def put(base, **changes):
    return _call(base, "/api/settings", "PUT", settings(base) | changes)


def test_claude_settings_round_trip(claude_server):
    base, _ = claude_server
    assert put(base, provider="claude")[0] == 200
    got = settings(base)
    assert got["provider"] == "claude" and got["claude_model_decide"] == "claude-haiku-5-5"
    assert got["claude_model_speak"] == "claude-haiku-5-5" and got["claude_embed"] == "local"
    assert got["claude_max_concurrent"] == 4 and got["claude_max_total_tokens"] == 30_000_000
    assert got["paid"] is False and got["claude_sdk"] is True and got["local_embed"] is True
    assert got["claude_login"] is True  # the token in .env; its value never leaves the server
    assert SECRET not in json.dumps(got)
    assert put(base, claude_embed="openai")[0] == 200 and settings(base)["paid"] is True
    assert put(base, claude_embed="other")[0] == 400
    assert put(base, claude_max_concurrent=0)[0] == 400
    assert put(base, claude_model_speak="")[0] == 400
    assert put(base, provider="anthropic")[0] == 400


def test_the_login_is_unknown_without_a_token(tmp_path, monkeypatch):
    monkeypatch.setattr(server_module, "installed", lambda module: True)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-x\n")
    httpd = make_server(runs_root=tmp_path / "runs", settings_path=tmp_path / "s.json",
                        static_root=None, env_file=tmp_path / ".env", port=0)  # fmt: skip
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        assert settings(f"http://127.0.0.1:{httpd.server_address[1]}")["claude_login"] is None
    finally:
        httpd.shutdown()


def test_choosing_claude_without_the_sdk_is_a_409_with_the_install_line(claude_server,
                                                                       monkeypatch):  # fmt: skip
    base, httpd = claude_server
    monkeypatch.setattr(server_module, "installed", lambda module: module != "claude_agent_sdk")
    status, body = put(base, provider="claude")
    assert status == 409 and "uv sync --extra claude" in body
    httpd.settings_path.write_text(json.dumps({"provider": "claude"}))  # chosen before
    status, body = _call(base, "/api/live", "POST", {"scenario": "s0_smoke"})
    assert status == 409 and "uv sync --extra claude" in body


def test_local_embedding_without_the_package_is_a_409(claude_server, monkeypatch):
    base, _ = claude_server
    monkeypatch.setattr(server_module, "installed", lambda module: module != "fastembed")
    status, body = put(base, provider="claude", claude_embed="local")
    assert status == 409 and "uv sync --extra embed" in body
    assert put(base, provider="claude", claude_embed="openai")[0] == 200


class Launched(Exception):
    pass


def capture_launch(monkeypatch):
    """Stop live._launch at the process start and keep its command and environment."""
    seen = {}

    def popen(argv, **kwargs):
        seen.update(argv=argv, env=kwargs["env"])
        raise Launched

    monkeypatch.setattr(live.subprocess, "Popen", popen)
    return seen


def test_a_keyless_claude_start_needs_no_paid_confirmation(tmp_path, monkeypatch):
    seen = capture_launch(monkeypatch)
    monkeypatch.delenv("ALLOW_PAID_API_EXPERIMENTS", raising=False)
    models = {"model_decide": "claude-haiku-5-5", "model_speak": "claude-haiku-5-5",
              "model_embed": "m-local", "embed_backend": "local", "claude_max_concurrent": 3}
    with pytest.raises(Launched):
        live.start(tmp_path, scenario="s0_smoke", days=1, max_total_tokens=None,
                   backend="claude", models=models, paid_confirmed=False)  # fmt: skip
    argv = seen["argv"]
    assert argv[argv.index("--backend") + 1] == "claude"
    assert argv[argv.index("--embed-backend") + 1] == "local"
    assert argv[argv.index("--claude-max-concurrent") + 1] == "3"
    assert "ALLOW_PAID_API_EXPERIMENTS" not in seen["env"]


def test_claude_with_openai_embeddings_needs_confirmation(tmp_path, monkeypatch):
    seen = capture_launch(monkeypatch)
    models = {"embed_backend": "openai", "model_embed": "text-embedding-3-small"}
    with pytest.raises(PermissionError):
        live.start(tmp_path, scenario="s0_smoke", days=1, max_total_tokens=None,
                   backend="claude", models=models, paid_confirmed=False)  # fmt: skip
    with pytest.raises(Launched):
        live.start(tmp_path, scenario="s0_smoke", days=1, max_total_tokens=None,
                   backend="claude", models=models, paid_confirmed=True)  # fmt: skip
    assert seen["env"]["ALLOW_PAID_API_EXPERIMENTS"] == "1"


def paused_claude_run(root, embed_backend):
    run_dir = root / "ui-x" / "s0_smoke" / "replicate-1"
    run_scenario("s0_smoke", run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text())
    manifest |= {"backend": "claude", "status": "paused",
                 "llm": {"provider": "claude", "embed_backend": embed_backend}}  # fmt: skip
    (run_dir / "manifest.json").write_text(json.dumps(manifest))
    (run_dir / "paused.json").write_text(json.dumps({"status": "paused", "tick": 3,
                                                     "checkpoint": None}))  # fmt: skip
    return run_dir


def test_resume_reads_the_embedding_choice_from_the_manifest(tmp_path, monkeypatch):
    paused_claude_run(tmp_path, "local")
    seen = capture_launch(monkeypatch)  # after the run is made: it shells out to git
    with pytest.raises(Launched):
        live.resume(tmp_path, "ui-x/s0_smoke/replicate-1", max_total_tokens=None,
                    paid_confirmed=False)  # fmt: skip
    argv = seen["argv"]
    assert argv[argv.index("--embed-backend") + 1] == "local"


def test_run_rows_say_whether_resuming_is_paid(tmp_path):
    paused_claude_run(tmp_path, "openai")
    rows, _ = discover_company_runs(tmp_path)
    assert [r["paid"] for r in rows] == [True]
    run_scenario("s0_smoke", tmp_path / "demo" / "s0_smoke" / "replicate-1")
    rows, _ = discover_company_runs(tmp_path)
    assert sorted(r["paid"] for r in rows) == [False, True]


def test_a_claude_start_through_the_server_passes_the_claude_models(claude_server,
                                                                    monkeypatch):  # fmt: skip
    base, _ = claude_server
    seen = capture_launch(monkeypatch)
    put(base, provider="claude", claude_model_decide="claude-sonnet-5-5")
    status, _ = _call(base, "/api/live", "POST", {"scenario": "s0_smoke"})
    argv = seen["argv"]
    assert argv[argv.index("--model-decide") + 1] == "claude-sonnet-5-5"
    assert argv[argv.index("--embed-backend") + 1] == "local"
    assert argv[argv.index("--max-total-tokens") + 1] == "30000000"


class Checked:
    def __init__(self, fail=None):
        self.fail, self.auth = fail, None

    def complete(self, **request):
        if self.fail:
            raise LLMError(self.fail)
        self.auth = "subscription"
        return "OK"


def test_claude_check_reports_the_login_and_never_returns_credentials(claude_server):
    base, httpd = claude_server
    httpd.claude_check_backend = lambda: Checked()
    status, body = _call(base, "/api/settings/claude-check", "POST", {})
    assert status == 200 and json.loads(body) == {"ok": True, "auth": "subscription",
                                                  "error": None}  # fmt: skip
    httpd.claude_check_backend = lambda: Checked(fail="Claude call failed: ProcessError, exit 1")
    status, body = _call(base, "/api/settings/claude-check", "POST", {})
    got = json.loads(body)
    assert status == 200 and got["ok"] is False and "ProcessError" in got["error"]
    assert SECRET not in body


# ---- Task 7: the scenario generator on the Claude provider ----
from test_claude_backend import limit, result  # noqa: E402

from conflict_sim.claude_backend import ClaudeAgentBackend  # noqa: E402
from conflict_sim.server import GENERATION_TOKEN_CAP  # noqa: E402


def claude_generator(monkeypatch, messages):
    """The generator's Claude backend, built by the server, with the SDK call replaced."""
    built, seen = [], []

    async def run_query(*, prompt, options):
        seen.append(options)
        for message in messages:
            yield message

    def make(env_file, **options):
        built.append(options)
        return ClaudeAgentBackend(run_query=run_query, **options)

    monkeypatch.setattr(server_module, "make_claude_backend", make)
    return built, seen


def new_draft(base):
    status, body = _call(base, "/api/drafts", "POST", {"mode": "scratch", "source": None})
    assert status == 200
    return json.loads(body)["id"]


def test_the_generator_runs_on_the_claude_provider(claude_server, monkeypatch):
    base, _ = claude_server
    reply = json.dumps({"reply": "무엇을 비교할까요?", "next": "ask", "settings": {}})
    built, seen = claude_generator(monkeypatch, [result(reply)])
    put(base, provider="claude", claude_model_decide="claude-sonnet-5-5")
    draft = new_draft(base)
    status, body = _call(base, f"/api/drafts/{draft}/messages", "POST",
                         {"text": "실험하고 싶어", "files": []})  # fmt: skip
    assert status == 200 and json.loads(body)["messages"][-1]["text"] == "무엇을 비교할까요?"
    assert seen[0]["model"] == "claude-sonnet-5-5" and "output_format" not in seen[0]
    assert built[0]["max_total_tokens"] == GENERATION_TOKEN_CAP
    assert built[0]["max_input_chars"] == 400_000 and built[0]["max_concurrent"] == 1


def test_the_demo_provider_still_refuses_generation(claude_server):
    base, _ = claude_server
    put(base, provider="demo")
    status, body = _call(base, f"/api/drafts/{new_draft(base)}/messages", "POST",
                         {"text": "x", "files": []})  # fmt: skip
    assert status == 409 and "real model provider" in body


def test_a_limit_during_generation_keeps_the_message(claude_server, monkeypatch):
    base, _ = claude_server
    claude_generator(monkeypatch, [limit("rejected", "five_hour"), result("{}")])
    put(base, provider="claude")
    draft = new_draft(base)
    status, body = _call(base, f"/api/drafts/{draft}/messages", "POST",
                         {"text": "결제팀 실험", "files": []})  # fmt: skip
    assert status == 502 and "구독 한도" in body
    kept = json.loads(_call(base, f"/api/drafts/{draft}")[1])["messages"]
    assert kept[0]["text"] == "결제팀 실험" and "구독 한도" in kept[-1]["text"]


def test_a_claude_resume_through_the_server_defaults_to_the_claude_cap(claude_server,
                                                                      monkeypatch):  # fmt: skip
    base, httpd = claude_server
    paused_claude_run(httpd.runs_root, "local")
    seen = capture_launch(monkeypatch)  # after the run is made: it shells out to git
    status, _ = _call(base, "/api/runs/ui-x/s0_smoke/replicate-1/resume", "POST", {})
    argv = seen["argv"]
    assert argv[argv.index("--max-total-tokens") + 1] == "30000000"
