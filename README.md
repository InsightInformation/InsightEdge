# Quill — your personal writing agent

Quill is a command-line writing partner built on Claude. It learns **your** voice from samples of
your writing, then drafts, edits, critiques, and brainstorms with you — and it remembers what it
learns about your style across sessions.

## Setup

```bash
pip install -e .            # or: pip install -e ".[dev]" to run tests
export ANTHROPIC_API_KEY=sk-ant-...   # or run `ant auth login`
```

## Quick start

```bash
# 1. Teach it your voice (a few pieces you're happy with work best)
quill learn old-essay.md journal-entry.txt newsletter.md

# 2. Write together
quill                      # interactive chat (same as `quill chat`)
quill draft "A 600-word blog post about why I started running at 40" --name running-at-40
quill edit running-at-40 -m "tighter opening, less hedging"
quill critique ~/Documents/cover-letter.md -f "does it sound confident?"
quill brainstorm "a personal essay about moving back to my hometown"

# Keep iterating after a one-shot command
quill -i draft "birthday toast for my sister"
```

Local commands (no API call): `quill drafts`, `quill voice`, `quill where`.

Inside chat: `/drafts`, `/voice`, `/notes`, `/new`, `/help`, `/quit`. End a line with `\` to write
multiple lines.

## How it works

- **Voice profile** (`voice.md`) — a Markdown description of how you write: tone, rhythm,
  vocabulary, habits, and a do/don't list. `quill learn` builds it from your samples, and Quill
  updates it whenever you tell it something lasting ("I never use semicolons"). Edit it by hand anytime.
- **Drafts** (`drafts/*.md`) — Quill saves work here. Overwriting keeps the old version as
  `name.vN.md.bak`, so nothing is lost.
- **Notes** (`notes.md`) — ideas and snippets captured during sessions.
- **Samples** (`samples/*.txt`) — copies of the writing you taught it with.

Everything lives in `~/.quill` (override with `QUILL_HOME`) as plain files you own.

Under the hood Quill runs a streaming tool-use loop on the Claude API: Claude calls small tools to
read/update your voice profile, drafts, samples, and notes. Every tool input is validated before
it runs, and file names are slugified so the agent can only touch files inside the workspace.

## Configuration

| Variable        | Default          | Purpose                                            |
|-----------------|------------------|----------------------------------------------------|
| `QUILL_HOME`    | `~/.quill`       | Workspace directory                                |
| `QUILL_MODEL`   | `claude-opus-5`  | Claude model (also `--model`)                      |
| `QUILL_EFFORT`  | `high`           | Thinking effort: low/medium/high/xhigh/max (also `--effort`) |

Requests use prompt caching (cheaper follow-up turns) and server-side refusal fallbacks
(`fallbacks: "default"`), so if the primary model declines a request, another Claude model
answers it automatically.

## Development

```bash
pip install -e ".[dev]"
pytest
```

The tests use a fake client, so they run without an API key.
