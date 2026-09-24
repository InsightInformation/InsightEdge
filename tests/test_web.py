import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import quill.agent
from quill.store import Workspace
from quill.web import QuillApp, make_handler

from conftest import FakeClient, msg, text, tool_use


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    ws = Workspace(tmp_path)
    ws.ensure()
    fake = FakeClient([])
    monkeypatch.setattr(quill.agent, "make_client", lambda ws: fake)
    app = QuillApp(ws)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), None)
    port = httpd.server_address[1]
    httpd.RequestHandlerClass = make_handler(app, port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield {"url": f"http://127.0.0.1:{port}", "app": app, "ws": ws, "fake": fake}
    httpd.shutdown()


def call(server, path, body=None, token=True, raw=False):
    req = urllib.request.Request(server["url"] + path, method="POST" if body is not None else "GET")
    if token:
        req.add_header("X-Quill-Token", server["app"].token)
    if body is not None:
        req.data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        data = r.read().decode()
        return data if raw else json.loads(data)


def test_page_embeds_token(server):
    page = call(server, "/", raw=True, token=False)
    assert server["app"].token in page and "__QUILL_TOKEN__" not in page


def test_api_requires_token(server):
    with pytest.raises(urllib.error.HTTPError) as e:
        call(server, "/api/state", token=False)
    assert e.value.code == 403


def test_rejects_foreign_host(server):
    req = urllib.request.Request(server["url"] + "/api/state", headers={
        "X-Quill-Token": server["app"].token, "Host": "evil.example:80"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 403


def test_setup_flow(server):
    assert call(server, "/api/state")["needs_setup"] is True
    state = call(server, "/api/setup", {"name": "Mikhail", "api_key": "sk-test", "about": "# About Me\nI write essays."})
    assert state["needs_setup"] is False and state["name"] == "Mikhail" and state["key_source"] == "saved"
    assert "api_key" not in state
    assert "I write essays." in server["ws"].read_about()
    # Blank key in Settings keeps the saved one.
    call(server, "/api/setup", {"name": "Mikhail", "api_key": ""})
    assert server["ws"].load_config()["api_key"] == "sk-test"


def test_drafts_and_samples(server):
    call(server, "/api/draft", {"name": "My Letter", "content": "Dear you"})
    assert call(server, "/api/draft?name=my-letter")["content"].strip() == "Dear you"
    with pytest.raises(urllib.error.HTTPError):
        call(server, "/api/sample", {"name": "tiny", "text": "too short"})
    r = call(server, "/api/sample", {"name": "Blog", "text": "word " * 50})
    assert r["name"] == "blog" and "blog" in r["prompt"]


def test_chat_streams_events(server):
    server["fake"].responses.extend([
        msg("tool_use", text("On it. "), tool_use("t1", "save_draft", {"name": "note", "content": "hi"})),
        msg("end_turn", text("Saved.")),
    ])
    body = call(server, "/api/chat", {"message": "save a note"}, raw=True)
    events = [json.loads(line[6:]) for line in body.split("\n\n") if line.startswith("data: ")]
    assert [e["type"] for e in events if e["type"] != "text"] == ["tool", "done"]
    assert next(e for e in events if e["type"] == "tool")["label"] == "Saving a draft"
    assert "".join(e.get("text", "") for e in events).strip() == "On it. Saved."
    assert server["ws"].read_draft("note").strip() == "hi"


def test_chat_reports_errors(server):
    body = call(server, "/api/chat", {"message": "hello"}, raw=True)  # no queued response -> error
    assert '"type": "error"' in body


def test_check_endpoint(server):
    r = call(server, "/api/check", {"text": "It's not about speed, it's about showing up."})
    assert r["score"] < 100 and any(t["kind"] == "contrast" for t in r["tells"])


def test_rewrite_endpoint(server):
    server["fake"].responses.append(msg("end_turn", text("<rewrite>I ran.</rewrite>")))
    r = call(server, "/api/rewrite", {"passage": "Running is a journey.", "instruction": "tighten"})
    assert r["text"] == "I ran." and r["check"]["score"] == 100


def test_versions_and_delete_endpoints(server):
    call(server, "/api/draft", {"name": "e", "content": "one"})
    call(server, "/api/draft", {"name": "e", "content": "two"})
    d = call(server, "/api/draft?name=e")
    assert d["versions"][0]["version"] == 1
    assert call(server, "/api/version?name=e&v=1")["content"].strip() == "one"
    call(server, "/api/draft/delete", {"name": "e"})
    assert call(server, "/api/state")["drafts"] == []
