"""A private, local browser app for Quill.

Runs on 127.0.0.1 only. Every API call must carry a per-launch token that is embedded
in the page, so other websites open in your browser can't talk to it.
"""

from __future__ import annotations

import json
import secrets
import socket
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import parse_qs, urlparse

import anthropic

from quill import __version__, prompts, tells
from quill.store import Workspace, slugify

MAX_BODY = 5 * 1024 * 1024
TOOL_LABELS = {
    "read_voice_profile": "Reading your voice profile",
    "update_voice_profile": "Updating your voice profile",
    "update_about_me": "Updating your About me",
    "list_drafts": "Looking at your drafts",
    "read_draft": "Reading a draft",
    "save_draft": "Saving a draft",
    "list_samples": "Looking at your samples",
    "read_sample": "Reading a sample",
    "read_notes": "Reading your notes",
    "append_note": "Adding to your notes",
    "check_writing": "Checking for AI tells",
}


def friendly_error(e: Exception) -> str:
    if isinstance(e, anthropic.AuthenticationError):
        return "Your API key was rejected. Update it in Settings."
    if isinstance(e, anthropic.PermissionDeniedError):
        return "Your API key doesn't have access to this model. Try another model in Settings."
    if isinstance(e, anthropic.RateLimitError):
        return "The API is rate-limiting you right now. Wait a moment and try again."
    if isinstance(e, anthropic.APIConnectionError):
        return "Couldn't reach the Claude API. Check your internet connection."
    if isinstance(e, anthropic.APIStatusError):
        return f"The Claude API returned an error ({e.status_code}): {e.message}"
    if isinstance(e, RuntimeError):
        return str(e)
    return f"Something went wrong: {e}"


class QuillApp:
    """Shared state for the server: one workspace, one conversation at a time."""

    def __init__(self, ws: Workspace, model: str | None = None, effort: str | None = None):
        self.ws = ws
        self.model = model
        self.effort = effort
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self._agent = None

    def agent(self):
        from quill.agent import WritingAgent

        if self._agent is None:
            self._agent = WritingAgent(self.ws, model=self.model, effort=self.effort)
        return self._agent

    def reset_agent(self) -> None:
        self._agent = None

    def state(self) -> dict:
        import os

        config = self.ws.load_config()
        from quill.agent import DEFAULT_MODEL

        key_source = (
            "env" if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            else "saved" if config.get("api_key") else None
        )
        return {
            "version": __version__,
            "name": config.get("name", ""),
            "needs_setup": self.ws.needs_setup(),
            "key_source": key_source,
            "model": self.model or config.get("model") or DEFAULT_MODEL,
            "effort": self.effort or config.get("effort") or "high",
            "drafts": self.ws.list_drafts(),
            "samples": self.ws.list_samples(),
            "voice": self.ws.read_voice(),
            "about": self.ws.read_about(),
            "notes": self.ws.read_notes(),
            "workspace": str(self.ws.root),
        }


