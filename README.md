# Quill — your personal writing agent

Quill is a command-line writing partner built on Claude. It learns **your** voice from samples of
your writing, then drafts, edits, critiques, and brainstorms with you — and it remembers what it
learns about your style across sessions.

## Install (one time)

You need Python 3.10+ ([python.org](https://www.python.org/downloads/)) and an Anthropic API key
([console.anthropic.com](https://console.anthropic.com/settings/keys)).

**Mac / Linux**: in a terminal, from this folder:

```bash
./install.sh
```

**Windows**: in PowerShell, from this folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The installer puts Quill in its own private environment, adds a **Quill** shortcut to your Desktop
(Mac/Windows) or app menu (Linux), and opens it. The first time, Quill asks your name, what you write,
who you write for, your goals, and your API key. The key is saved only on your computer
(`~/.quill/config.json`, readable only by you).

## Everyday use

Double-click **Quill** (or type `quill`). It opens in your browser at `http://127.0.0.1:8765` and
runs only on your computer. From there:

- **Teach Quill my voice**: paste something you've written; Quill studies it and builds your voice
  profile. Add a few pieces over time and it keeps getting closer to how you sound.
- **Draft / Edit / Get feedback / Brainstorm**: pick a starter or just type what you want.
- **The desk**: open any draft (or **＋ Blank page**) and it fills the screen as a proper editor
  that autosaves as you type. Beside the page:
  - **Sound check** scores how human the piece reads and underlines AI tells right in the text:
    stock words ("delve", "journey", "testament"), "it's not X, it's Y" framing, "The result?"
    reveals, em-dash habits, tidy morals, and monotone sentence rhythm. Click a finding to jump
    to it, or hit **Fix** to have Quill rewrite just that sentence.
  - **Rework a passage**: select any text and pick *Less AI*, *Tighten*, *Plainer*, *More vivid*,
    *Warmer*, *Sharper*, or type your own instruction. Quill rewrites only that passage, in your
    voice, and you choose whether to use it. Ctrl+Z still works.
  - **Versions** lists every earlier save, and you can preview or restore any of them. There's
    also rename, export to `.md`, and **Focus** mode (Ctrl+.) to hide everything but the page.
- **My voice profile / About me**: read and edit what Quill knows about you. It updates these on
  its own when you tell it something lasting ("I hate semicolons", "I'm starting a newsletter").
- **Settings**: change your name, API key, model, or effort.

### Terminal, if you prefer

```bash
quill chat                                   # chat in the terminal
quill setup                                  # redo the first-run questions
quill learn old-essay.md journal.txt         # learn your voice from files
quill draft "600 words on why I started running at 40" --name running-at-40
quill edit running-at-40 -m "tighter opening, less hedging"
quill critique ~/Documents/cover-letter.md -f "does it sound confident?"
quill brainstorm "moving back to my hometown"
quill drafts        # also: quill voice, quill where (no API call)
```

## How it works

- **Voice profile** (`voice.md`) — a Markdown description of how you write: tone, rhythm,
  vocabulary, habits, and a do/don't list. `quill learn` builds it from your samples, and Quill
  updates it whenever you tell it something lasting ("I never use semicolons"). Edit it by hand anytime.
- **Drafts** (`drafts/*.md`) — Quill saves work here. Overwriting keeps the old version as
  `name.vN.md.bak`, so nothing is lost.
- **About me** (`about.md`): who you are, what you write, your audiences and goals, so Quill's help is personal.
- **Notes** (`notes.md`) — ideas and snippets captured during sessions.
- **Samples** (`samples/*.txt`) — copies of the writing you taught it with. The samples
  themselves (up to about 8,000 words, newest first) go to Claude with every request. The profile
  only describes your voice; the samples show it, and Claude imitates what it can see.
- **AI-tell checker** (`quill/tells.py`) is a local, rule-based scan that runs without an API
  call. Quill runs it on every draft before saving and revises anything it flags. A habit that
  shows up in your own samples (say you love em dashes) is treated as your voice and never
  flagged.

Everything lives in `~/.quill` (override with `QUILL_HOME`) as plain files you own.

The browser app listens only on `127.0.0.1`, and every request must carry a secret token generated
each time Quill starts, so other websites open in your browser can't reach it.

Under the hood Quill runs a streaming tool-use loop on the Claude API: Claude calls small tools to
read/update your voice profile, drafts, samples, and notes. Every tool input is validated before
it runs, and file names are slugified so the agent can only touch files inside the workspace.

## Configuration

| Variable        | Default          | Purpose                                            |
|-----------------|------------------|----------------------------------------------------|
| `QUILL_HOME`    | `~/.quill`       | Workspace directory                                |
| `QUILL_MODEL`   | `claude-opus-5`  | Claude model (also `--model` or Settings)          |
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
