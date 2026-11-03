"""`conflict-server`: the viewer's backend. Lists runs and scenarios, serves run journals and the
built viewer, keeps settings, and (live.py) starts and stops runs. Local use only: 127.0.0.1.

Spec: docs/superpowers/specs/2026-11-03-viz-main-menu-design.md, section 5.1.
"""

import argparse
import json
import mimetypes
import re
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import live
from .runs import discover_company_runs, people, scenario_catalog

DEFAULT_PORT = 8780
LOCAL = ("127.0.0.1", "localhost")
PROVIDERS = ("openai", "demo")
DEFAULTS = {
    "provider": "openai",
    "model_decide": "gpt-6-luna",
    "model_speak": "gpt-6-luna",
    "model_embed": "text-embedding-3-small",
    "max_total_tokens": 2_000_000,
}


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

    def has_openai_key(self) -> bool:
        if not self.env_file.is_file():
            return False
        return any(
            line.split("=", 1)[0].strip() == "OPENAI_API_KEY" and line.split("=", 1)[1].strip()
            for line in self.env_file.read_text(encoding="utf-8").splitlines()
            if "=" in line
        )


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
    return server.settings() | {"openai_key": server.has_openai_key()}


def _put_settings(server: Server, _match, body):
    if not isinstance(body, dict):
        raise HTTPError(400, "settings must be an object")
    new = server.settings() | {k: v for k, v in body.items() if k in DEFAULTS}
    if new["provider"] not in PROVIDERS:
        raise HTTPError(400, f"provider must be one of {', '.join(PROVIDERS)}")
    cap = new["max_total_tokens"]
    if cap is not None and (type(cap) is not int or cap < 1):
        raise HTTPError(400, "max_total_tokens must be a positive integer or null")
    if not all(isinstance(new[k], str) and new[k] for k in DEFAULTS if k.startswith("model_")):
        raise HTTPError(400, "models must be non-empty strings")
    server.settings_path.parent.mkdir(parents=True, exist_ok=True)
    server.settings_path.write_text(json.dumps(new, indent=2), encoding="utf-8")
    return _get_settings(server, None, None)


def _models(settings: dict) -> dict:
    return {k: settings[k] for k in ("model_decide", "model_speak", "model_embed")}


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
    cap = body.get("max_total_tokens", settings["max_total_tokens"])
    return _guarded(lambda: live.start(
        server.runs_root, scenario=str(body["scenario"]), days=int(body.get("days", 1)),
        max_total_tokens=cap, backend=settings["provider"], models=_models(settings),
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
    server.route("GET", r"/api/runs")(_runs)
    server.route("GET", r"/api/runs/(?P<run>.+)/people")(_people)
    server.route("GET", r"/runs")(_journals)
    server.route("GET", r"/runs/(?P<path>.+)")(_journal)
    server.route("GET", r"/api/scenarios")(_scenarios)
    server.route("GET", r"/api/settings")(_get_settings)
    server.route("PUT", r"/api/settings")(_put_settings)
    server.route("POST", r"/api/live")(_start)
    server.route("GET", r"/api/live")(lambda s, _m, _b: live.active(s.runs_root))
    server.route("POST", r"/api/live/(?P<id>[^/]+)/stop")(_stop)
    server.route("POST", r"/api/runs/(?P<run>.+)/resume")(_resume)
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
