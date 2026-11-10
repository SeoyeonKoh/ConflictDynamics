"""`conflict-server`: the viewer's backend. Lists runs and scenarios, serves run journals and the
built viewer, keeps settings, and (live.py) starts and stops runs. Local use only: 127.0.0.1.

Spec: docs/superpowers/specs/2026-11-03-viz-main-menu-design.md, section 5.1.
"""

import argparse
import importlib.util
import json
import mimetypes
import re
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from . import company_runtime, generator, interview, live
from .experiment import all_scenarios
from .llm import LLMError, OpenAIBackend, create_openai_client, is_paid, make_claude_backend
from .runs import discover_company_runs, people, scenario_catalog, warm_catalog

DEFAULT_PORT = 8780
LOCAL = ("127.0.0.1", "localhost")
PROVIDERS = ("openai", "demo", "claude")
DEFAULTS = {
    "provider": "openai",
    "model_decide": "gpt-6-luna",
    "model_speak": "gpt-6-luna",
    "model_embed": "text-embedding-3-small",
    "max_total_tokens": 2_000_000,
    # The Claude subscription route (Agent SDK); its own models, embeddings and cap.
    "claude_model_decide": "claude-haiku-5-5",
    "claude_model_speak": "claude-haiku-5-5",
    "claude_embed": "local",
    "model_embed_local": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "claude_max_concurrent": 4,
    "claude_max_total_tokens": 30_000_000,  # a call costs ~11k tokens with the CLI's context
}
CLAUDE_INSTALL = "Install the Claude extra: uv sync --extra claude"
EMBED_INSTALL = "Install the local embedding extra: uv sync --extra embed"


def installed(module: str) -> bool:
    """Whether an optional package can be imported (tests replace this)."""
    return importlib.util.find_spec(module) is not None


def _env_has(env_file: Path, name: str) -> bool:
    if not env_file.is_file():
        return False
    return any(
        line.split("=", 1)[0].strip() == name and line.split("=", 1)[1].strip()
        for line in env_file.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )


def _claude_ready(settings: dict) -> None:
    """Refuse the Claude provider while its packages are missing (409 with the install line)."""
    if settings["provider"] != "claude":
        return
    if not installed("claude_agent_sdk"):
        raise HTTPError(409, f"the Claude Agent SDK is not installed. {CLAUDE_INSTALL}")
    if settings["claude_embed"] == "local" and not installed("fastembed"):
        raise HTTPError(409, f"the local embedding package is not installed. {EMBED_INSTALL}")
GENERATION_TOKEN_CAP = 300_000  # tokens one generator message may spend (shown by the screen)


class HTTPError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


Route = tuple[str, re.Pattern, Callable]


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port, *, runs_root, settings_path, static_root, env_file):
        super().__init__(("127.0.0.1", port), Handler)
        self.runs_root = runs_root.resolve()
        self.settings_path = settings_path
        self.static_root = static_root.resolve() if static_root else None
        self.env_file = env_file
        self.routes: list[Route] = []
        self.listeners: list[Callable[[list[dict]], None]] = []  # live.py marks running rows
        self.drafts = generator.Drafts(settings_path.parent / "drafts")

    def route(self, method: str, pattern: str):
        def add(handler):
            self.routes.append((method, re.compile(pattern + "$"), handler))
            return handler

        return add

    def run_dir(self, run: str) -> Path:
        path = (self.runs_root / unquote(run)).resolve()
        if not path.is_relative_to(self.runs_root) or not (path / "manifest.json").is_file():
            raise HTTPError(404, "no such run")
        return path

    def settings(self) -> dict:
        saved = {}
        if self.settings_path.is_file():
            saved = json.loads(self.settings_path.read_text(encoding="utf-8"))
        return DEFAULTS | {k: v for k, v in saved.items() if k in DEFAULTS}

    def generator_llm(self):
        """A fresh backend for one generator turn (its usage counter is that turn's tokens);
        tests replace this."""
        llm = OpenAIBackend(create_openai_client(self.env_file),
                            max_total_tokens=GENERATION_TOKEN_CAP,
                            reasoning_effort="none", max_tokens_decide=32_000,
                            max_input_chars=400_000)  # fmt: skip
        return llm, self.settings()["model_decide"]

    def has_openai_key(self) -> bool:
        return _env_has(self.env_file, "OPENAI_API_KEY")

    def claude_check_backend(self):
        """A backend for one login check call (tests replace this)."""
        return make_claude_backend(self.env_file, max_total_tokens=None, reasoning_effort="none",
                                   max_concurrent=1, timeout=60.0)  # fmt: skip


