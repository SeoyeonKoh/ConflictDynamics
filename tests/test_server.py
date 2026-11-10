import json
import threading
import urllib.error
import urllib.request

import pytest

from conflict_sim.experiment import run_scenario
from conflict_sim.llm import LLMError
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


class FakeLLM:
    """Scripted JSON replies in order; an Exception in the script is raised."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        self.usage = {"decide": {"total_tokens": 0}}

    def complete(self, **request):
        self.requests.append(request)
        self.usage["decide"]["total_tokens"] += 10
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def router(next_step, reply=""):
    return json.dumps({"reply": reply, "next": next_step, "settings": {}})


def _fake_generator(monkeypatch, replies):
    from conflict_sim.server import Server

    llm = FakeLLM(replies)
    monkeypatch.setattr(Server, "generator_llm",
                        lambda server: (llm, server.settings()["model_decide"]))  # fmt: skip
    return llm


def _new_draft(base, mode="scratch", source=None):
    status, body = _call(base, "/api/drafts", "POST", {"mode": mode, "source": source})
    assert status == 200
    return json.loads(body)["id"]


def test_drafts_through_the_api(server, monkeypatch):
    base, _ = server
    llm = _fake_generator(monkeypatch, [router("ask", reply="무엇을 비교할까요?")])
    draft_id = _new_draft(base)
    status, body = _call(base, f"/api/drafts/{draft_id}/messages", "POST",
                         {"text": "실험하고 싶어", "files": []})  # fmt: skip
    assert status == 200 and json.loads(body)["messages"][-1]["role"] == "ai"
    assert llm.requests[0]["temperature"] == 0.4 and llm.requests[0]["json_mode"] is True
    assert llm.requests[0]["model"] == "gpt-6-luna"
    assert json.loads(_call(base, f"/api/drafts/{draft_id}")[1])["id"] == draft_id
    assert any(d["id"] == draft_id for d in json.loads(_call(base, "/api/drafts")[1]))


def test_draft_creation_and_lookup_errors(server):
    base, _ = server
    assert _call(base, "/api/drafts", "POST", {"mode": "variant", "source": "nope"})[0] == 404
    assert _call(base, "/api/drafts/d-20990101-0000-ffff")[0] == 404
    assert _call(base, "/api/drafts/d-20990101-0000-ffff/messages", "POST",
                 {"text": "x", "files": []})[0] == 404  # fmt: skip
    assert _call(base, "/api/drafts/d-20990101-0000-ffff/save", "POST", {})[0] == 404
    assert _call(base, "/api/drafts", "POST", {"mode": "bogus"})[0] == 400


def test_generation_is_refused_on_demo(server, monkeypatch):
    base, _ = server
    _fake_generator(monkeypatch, [])
    draft_id = _new_draft(base)
    settings = json.loads(_call(base, "/api/settings")[1])
    _call(base, "/api/settings", "PUT", settings | {"provider": "demo"})
    status, body = _call(base, f"/api/drafts/{draft_id}/messages", "POST",
                         {"text": "x", "files": []})  # fmt: skip
    assert status == 409 and "OpenAI provider" in json.loads(body)["error"]


def test_generation_is_refused_without_a_key(server, monkeypatch, tmp_path):
    base, _ = server
    _fake_generator(monkeypatch, [])
    draft_id = _new_draft(base)
    (tmp_path / ".env").write_text("")
    status, body = _call(base, f"/api/drafts/{draft_id}/messages", "POST",
                         {"text": "x", "files": []})  # fmt: skip
    assert status == 409 and "no OpenAI key" in json.loads(body)["error"]


def test_a_busy_draft_answers_409(server, monkeypatch):
    from conflict_sim.server import Server

    base, _ = server
    llm = FakeLLM([router("ask", reply="?")])
    draft_id = _new_draft(base)
    path, seen = f"/api/drafts/{draft_id}/messages", []

    def second_request_meets_the_lock(_server):
        seen.append(_call(base, path, "POST", {"text": "again", "files": []}))
        return llm, "m"

    monkeypatch.setattr(Server, "generator_llm", second_request_meets_the_lock)
    assert _call(base, path, "POST", {"text": "first", "files": []})[0] == 200
    assert seen[0][0] == 409 and json.loads(seen[0][1])["error"] == "the draft is busy"


def test_an_llm_failure_leaves_the_draft_as_it_was(server, monkeypatch):
    base, _ = server
    _fake_generator(monkeypatch, [LLMError("Run token budget reached; no further API calls")])
    draft_id = _new_draft(base)
    status, body = _call(base, f"/api/drafts/{draft_id}/messages", "POST",
                         {"text": "만들어줘", "files": []})  # fmt: skip
    assert status == 502 and "token budget" in json.loads(body)["error"]
    draft = json.loads(_call(base, f"/api/drafts/{draft_id}")[1])
    assert [m["role"] for m in draft["messages"]] == ["user", "check"]
    assert draft["messages"][-1]["text"].startswith("생성 실패: ")
    assert draft["versions"] == {"baseline": None, "variant": None}


def test_oversized_attachments_are_refused(server, monkeypatch):
    base, _ = server
    _fake_generator(monkeypatch, [])
    draft_id = _new_draft(base)
    path = f"/api/drafts/{draft_id}/messages"
    big = {"name": "a.txt", "text": "x" * 201_000}
    status, body = _call(base, path, "POST", {"text": "x", "files": [big]})
    assert status == 400
    assert json.loads(body)["error"] == "attachments are limited to 200 KB each, 1 MB in all"
    many = [{"name": f"{i}.txt", "text": "x" * 190_000} for i in range(6)]
    assert _call(base, path, "POST", {"text": "x", "files": many})[0] == 400
    assert _call(base, path, "POST", {"text": "x", "files": [{"name": 1}]})[0] == 400


def test_other_sites_cannot_generate(server):
    base, _ = server
    request = urllib.request.Request(
        base + "/api/drafts", data=b'{"mode": "scratch"}', method="POST",
        headers={"Content-Type": "application/json", "Origin": "http://evil.example"})  # fmt: skip
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(request)
    assert error.value.code == 403


def test_saving_a_draft_writes_into_the_conf_folder(server, monkeypatch, tmp_path):
    import shutil

    from conflict_sim import company, company_runtime, runs

    conf = tmp_path / "conf"
    shutil.copytree(company_runtime.CONF_DIR, conf)
    for module in (company, company_runtime):
        monkeypatch.setattr(module, "CONF_DIR", conf)
    runs._CATALOG.clear()
    base, _ = server
    assert _call(base, f"/api/drafts/{_new_draft(base)}/save", "POST", {})[0] == 409  # nothing yet
    draft_id = _new_draft(base, "variant", "r10_human")
    path = tmp_path / "drafts" / f"{draft_id}.json"
    draft = json.loads(path.read_text("utf-8"))
    draft["title"] = "api save"
    draft["versions"]["variant"] = draft["versions"]["baseline"]
    path.write_text(json.dumps(draft), "utf-8")
    status, body = _call(base, f"/api/drafts/{draft_id}/save", "POST", {})
    assert status == 200 and json.loads(body)["saved"] == ["gen_api_save_var"]
    assert list((conf / "scenario" / "company_c15").glob("gen_api_save_var*"))
    assert json.loads(_call(base, f"/api/drafts/{draft_id}")[1])["saved"] == ["gen_api_save_var"]


def test_a_body_that_is_not_an_object_is_a_400(server, monkeypatch):
    base, _ = server
    _fake_generator(monkeypatch, [])
    draft_id = _new_draft(base)
    for path in ["/api/drafts", f"/api/drafts/{draft_id}/messages", f"/api/drafts/{draft_id}/save"]:
        for body in ([1, 2], "text"):
            status, answer = _call(base, path, "POST", body)
            assert status == 400 and json.loads(answer)["error"] == "send a JSON object"


def test_saving_a_variant_draft_without_a_variant_is_a_409(server):
    base, _ = server
    draft_id = _new_draft(base, "variant", "r10_human")
    status, body = _call(base, f"/api/drafts/{draft_id}/save", "POST", {})
    assert status == 409 and json.loads(body)["error"] == "write the variant first"
