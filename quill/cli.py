"""Command-line interface: `quill chat`, `quill draft`, `quill edit`, and friends."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import anthropic

from quill import __version__, prompts
from quill.store import Workspace, slugify

HELP = """Commands inside chat:
  /drafts   list saved drafts        /voice   show your voice profile
  /notes    show your notes          /new     start a fresh conversation
  /help     this help                /quit    exit
Anything else is sent to Quill. End a line with \\ to keep typing on the next line."""


def _source(ws: Workspace, target: str) -> tuple[str, str]:
    """Resolve a file path or draft name into (name, prompt text)."""
    path = Path(target).expanduser()
    if path.is_file():
        return slugify(path.stem), f"<piece title=\"{path.name}\">\n{path.read_text(encoding='utf-8')}\n</piece>"
    name = slugify(target)
    ws.read_draft(name)  # raises FileNotFoundError with a clear message
    return name, f"The piece is my saved draft '{name}' — read it with read_draft first."


def _read_input(prompt: str = "\nyou › ") -> str | None:
    lines = []
    try:
        line = input(prompt)
        while line.endswith("\\"):
            lines.append(line[:-1])
            line = input("    … ")
        lines.append(line)
    except EOFError:
        return None
    return "\n".join(lines).strip()


def chat(agent, ws: Workspace) -> None:
    print(f"Quill {__version__} — your writing partner. Type /help for commands.")
    while True:
        try:
            text = _read_input()
        except KeyboardInterrupt:
            print()
            return
        if text is None or text in ("/quit", "/exit"):
            return
        if not text:
            continue
        if text == "/help":
            print(HELP)
        elif text == "/drafts":
            drafts = ws.list_drafts()
            print("\n".join(f"  {d['name']:<40} {d['words']:>6} words  {d['modified']}" for d in drafts)
                  or "  No drafts yet.")
        elif text == "/voice":
            print(ws.read_voice())
        elif text == "/notes":
            print(ws.read_notes())
        elif text == "/new":
            agent.reset()
            print("  Started a fresh conversation.")
        else:
            print("\nquill › ", end="")
            try:
                agent.send(text)
            except KeyboardInterrupt:
                print("\n  (interrupted)")
            except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError) as e:
                print(f"\n  (temporary API problem: {type(e).__name__} — try again)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="quill", description="A personal writing agent powered by Claude.")
    p.add_argument("--version", action="version", version=f"quill {__version__}")
    p.add_argument("--model", help="Claude model ID (default: $QUILL_MODEL or claude-opus-5)")
    p.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"],
                   help="How hard Claude thinks (default: $QUILL_EFFORT or high)")
    p.add_argument("-i", "--interactive", action="store_true",
                   help="After a one-shot command, stay in chat to keep iterating")
    sub = p.add_subparsers(dest="command")

    sub.add_parser("chat", help="Open an interactive writing session (default)")
    s = sub.add_parser("learn", help="Learn your voice from samples of your writing")
    s.add_argument("files", nargs="+", type=Path)
    s = sub.add_parser("draft", help="Draft something from a brief")
    s.add_argument("brief")
    s.add_argument("--name", help="Draft name to save as")
    s = sub.add_parser("edit", help="Revise a file or saved draft")
    s.add_argument("target", help="File path or draft name")
    s.add_argument("-m", "--instructions", default="", help="What to change")
    s = sub.add_parser("critique", help="Get editorial feedback on a file or draft")
    s.add_argument("target", help="File path or draft name")
    s.add_argument("-f", "--focus", default="", help="What to focus on")
    s = sub.add_parser("brainstorm", help="Generate angles, openings, and titles")
    s.add_argument("topic")
    sub.add_parser("drafts", help="List saved drafts")
    sub.add_parser("voice", help="Show your voice profile")
    sub.add_parser("where", help="Show the workspace directory")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ws = Workspace.default()
    cmd = args.command or "chat"

    # Local commands — no API call.
    if cmd == "drafts":
        for d in ws.list_drafts():
            print(f"{d['name']:<40} {d['words']:>6} words  {d['modified']}")
        return 0
    if cmd == "voice":
        print(ws.read_voice())
        return 0
    if cmd == "where":
        print(ws.root)
        return 0

    try:
        task = None
        if cmd == "learn":
            names = []
            for f in args.files:
                if not f.is_file():
                    print(f"quill: not a file: {f}", file=sys.stderr)
                    return 2
                names.append(ws.add_sample(f).stem)
            task = prompts.LEARN_TASK.format(names=", ".join(names))
        elif cmd == "draft":
            task = prompts.DRAFT_TASK.format(brief=args.brief, name=slugify(args.name or args.brief[:50]))
        elif cmd == "edit":
            name, source = _source(ws, args.target)
            how = f" as follows: {args.instructions}" if args.instructions else " to make it stronger"
            task = prompts.EDIT_TASK.format(how=how, name=name, source=source)
        elif cmd == "critique":
            _, source = _source(ws, args.target)
            focus = f", focusing on {args.focus}" if args.focus else ""
            task = prompts.CRITIQUE_TASK.format(focus=focus, source=source)
        elif cmd == "brainstorm":
            task = prompts.BRAINSTORM_TASK.format(topic=args.topic)
    except FileNotFoundError as e:
        print(f"quill: {e}", file=sys.stderr)
        return 2

    from quill.agent import WritingAgent

    try:
        agent = WritingAgent(ws, model=args.model, effort=args.effort)
        if task:
            agent.send(task)
        if not task or args.interactive:
            chat(agent, ws)
    except anthropic.AuthenticationError:
        print("quill: authentication failed — set ANTHROPIC_API_KEY or run `ant auth login`.", file=sys.stderr)
        return 1
    except anthropic.RateLimitError:
        print("quill: rate limited by the API — wait a moment and try again.", file=sys.stderr)
        return 1
    except anthropic.APIStatusError as e:
        print(f"quill: API error {e.status_code}: {e.message}", file=sys.stderr)
        return 1
    except anthropic.APIConnectionError:
        print("quill: could not reach the Claude API — check your connection.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print()
        return 130
    return 0
