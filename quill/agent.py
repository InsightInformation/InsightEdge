"""The agent loop: streams Claude's replies and runs workspace tools until the turn is done."""

from __future__ import annotations

import os
import re
import sys
from typing import Callable

import anthropic

from quill.prompts import REWRITE_PRESETS, REWRITE_SYSTEM, SYSTEM_PROMPT, about_block, samples_block, voice_block
from quill.store import Workspace
from quill.tools import TOOLS, ToolInputError, run_tool, validate_input

DEFAULT_MODEL = "claude-opus-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 64000
MAX_JSON_RETRIES = 2
MAX_STEPS = 25


def make_client(workspace: Workspace) -> anthropic.Anthropic:
    """Environment credentials win; otherwise use the key saved during setup."""
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return anthropic.Anthropic()
    key = workspace.load_config().get("api_key")
    return anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()


class WritingAgent:
    def __init__(
        self,
        workspace: Workspace,
        *,
        model: str | None = None,
        effort: str | None = None,
        client: anthropic.Anthropic | None = None,
        out: Callable[[str], None] | None = None,
        on_tool: Callable[[str], None] | None = None,
    ) -> None:
        self.ws = workspace
        config = workspace.load_config()
        self.model = model or os.environ.get("QUILL_MODEL") or config.get("model") or DEFAULT_MODEL
        self.effort = effort or os.environ.get("QUILL_EFFORT") or config.get("effort") or "high"
        self.client = client or make_client(workspace)
        self.out = out or (lambda s: (sys.stdout.write(s), sys.stdout.flush()))
        self.on_tool = on_tool or (lambda name: self.out(f"\n  · {name.replace('_', ' ')}…\n"))
        self.messages: list = []
        self._system = self._build_system()

    def _build_system(self) -> list[dict]:
        # Profiles are snapshotted per conversation so the prefix stays cacheable;
        # the agent reads the live voice file via read_voice_profile when it needs the latest.
        return [
            {"type": "text", "text": SYSTEM_PROMPT},
            {"type": "text", "text": about_block(self.ws.load_config().get("name"), self.ws.read_about())},
            {"type": "text", "text": voice_block(self.ws.read_voice())},
            # Real samples beat any description of a voice: the model imitates what it sees.
            {"type": "text", "text": samples_block(self.ws.samples_for_prompt())},
        ]

    def reset(self) -> None:
        self.messages = []
        self._system = self._build_system()

    # --- one model call -----------------------------------------------------
    def _stream_once(self):
        with self.client.beta.messages.stream(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=self._system,
            tools=TOOLS,
            messages=self.messages,
            output_config={"effort": self.effort},
            cache_control={"type": "ephemeral"},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            for event in stream:
                if event.type == "text":
                    self.out(event.text)
                elif event.type == "content_block_start" and event.content_block.type == "tool_use":
                    self.on_tool(event.content_block.name)
            return stream.get_final_message()

    def _call_model(self):
        for attempt in range(MAX_JSON_RETRIES + 1):
            try:
                return self._stream_once()
            except ValueError:
                # Eager input streaming can yield unparseable tool JSON; nothing was
                # appended to history, so simply re-issue the request.
                if attempt == MAX_JSON_RETRIES:
                    raise
                self.out("\n  (retrying a garbled tool call…)\n")

    # --- a full user turn ---------------------------------------------------
    def send(self, text: str) -> str:
        """Send a user message, run tools as needed, and return the final reply text.

        If anything fails mid-turn (API error, Ctrl-C), the turn is rolled back so the
        conversation history stays valid and the chat can carry on.
        """
        start = len(self.messages)
        try:
            return self._run_turn(text)
        except BaseException:
            del self.messages[start:]
            raise

    def _run_turn(self, text: str) -> str:
        self.messages.append({"role": "user", "content": text})
        final_text = ""
        for _ in range(MAX_STEPS):
            response = self._call_model()

            if response.stop_reason == "refusal":
                self.messages.pop()  # drop the unanswered user turn so the chat can continue
                self.out("\n[Claude declined this request. Try rephrasing it.]\n")
                return ""

            if response.model != self.model:
                self.out(f"\n  (answered by fallback model {response.model})\n")

            self.messages.append({"role": "assistant", "content": response.content})
            final_text = "".join(b.text for b in response.content if b.type == "text")
            tool_uses = [b for b in response.content if b.type == "tool_use"]

            if response.stop_reason == "pause_turn":
                continue
            if not tool_uses:
                if response.stop_reason == "max_tokens":
                    self.out("\n[Reply hit the length limit — say 'continue' for more.]\n")
                break

            truncated = response.stop_reason == "max_tokens"
            results = []
            for block in tool_uses:
                results.append(self._tool_result(block, truncated))
            self.messages.append({"role": "user", "content": results})
        else:
            self.out("\n[Stopped after too many tool steps.]\n")

        self.out("\n")
        return final_text

    def _tool_result(self, block, truncated: bool) -> dict:
        result = {"type": "tool_result", "tool_use_id": block.id}
        if truncated:
            return {**result, "content": "Tool input was cut off by the output limit; not run. Retry "
                    "with a shorter input.", "is_error": True}
        try:
            data = validate_input(block.name, block.input)
            return {**result, "content": run_tool(self.ws, block.name, data)}
        except (ToolInputError, FileNotFoundError, OSError) as e:
            return {**result, "content": f"Error: {e}", "is_error": True}


def rewrite_passage(
    ws: Workspace,
    client: anthropic.Anthropic,
    *,
    passage: str,
    instruction: str,
    before: str = "",
    after: str = "",
    model: str | None = None,
    effort: str | None = None,
) -> str:
    """Rewrite one passage of a draft in the user's voice and return only the new passage."""
    config = ws.load_config()
    model = model or os.environ.get("QUILL_MODEL") or config.get("model") or DEFAULT_MODEL
    effort = effort or os.environ.get("QUILL_EFFORT") or config.get("effort") or "high"
    how = REWRITE_PRESETS.get(instruction, instruction.strip() or REWRITE_PRESETS["human"])
    prompt = (
        f"<before>\n{before[-2500:]}\n</before>\n\n<passage>\n{passage}\n</passage>\n\n"
        f"<after>\n{after[:1500]}\n</after>\n\nRewrite only the passage. {how}"
    )
    response = client.beta.messages.create(
        model=model,
        max_tokens=16000,
        system=[
            {"type": "text", "text": REWRITE_SYSTEM},
            {"type": "text", "text": voice_block(ws.read_voice())},
            {"type": "text", "text": samples_block(ws.samples_for_prompt())},
        ],
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": effort},
        cache_control={"type": "ephemeral"},
        betas=[FALLBACK_BETA],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to rewrite this passage.")
    out = "".join(b.text for b in response.content if b.type == "text")
    m = re.search(r"<rewrite>\n?(.*?)\n?</rewrite>", out, re.S)
    text = (m.group(1) if m else out).strip("\n")
    # Keep the passage's own leading/trailing whitespace so it drops back in cleanly.
    lead = passage[: len(passage) - len(passage.lstrip())]
    trail = passage[len(passage.rstrip()):]
    return lead + text.strip() + trail
