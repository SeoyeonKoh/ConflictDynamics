import json
import threading
import urllib.error
import urllib.request

import pytest

from conflict_sim.experiment import run_scenario
from conflict_sim.runs import discover_company_runs, people, scenario_catalog
from conflict_sim.server import make_server


@pytest.fixture
def server(tmp_path):
    runs = tmp_path / "runs"
    run_scenario("s0_smoke", runs / "one" / "s0_smoke" / "replicate-1")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-secret-value\n")
    static = tmp_path / "dist"
    static.mkdir()
    (static / "index.html").write_text("<p>menu</p>")
    httpd = make_server(runs_root=runs, settings_path=tmp_path / "settings.json",
                        static_root=static, env_file=tmp_path / ".env", port=0)  # fmt: skip
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", runs
    httpd.shutdown()


def _call(base, path, method="GET", body=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {} if body is None else {"Content-Type": "application/json"}
    request = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def test_run_files_cannot_escape_the_runs_folder(server):
    base, _ = server
    for path in ["/runs/../pyproject.toml", "/runs/%2e%2e/.env", "/runs/one/manifest.json",
                 "/runs/one/s0_smoke/replicate-1/nothing.jsonl"]:  # fmt: skip
        assert _call(base, path)[0] == 404


def test_run_listing_files_people_and_scenarios(server):
    base, runs = server
    status, body = _call(base, "/api/runs")
    assert status == 200
    expected, _ = discover_company_runs(runs)
    assert [r["run"] for r in json.loads(body)["runs"]] == [r["run"] for r in expected]
    run = expected[0]["run"]
    status, body = _call(base, f"/runs/{run}/frames.jsonl")
    assert status == 200 and body.startswith('{"type": "hello"')
    assert json.loads(_call(base, "/runs")[1]) == [run]
    assert json.loads(_call(base, f"/api/runs/{run}/people")[1]) == people(runs / run)
    names = [s["name"] for s in json.loads(_call(base, "/api/scenarios")[1])]
    assert names == [s["name"] for s in scenario_catalog(runs)]


def test_settings_round_trip_and_never_show_the_key(server):
    base, _ = server
    got = json.loads(_call(base, "/api/settings")[1])
    assert got["provider"] == "openai" and got["openai_key"] is True
    assert got["max_total_tokens"] == 2_000_000 and got["model_decide"] == "gpt-6-luna"
    status, _ = _call(base, "/api/settings", "PUT", got | {"provider": "demo",
                                                          "max_total_tokens": None})  # fmt: skip
    assert status == 200
    got = json.loads(_call(base, "/api/settings")[1])
    assert got["provider"] == "demo" and got["max_total_tokens"] is None
    assert "sk-secret" not in json.dumps(got)
    assert _call(base, "/api/settings", "PUT", got | {"provider": "anthropic"})[0] == 400


def test_other_paths_are_the_built_viewer(server):
    base, _ = server
    assert _call(base, "/") == (200, "<p>menu</p>")
    assert _call(base, "/index.html") == (200, "<p>menu</p>")
    assert _call(base, "/../secret")[0] == 404


def test_live_runs_through_the_api(server, monkeypatch):
    import time

    base, runs = server
    _call(base, "/api/settings", "PUT", {"provider": "demo"})
    body = {"scenario": "s0_smoke", "days": 1, "max_total_tokens": None, "tick_delay": 0.05}
    status, text = _call(base, "/api/live", "POST", body)
    assert status == 200
    started = json.loads(text)
    assert [a["id"] for a in json.loads(_call(base, "/api/live")[1])] == [started["id"]]
    row = next(r for r in json.loads(_call(base, "/api/runs")[1])["runs"]
               if r["run"] == started["run"])  # fmt: skip
    assert row["live"]["id"] == started["id"]
    assert _call(base, f"/api/live/{started['id']}/stop", "POST", {})[0] == 200
    for _ in range(200):
        if not json.loads(_call(base, "/api/live")[1]):
            break
        time.sleep(0.05)
    assert _call(base, "/api/runs/one/s0_smoke/replicate-1/resume", "POST",
                 {"max_total_tokens": None})[0] == 409  # fmt: skip
    _call(base, "/api/settings", "PUT", {"provider": "openai"})
    assert _call(base, "/api/live", "POST", body)[0] == 403


def test_an_unexpected_error_is_a_500_not_a_dropped_connection(tmp_path):
    httpd = make_server(runs_root=tmp_path, settings_path=tmp_path / "s.json", static_root=None,
                        env_file=tmp_path / ".env")  # fmt: skip

    def boom(*_):
        raise RuntimeError("boom")

    httpd.route("GET", r"/api/boom")(boom)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        assert _call(f"http://127.0.0.1:{httpd.server_address[1]}", "/api/boom")[0] == 500
    finally:
        httpd.shutdown()


def test_other_sites_cannot_start_or_change_anything(server):
    base, _ = server
    body = json.dumps({"provider": "demo"}).encode()

    def send(headers):
        request = urllib.request.Request(base + "/api/settings", data=body, method="PUT",
                                         headers=headers)  # fmt: skip
        try:
            with urllib.request.urlopen(request) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code

    json_type = {"Content-Type": "application/json"}
    assert send({"Content-Type": "text/plain"}) == 415  # a form or no-preflight fetch
    assert send(json_type | {"Origin": "https://evil.example"}) == 403
    assert send(json_type | {"Host": "evil.example:8780"}) == 403  # DNS rebinding
    assert send(json_type | {"Origin": "http://localhost:5173"}) == 200  # the dev viewer


def test_an_interview_through_the_api(server):
    base, runs = server
    _call(base, "/api/settings", "PUT", {"provider": "demo"})
    run = "one/s0_smoke/replicate-1"
    body = {"agent": "HDS-001", "tick": 5}
    status, text = _call(base, f"/api/runs/{run}/interviews", "POST", body)
    assert status == 200
    iv = json.loads(text)
    assert iv["summary"]["name"]
    ask = f"/api/runs/{run}/interviews/{iv['id']}/ask"
    status, text = _call(base, ask, "POST", {"question": "안녕하세요?"})
    assert status == 200 and json.loads(text)["a"]
    listed = json.loads(_call(base, f"/api/runs/{run}/interviews?agent=HDS-001")[1])
    assert listed[0]["questions"] == 1
    assert json.loads(_call(base, f"/api/runs/{run}/interviews/{iv['id']}")[1])["turns"]
    assert _call(base, ask, "POST", {"question": " "})[0] == 400
    assert _call(base, f"/api/runs/{run}/interviews", "POST",
                 {"agent": "NOBODY", "tick": 1})[0] == 404  # fmt: skip
    assert _call(base, f"/api/runs/{run}/interviews/..%2Fmanifest")[0] == 404
    (runs / run / ".before-replay").mkdir()
    assert _call(base, ask, "POST", {"question": "?"})[0] == 409


def test_an_openai_interview_without_a_key_is_refused(server):
    base, runs = server
    (runs.parent / ".env").write_text("OTHER=1\n")
    run = "one/s0_smoke/replicate-1"
    iv = json.loads(_call(base, f"/api/runs/{run}/interviews", "POST",
                          {"agent": "HDS-001", "tick": 5})[1])  # fmt: skip
    status, _ = _call(base, f"/api/runs/{run}/interviews/{iv['id']}/ask", "POST", {"question": "?"})
    assert status == 409


def test_an_openai_interview_asks_the_way_the_run_did(server, monkeypatch):
    """gpt-6 models take a temperature only with reasoning turned off; the engine sends
    reasoning_effort with every call and the interview must too (it got HTTP 400)."""
    from types import SimpleNamespace

    from conflict_sim import server as server_module

    base, runs = server
    (runs.parent / ".env").write_text("OPENAI_API_KEY=sk-test\n")
    sent = []

    def create(**kwargs):
        sent.append(kwargs)
        message = SimpleNamespace(content="네, 기억나요.", refusal=None)
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15,
                                prompt_tokens_details=None, completion_tokens_details=None,
                                model_dump=lambda: {"total_tokens": 15})
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")],
                               usage=usage, model=kwargs["model"])  # fmt: skip

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(server_module, "create_openai_client", lambda env_file: client)
    run = "one/s0_smoke/replicate-1"
    iv = json.loads(_call(base, f"/api/runs/{run}/interviews", "POST",
                          {"agent": "HDS-001", "tick": 5})[1])  # fmt: skip
    status, text = _call(base, f"/api/runs/{run}/interviews/{iv['id']}/ask", "POST",
                         {"question": "그때 왜 쉬었어요?"})  # fmt: skip
    assert status == 200, text
    assert sent and "temperature" in sent[0]
    assert sent[0].get("reasoning_effort") == "none"
