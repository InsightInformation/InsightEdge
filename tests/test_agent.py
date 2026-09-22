from types import SimpleNamespace as NS

import pytest

from quill.agent import WritingAgent
from quill.store import Workspace


class FakeStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        for block in self.message.content:
            if block.type == "text":
                yield NS(type="text", text=block.text)

    def get_final_message(self):
        return self.message


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.beta = NS(messages=NS(stream=self._stream))

    def _stream(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return FakeStream(self.responses.pop(0))


def msg(stop, *blocks, model="claude-opus-5"):
    return NS(stop_reason=stop, content=list(blocks), model=model)


def text(t):
    return NS(type="text", text=t)


def tool_use(id_, name, input_):
    return NS(type="tool_use", id=id_, name=name, input=input_)


@pytest.fixture
def ws(tmp_path):
    w = Workspace(tmp_path)
    w.ensure()
    return w


def make(ws, responses):
    client = FakeClient(responses)
    return WritingAgent(ws, client=client, out=lambda s: None), client


def test_runs_tools_and_returns_final_text(ws):
    agent, client = make(ws, [
        msg("tool_use", text("Drafting."), tool_use("t1", "save_draft", {"name": "Poem", "content": "roses"})),
        msg("end_turn", text("Saved your poem.")),
    ])
    assert agent.send("write a poem") == "Saved your poem."
    assert ws.read_draft("poem").strip() == "roses"
    result = client.calls[1]["messages"][-1]["content"][0]
    assert result["tool_use_id"] == "t1" and "is_error" not in result
    # Request shape: fallbacks + effort + caching on every call.
    call = client.calls[0]
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["output_config"] == {"effort": "high"}
    assert "voice_profile" in call["system"][1]["text"]


def test_invalid_tool_input_returns_error_result(ws):
    agent, client = make(ws, [
        msg("tool_use", tool_use("t1", "save_draft", {"name": "x"})),
        msg("end_turn", text("oops")),
    ])
    agent.send("go")
    result = client.calls[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True and "content" in result["content"]


def test_truncated_tool_call_is_not_run(ws):
    agent, client = make(ws, [
        msg("max_tokens", tool_use("t1", "save_draft", {"name": "x", "content": "partial"})),
        msg("end_turn", text("retry")),
    ])
    agent.send("go")
    assert ws.list_drafts() == []
    assert client.calls[1]["messages"][-1]["content"][0]["is_error"] is True


def test_refusal_drops_user_turn(ws):
    agent, _ = make(ws, [msg("refusal")])
    assert agent.send("bad") == ""
    assert agent.messages == []


def test_garbled_json_is_retried(ws):
    agent, client = make(ws, [msg("end_turn", text("ok"))])
    real = client._stream
    fails = {"n": 1}

    def flaky(**kw):
        if fails["n"]:
            fails["n"] -= 1
            raise ValueError("bad json")
        return real(**kw)

    client.beta.messages.stream = flaky
    assert agent.send("hi") == "ok"


def test_error_mid_turn_rolls_back(ws):
    agent, client = make(ws, [msg("tool_use", tool_use("t1", "list_drafts", {}))])
    # Second call has no queued response -> IndexError mid-turn.
    with pytest.raises(IndexError):
        agent.send("go")
    assert agent.messages == []