class Handler(BaseHTTPRequestHandler):
    server: Server

    def log_message(self, *_):  # quiet: the run logs are the record
        pass

    def do_GET(self):
        self._dispatch("GET")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_POST(self):
        self._dispatch("POST")

    def _guard(self, method: str, length: int):
        """Only this machine's pages may use the API: a Host that is not local is a rebound DNS
        name, an Origin that is not local is another site, and a body that is not JSON is a form
        or a fetch that skipped the browser's preflight. Each could start a paid run."""
        if (urlsplit(f"//{self.headers.get('Host', '')}").hostname or "") not in LOCAL:
            raise HTTPError(403, "not a local host")
        if method == "GET":
            return
        origin = self.headers.get("Origin")
        if origin is not None and (urlsplit(origin).hostname or "") not in LOCAL:
            raise HTTPError(403, "not a local page")
        kind = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        if length and kind != "application/json":
            raise HTTPError(415, "send JSON")

    def _dispatch(self, method: str):
        path = urlsplit(self.path).path
        try:
            length = int(self.headers.get("Content-Length") or 0)
            self._guard(method, length)
            body = json.loads(self.rfile.read(length) or b"null") if length else None
            if method == "GET":  # a GET's query is its body
                body = dict(parse_qsl(urlsplit(self.path).query))
            for verb, pattern, handler in self.server.routes:
                if verb == method and (match := pattern.match(path)):
                    return self._send(200, handler(self.server, match, body))
            if method == "GET":
                return self._static(path)
            raise HTTPError(404, "not found")
        except HTTPError as error:
            self._send(error.status, {"error": str(error)})
        except (ValueError, TypeError, KeyError) as error:
            self._send(400, {"error": str(error)})
        except Exception as error:  # noqa: BLE001 - one bad request must not drop the connection
            self._send(500, {"error": f"{type(error).__name__}: {error}"})

    def _send(self, status: int, payload, content_type: str = "application/json"):
        if isinstance(payload, bytes):
            data = payload
        elif isinstance(payload, str):
            data, content_type = payload.encode(), "text/plain; charset=utf-8"
        else:
            data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _static(self, path: str):
        root = self.server.static_root
        if root is None:
            raise HTTPError(404, "viewer not built")
        target = (root / unquote(path).lstrip("/")).resolve()
        if target.is_dir():
            target = target / "index.html"
        if not target.is_relative_to(root) or not target.is_file():
            raise HTTPError(404, "not found")
        kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self._send(200, target.read_bytes(), kind)


def _runs(server: Server, _match, _body):
    found = server.runs_root.is_dir()
    rows, broken = discover_company_runs(server.runs_root) if found else ([], [])
    for listener in server.listeners:
        listener(rows)
    return {"runs": rows, "broken": broken}


def _journals(server: Server, _match, _body):
    if not server.runs_root.is_dir():
        return []
    return sorted(str(p.parent.relative_to(server.runs_root))
                  for p in server.runs_root.rglob("frames.jsonl"))  # fmt: skip


def _journal(server: Server, match, _body):
    path = (server.runs_root / unquote(match["path"])).resolve()
    if not path.is_relative_to(server.runs_root) or path.suffix != ".jsonl" or not path.is_file():
        raise HTTPError(404, "not found")
    return path.read_text(encoding="utf-8")


def _people(server: Server, match, _body):
    return people(server.run_dir(match["run"]))


def _scenarios(server: Server, _match, _body):
    return scenario_catalog(server.runs_root)