def make_handler(app: QuillApp, port: int):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        server_version = f"Quill/{__version__}"

        def log_message(self, *args):  # keep the terminal quiet
            pass

        # --- helpers ----------------------------------------------------------
        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data, status: int = 200) -> None:
            self._send(status, json.dumps(data).encode(), "application/json")

        def _error(self, status: int, message: str) -> None:
            self._json({"error": message}, status)

        def _authorized(self, api: bool) -> bool:
            if self.headers.get("Host") not in allowed_hosts:
                self._error(HTTPStatus.FORBIDDEN, "Bad host.")
                return False
            if api and not secrets.compare_digest(self.headers.get("X-Quill-Token", ""), app.token):
                self._error(HTTPStatus.FORBIDDEN, "Bad token. Reload the page.")
                return False
            return True

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise ValueError("Request too large.")
            data = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object.")
            return data

        # --- routes -----------------------------------------------------------
        def do_GET(self):
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                if not self._authorized(api=False):
                    return
                page = resources.files("quill").joinpath("static/index.html").read_text(encoding="utf-8")
                self._send(200, page.replace("__QUILL_TOKEN__", app.token).encode(), "text/html; charset=utf-8")
                return
            if not url.path.startswith("/api/"):
                self._error(HTTPStatus.NOT_FOUND, "Not found.")
                return
            if not self._authorized(api=True):
                return
            try:
                if url.path == "/api/state":
                    self._json(app.state())
                elif url.path == "/api/draft":
                    name = parse_qs(url.query).get("name", [""])[0]
                    self._json({"name": slugify(name), "content": app.ws.read_draft(name),
                                "versions": app.ws.list_versions(name)})
                elif url.path == "/api/version":
                    q = parse_qs(url.query)
                    name, v = q.get("name", [""])[0], q.get("v", ["0"])[0]
                    if not v.isdigit():
                        self._error(HTTPStatus.BAD_REQUEST, "Bad version.")
                        return
                    self._json({"name": slugify(name), "version": int(v), "content": app.ws.read_version(name, int(v))})
                else:
                    self._error(HTTPStatus.NOT_FOUND, "Not found.")
            except FileNotFoundError as e:
                self._error(HTTPStatus.NOT_FOUND, str(e))

        def do_POST(self):
            url = urlparse(self.path)
            if not self._authorized(api=True):
                return
            try:
                data = self._body()
            except (ValueError, json.JSONDecodeError) as e:
                self._error(HTTPStatus.BAD_REQUEST, str(e))
                return
            ws = app.ws

            if url.path == "/api/chat":
                self._chat(str(data.get("message", "")).strip())
                return
            if url.path == "/api/setup":
                allowed = {"name", "api_key", "model", "effort"}
                updates = {k: str(v).strip() for k, v in data.items() if k in allowed and v is not None}
                if updates.get("effort") and updates["effort"] not in ("low", "medium", "high", "xhigh", "max"):
                    self._error(HTTPStatus.BAD_REQUEST, "Unknown effort level.")
                    return
                # An empty api_key in the form means "keep the saved one".
                if not updates.get("api_key"):
                    updates.pop("api_key", None)
                ws.save_config(updates)
                if isinstance(data.get("about"), str) and data["about"].strip():
                    ws.write_about(data["about"])
                if updates.get("model"):
                    app.model = None
                if updates.get("effort"):
                    app.effort = None
                with app.lock:
                    app.reset_agent()
                self._json(app.state())
            elif url.path == "/api/new":
                with app.lock:
                    app.reset_agent()
                self._json({"ok": True})
            elif url.path == "/api/draft":
                name, content = str(data.get("name", "")), str(data.get("content", ""))
                if not name.strip():
                    self._error(HTTPStatus.BAD_REQUEST, "A draft needs a name.")
                    return
                path = ws.save_draft(name, content)
                self._json({"name": path.stem})
            elif url.path == "/api/draft/delete":
                try:
                    ws.delete_draft(str(data.get("name", "")))
                except FileNotFoundError as e:
                    self._error(HTTPStatus.NOT_FOUND, str(e))
                    return
                self._json({"ok": True})
            elif url.path == "/api/check":
                samples = "\n\n".join(t for _, t in ws.samples_for_prompt(max_words=20000))
                self._json(tells.analyze(str(data.get("text", "")), samples))
            elif url.path == "/api/rewrite":
                self._rewrite(data)
            elif url.path in ("/api/voice", "/api/about"):
                content = str(data.get("content", ""))
                (ws.write_voice if url.path == "/api/voice" else ws.write_about)(content)
                with app.lock:
                    app.reset_agent()  # pick up the edited profile in a fresh conversation
                self._json({"ok": True})
            elif url.path == "/api/sample":
                name, text = str(data.get("name", "")).strip() or "sample", str(data.get("text", ""))
                if len(text.split()) < 20:
                    self._error(HTTPStatus.BAD_REQUEST, "Paste at least a few paragraphs so Quill has something to learn from.")
                    return
                saved = ws.add_sample_text(name, text).stem
                self._json({"name": saved, "prompt": prompts.LEARN_TASK.format(names=saved)})
            else:
                self._error(HTTPStatus.NOT_FOUND, "Not found.")

        def _rewrite(self, data: dict) -> None:
            import quill.agent as agent_mod

            passage = str(data.get("passage", ""))
            if not passage.strip():
                self._error(HTTPStatus.BAD_REQUEST, "Select some text to rewrite first.")
                return
            try:
                text = agent_mod.rewrite_passage(
                    app.ws, agent_mod.make_client(app.ws), passage=passage,
                    instruction=str(data.get("instruction", "human")),
                    before=str(data.get("before", "")), after=str(data.get("after", "")),
                    model=app.model, effort=app.effort,
                )
            except Exception as e:  # report to the page instead of dying
                self._error(HTTPStatus.BAD_GATEWAY, friendly_error(e))
                return
            samples = "\n\n".join(t for _, t in app.ws.samples_for_prompt(max_words=20000))
            self._json({"text": text, "check": tells.analyze(text, samples)})

        def _chat(self, message: str) -> None:
            if not message:
                self._error(HTTPStatus.BAD_REQUEST, "Empty message.")
                return
            if not app.lock.acquire(blocking=False):
                self._error(HTTPStatus.CONFLICT, "Quill is still working on your last message.")
                return
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Accel-Buffering", "no")
                self.end_headers()

                def emit(event: dict) -> None:
                    self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
                    self.wfile.flush()

                try:
                    agent = app.agent()
                    agent.out = lambda text: emit({"type": "text", "text": text})
                    agent.on_tool = lambda name: emit({"type": "tool", "name": name,
                                                       "label": TOOL_LABELS.get(name, name)})
                    agent.send(message)
                    emit({"type": "done"})
                except (BrokenPipeError, ConnectionResetError):
                    pass  # browser went away; the agent already rolled the turn back
                except Exception as e:  # report every failure to the page instead of dying
                    if isinstance(e, anthropic.AuthenticationError):
                        app.reset_agent()
                    try:
                        emit({"type": "error", "message": friendly_error(e)})
                    except OSError:
                        pass
            finally:
                app.lock.release()

    return Handler


def _free_port(preferred: int) -> int:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


def serve(ws: Workspace, *, port: int = 8765, open_browser: bool = True,
          model: str | None = None, effort: str | None = None) -> None:
    app = QuillApp(ws, model=model, effort=effort)
    port = _free_port(port)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app, port))
    server.daemon_threads = True
    url = f"http://127.0.0.1:{port}/"
    print(f"Quill is running at {url}\nKeep this window open while you write. Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nQuill stopped. Your work is saved in", ws.root)
    finally:
        server.server_close()
