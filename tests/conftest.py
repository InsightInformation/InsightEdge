from types import SimpleNamespace as NS


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
            elif block.type == "tool_use":
                yield NS(type="content_block_start", content_block=block)

    def get_final_message(self):
        return self.message


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.beta = NS(messages=NS(stream=self._stream, create=self._create))

    def _create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)

    def _stream(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return FakeStream(self.responses.pop(0))


def msg(stop, *blocks, model="claude-opus-5"):
    return NS(stop_reason=stop, content=list(blocks), model=model)


def text(t):
    return NS(type="text", text=t)


def tool_use(id_, name, input_):
    return NS(type="tool_use", id=id_, name=name, input=input_)