def _get_settings(server: Server, _match, _body):
    settings = server.settings()
    run = _run_models(settings)
    return settings | {
        "openai_key": server.has_openai_key(),
        "generation_token_cap": GENERATION_TOKEN_CAP,
        "claude_sdk": installed("claude_agent_sdk"),
        "local_embed": installed("fastembed"),
        # A token in .env is a known login; the CLI's own stored login cannot be seen here.
        "claude_login": True if _env_has(server.env_file, "CLAUDE_CODE_OAUTH_TOKEN") else None,
        "paid": is_paid(settings["provider"], run.get("embed_backend")),
    }


def _claude_check(server: Server, _match, _body):
    """One short call on the subscription: whether the CLI is logged in. Only on request."""
    if not installed("claude_agent_sdk"):
        raise HTTPError(409, f"the Claude Agent SDK is not installed. {CLAUDE_INSTALL}")
    backend = server.claude_check_backend()
    try:
        backend.complete(system="Reply with OK.", prompt="OK?",
                         model=server.settings()["claude_model_speak"], temperature=0,
                         json_mode=False)  # fmt: skip
    except LLMError as error:
        return {"ok": False, "auth": None, "error": str(error)}
    return {"ok": True, "auth": backend.auth, "error": None}


def _put_settings(server: Server, _match, body):
    if not isinstance(body, dict):
        raise HTTPError(400, "settings must be an object")
    new = server.settings() | {k: v for k, v in body.items() if k in DEFAULTS}
    if new["provider"] not in PROVIDERS:
        raise HTTPError(400, f"provider must be one of {', '.join(PROVIDERS)}")
    cap = new["max_total_tokens"]
    if cap is not None and (type(cap) is not int or cap < 1):
        raise HTTPError(400, "max_total_tokens must be a positive integer or null")
    models = [k for k in DEFAULTS if k.startswith(("model_", "claude_model_"))]
    if not all(isinstance(new[k], str) and new[k] for k in models):
        raise HTTPError(400, "models must be non-empty strings")
    if new["claude_embed"] not in ("local", "openai"):
        raise HTTPError(400, "claude_embed must be local or openai")
    workers = new["claude_max_concurrent"]
    if type(workers) is not int or not 1 <= workers <= 16:
        raise HTTPError(400, "claude_max_concurrent must be an integer from 1 to 16")
    claude_cap = new["claude_max_total_tokens"]
    if claude_cap is not None and (type(claude_cap) is not int or claude_cap < 1):
        raise HTTPError(400, "claude_max_total_tokens must be a positive integer or null")
    _claude_ready(new)
    server.settings_path.parent.mkdir(parents=True, exist_ok=True)
    server.settings_path.write_text(json.dumps(new, indent=2), encoding="utf-8")
    return _get_settings(server, None, None)


def _run_models(settings: dict) -> dict:
    """The models (and, for Claude, embeddings and processes) a run started now would use."""
    if settings["provider"] != "claude":
        return {k: settings[k] for k in ("model_decide", "model_speak", "model_embed")}
    local = settings["claude_embed"] == "local"
    return {"model_decide": settings["claude_model_decide"],
            "model_speak": settings["claude_model_speak"],
            "model_embed": settings["model_embed_local"] if local else settings["model_embed"],
            "embed_backend": settings["claude_embed"],
            "claude_max_concurrent": settings["claude_max_concurrent"]}  # fmt: skip


def _guarded(call):
    """The live module's refusals as HTTP answers."""
    try:
        return call()
    except PermissionError as error:
        raise HTTPError(403, str(error)) from error
    except ValueError as error:
        raise HTTPError(409, str(error)) from error


def _start(server: Server, _match, body):
    body = body or {}
    settings = server.settings()
    _claude_ready(settings)
    cap_key = "claude_max_total_tokens" if settings["provider"] == "claude" else "max_total_tokens"
    cap = body.get("max_total_tokens", settings[cap_key])
    return _guarded(lambda: live.start(
        server.runs_root, scenario=str(body["scenario"]), days=int(body.get("days", 1)),
        max_total_tokens=cap, backend=settings["provider"], models=_run_models(settings),
        paid_confirmed=bool(body.get("paid_confirmed")), tick_delay=body.get("tick_delay"),
    ))  # fmt: skip


