"""Tools Claude can call to work with your workspace."""

from __future__ import annotations

import json
from typing import Any, Callable

from quill.store import Workspace
from quill.tells import report as tells_report


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        # Streamed requests: let large inputs (whole drafts) arrive as they are generated.
        "eager_input_streaming": True,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


_STR = {"type": "string"}

TOOLS: list[dict] = [
    _tool(
        "read_voice_profile",
        "Read the user's voice/style profile: tone, sentence rhythm, vocabulary, habits, and things to avoid.",
        {},
        [],
    ),
    _tool(
        "update_voice_profile",
        "Replace the user's voice profile with a revised full Markdown document. Use when you learn "
        "something durable about how the user writes or what they like/dislike. Preserve existing "
        "insights unless they are contradicted.",
        {"content": {**_STR, "description": "The complete new profile in Markdown."}},
        ["content"],
    ),
    _tool(
        "update_about_me",
        "Replace the user's 'About me' document (who they are, what they write, audiences, goals, "
        "current projects) with a revised full Markdown version. Keep existing facts unless corrected.",
        {"content": {**_STR, "description": "The complete new About-me document in Markdown."}},
        ["content"],
    ),
    _tool("list_drafts", "List saved drafts with word counts and last-modified times.", {}, []),
    _tool(
        "read_draft",
        "Read a saved draft by name.",
        {"name": {**_STR, "description": "Draft name as shown by list_drafts."}},
        ["name"],
    ),
    _tool(
        "save_draft",
        "Save a draft (full text, Markdown). Overwriting keeps the previous version as a backup.",
        {
            "name": {**_STR, "description": "Short title for the draft, e.g. 'newsletter-october'."},
            "content": {**_STR, "description": "The complete draft text."},
        },
        ["name", "content"],
    ),
    _tool(
        "check_writing",
        "Scan a piece of writing for AI tells: stock words, 'not X, it's Y' framing, em-dash habits, "
        "reflexive triads, moralizing endings, monotone rhythm. Habits found in the user's own samples "
        "are not flagged. Run this on every draft or rewrite before handing it over or saving it.",
        {"text": {**_STR, "description": "The full text to check."}},
        ["text"],
    ),
    _tool("list_samples", "List the user's writing samples used to learn their voice.", {}, []),
    _tool(
        "read_sample",
        "Read one of the user's writing samples.",
        {"name": {**_STR, "description": "Sample name as shown by list_samples."}},
        ["name"],
    ),
    _tool("read_notes", "Read the user's running list of notes and ideas.", {}, []),
    _tool(
        "append_note",
        "Add an idea, reminder, or snippet to the user's notes.",
        {"text": {**_STR, "description": "The note to add."}},
        ["text"],
    ),
]

_SCHEMAS = {t["name"]: t["input_schema"] for t in TOOLS}


class ToolInputError(ValueError):
    pass


def validate_input(name: str, data: Any) -> dict:
    """Validate tool input against its schema.

    Eager input streaming skips server-side validation, so a truncated or malformed
    input must be caught here before the tool runs.
    """
    schema = _SCHEMAS.get(name)
    if schema is None:
        raise ToolInputError(f"Unknown tool '{name}'.")
    if not isinstance(data, dict):
        raise ToolInputError("Tool input must be a JSON object.")
    props = schema["properties"]
    extra = set(data) - set(props)
    if extra:
        raise ToolInputError(f"Unexpected field(s): {', '.join(sorted(extra))}.")
    for key in schema["required"]:
        if key not in data:
            raise ToolInputError(f"Missing required field '{key}'.")
    for key, value in data.items():
        if props[key]["type"] == "string" and not isinstance(value, str):
            raise ToolInputError(f"Field '{key}' must be a string.")
    for key in ("content", "text"):
        if key in data and not data[key].strip():
            raise ToolInputError(f"Field '{key}' must not be empty.")
    return data


def run_tool(ws: Workspace, name: str, data: dict) -> str:
    """Execute a validated tool call and return its text result."""
    handlers: dict[str, Callable[[], str]] = {
        "read_voice_profile": lambda: ws.read_voice(),
        "update_voice_profile": lambda: (ws.write_voice(data["content"]), "Voice profile updated.")[1],
        "update_about_me": lambda: (ws.write_about(data["content"]), "About-me updated.")[1],
        "list_drafts": lambda: json.dumps(ws.list_drafts()) if ws.list_drafts() else "No drafts yet.",
        "read_draft": lambda: ws.read_draft(data["name"]),
        "save_draft": lambda: _save(ws, data["name"], data["content"]),
        "check_writing": lambda: tells_report(data["text"], _samples_text(ws)),
        "list_samples": lambda: json.dumps(ws.list_samples()) if ws.list_samples() else "No samples yet.",
        "read_sample": lambda: ws.read_sample(data["name"]),
        "read_notes": lambda: ws.read_notes(),
        "append_note": lambda: (ws.append_note(data["text"]), "Note added.")[1],
    }
    return handlers[name]()


def _samples_text(ws: Workspace) -> str:
    return "\n\n".join(text for _, text in ws.samples_for_prompt(max_words=20000))


def _save(ws: Workspace, name: str, content: str) -> str:
    path = ws.save_draft(name, content)
    check = tells_report(content, _samples_text(ws))
    if "No AI tells" in check:
        return f"Saved to {path}. {check}"
    return f"Saved to {path}.\nTell check on the saved text:\n{check}\nIf these aren't the user's style, revise and save again."