def _resume(server: Server, match, body):
    body = body or {}
    server.run_dir(match["run"])
    cap = body.get("max_total_tokens", server.settings()["max_total_tokens"])
    return _guarded(lambda: live.resume(
        server.runs_root, unquote(match["run"]), max_total_tokens=cap,
        paid_confirmed=bool(body.get("paid_confirmed")), tick_delay=body.get("tick_delay"),
    ))  # fmt: skip


def _stop(server: Server, match, _body):
    _guarded(lambda: live.stop(server.runs_root, unquote(match["id"])))
    return {"stopping": match["id"]}


def _interview_run(server: Server, match) -> Path:
    run_dir = server.run_dir(match["run"])
    replaying = any(a["run"] == str(run_dir.relative_to(server.runs_root)) and
                    a["status"] == "replaying" for a in live.active(server.runs_root))  # fmt: skip
    if (run_dir / ".before-replay").exists() or replaying:
        raise HTTPError(409, "the run is being rebuilt from its record; ask again when it is done")
    return run_dir


def _interviewed(call):
    try:
        return call()
    except KeyError as error:
        raise HTTPError(404, f"not found: {error}") from error
    except ValueError as error:
        raise HTTPError(400 if "empty" in str(error) else 409, str(error)) from error


def _interviews(server: Server, match, body):
    run_dir = server.run_dir(match["run"])
    return interview.listing(run_dir, (body or {}).get("agent"))


def _interview(server: Server, match, _body):
    return _interviewed(lambda: interview.load(server.run_dir(match["run"]), unquote(match["id"])))


def _interview_start(server: Server, match, body):
    run_dir, settings = _interview_run(server, match), server.settings()
    body = body or {}
    return _interviewed(lambda: interview.start(
        run_dir, str(body.get("agent")), int(body.get("tick", 0)), settings["provider"],
        settings["model_speak"] if settings["provider"] == "openai" else "demo"))  # fmt: skip


def _interview_ask(server: Server, match, body):
    run_dir, settings = _interview_run(server, match), server.settings()
    if settings["provider"] == "openai":
        if not server.has_openai_key():
            raise HTTPError(409, "no OpenAI key in the server's .env")
        llm = OpenAIBackend(create_openai_client(server.env_file), max_total_tokens=None,
                            reasoning_effort=interview.run_reasoning_effort(run_dir))  # fmt: skip
        model = settings["model_speak"]
    else:
        llm, model = interview.DemoInterviewer(), "demo"
    question = str((body or {}).get("question", ""))
    return _interviewed(lambda: interview.ask(
        run_dir, unquote(match["id"]), question, llm, model,
        interview.question_embedder(interview.run_backend(run_dir), settings["provider"],
                                    server.env_file, run_dir)))  # fmt: skip


def _draft(server: Server, match) -> dict:
    try:
        return server.drafts.load(match["id"])
    except KeyError as error:
        raise HTTPError(404, "no such draft") from error


def _object(body) -> dict:
    if body is not None and not isinstance(body, dict):
        raise HTTPError(400, "send a JSON object")
    return body or {}


def _create_draft(server: Server, _match, body):
    body = _object(body)
    source = body.get("source") or None
    if source is not None and source not in all_scenarios():
        raise HTTPError(404, "no such scenario")
    return generator.view(server.drafts.create(body.get("mode"), source))


def _attachments(body: dict) -> list[dict]:
    files = body.get("files") or []
    if not isinstance(files, list) or not all(
        isinstance(f, dict) and isinstance(f.get("name"), str) and isinstance(f.get("text"), str)
        for f in files
    ):
        raise HTTPError(400, "files must be a list of {name, text}")
    sizes = [len(f["text"].encode("utf-8")) for f in files]
    if any(size > 200_000 for size in sizes) or sum(sizes) > 1_000_000:
        raise HTTPError(400, "attachments are limited to 200 KB each, 1 MB in all")
    return [{"name": f["name"], "text": f["text"]} for f in files]


def _backend_failure(error: Exception) -> bool:
    return isinstance(error, LLMError) or type(error).__module__.split(".")[0] == "openai"


def _draft_message(server: Server, match, body):
    body = _object(body)
    draft_id, text = match["id"], str(body.get("text", ""))
    if server.settings()["provider"] != "openai":
        raise HTTPError(409, "scenario generation needs the OpenAI provider")
    if not server.has_openai_key():
        raise HTTPError(409, "no OpenAI key in the server's .env")
    files = _attachments(body)
    try:
        with server.drafts.busy(draft_id):
            draft = _draft(server, match)
            llm, model = server.generator_llm()
            try:
                draft = generator.turn(draft, text, files, llm, model)
            except Exception as error:  # noqa: BLE001 - only the backend's failures end a turn
                if not _backend_failure(error):
                    raise
                draft = generator.failed(draft, text, files, error, llm)
                server.drafts.write(draft)
                raise HTTPError(502, str(error)) from error
            server.drafts.write(draft)
            return generator.view(draft)
    except generator.DraftBusy as error:
        raise HTTPError(409, "the draft is busy") from error


def _draft_save(server: Server, match, body):
    accept = bool(_object(body).get("accept_outside"))
    try:
        with server.drafts.busy(match["id"]):
            draft = generator.save(_draft(server, match), company_runtime.CONF_DIR,
                                   accept_outside=accept)  # fmt: skip
            server.drafts.write(draft)
    except generator.DraftBusy as error:
        raise HTTPError(409, "the draft is busy") from error
    except generator.SaveRefused as error:
        raise HTTPError(409, str(error)) from error
    return generator.view(draft)


def make_server(
    *,
    runs_root: Path,
    settings_path: Path,
    static_root: Path | None,
    env_file: Path = Path(".env"),
    port: int = 0,
) -> Server:
    server = Server(port, runs_root=runs_root, settings_path=settings_path,
                    static_root=static_root, env_file=env_file)  # fmt: skip
    # The scenario catalog takes over a second to build the first time: build it now, not when
    # someone first opens the live dialog.
    threading.Thread(target=warm_catalog, daemon=True, name="catalog-warmup").start()
    server.route("GET", r"/api/runs")(_runs)
    server.route("GET", r"/api/runs/(?P<run>.+?)/interviews")(_interviews)
    server.route("POST", r"/api/runs/(?P<run>.+?)/interviews")(_interview_start)
    server.route("GET", r"/api/runs/(?P<run>.+?)/interviews/(?P<id>[^/]+)")(_interview)
    server.route("POST", r"/api/runs/(?P<run>.+?)/interviews/(?P<id>[^/]+)/ask")(_interview_ask)
    server.route("GET", r"/api/runs/(?P<run>.+)/people")(_people)
    server.route("GET", r"/runs")(_journals)
    server.route("GET", r"/runs/(?P<path>.+)")(_journal)
    server.route("GET", r"/api/scenarios")(_scenarios)
    server.route("GET", r"/api/settings")(_get_settings)
    server.route("PUT", r"/api/settings")(_put_settings)
    server.route("POST", r"/api/settings/claude-check")(_claude_check)
    server.route("POST", r"/api/live")(_start)
    server.route("GET", r"/api/live")(lambda s, _m, _b: live.active(s.runs_root))
    server.route("POST", r"/api/live/(?P<id>[^/]+)/stop")(_stop)
    server.route("POST", r"/api/runs/(?P<run>.+)/resume")(_resume)
    server.route("GET", r"/api/drafts")(lambda s, _m, _b: s.drafts.listing())
    server.route("POST", r"/api/drafts")(_create_draft)
    server.route("GET", r"/api/drafts/(?P<id>[^/]+)")(lambda s, m, _b: generator.view(_draft(s, m)))
    server.route("POST", r"/api/drafts/(?P<id>[^/]+)/messages")(_draft_message)
    server.route("POST", r"/api/drafts/(?P<id>[^/]+)/save")(_draft_save)
    server.listeners.append(lambda rows: live.mark(server.runs_root, rows))
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Conflict Dynamics viewer and its API")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--runs", type=Path, default=Path("runs"))
    parser.add_argument("--static", type=Path, default=Path("viz/dist"))
    args = parser.parse_args()
    server = make_server(
        runs_root=args.runs,
        settings_path=Path(".conflict-sim/settings.json"),
        static_root=args.static if args.static.is_dir() else None,
        port=args.port,
    )
    print(f"Conflict Dynamics: http://127.0.0.1:{server.server_address[1]}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
