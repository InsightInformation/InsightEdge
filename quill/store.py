"""On-disk workspace: your voice profile, writing samples, drafts and notes.

Everything is plain Markdown/text under one directory (default ``~/.quill``,
override with ``QUILL_HOME``) so you can read, edit, and back it up yourself.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_VOICE = """# My Voice Profile

_No profile yet. Run `quill learn <files>` with a few samples of your own writing,
or tell Quill about your style in chat and ask it to update this profile._
"""

DEFAULT_ABOUT = """# About Me

_Tell Quill who you are: what you write, who you write for, and what you're working toward._
"""

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Turn a free-form title into a safe file stem ("My Essay!" -> "my-essay")."""
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return slug[:80] or "untitled"


@dataclass
class Workspace:
    root: Path

    @classmethod
    def default(cls) -> "Workspace":
        root = Path(os.environ.get("QUILL_HOME", Path.home() / ".quill")).expanduser()
        ws = cls(root)
        ws.ensure()
        return ws

    # --- layout -------------------------------------------------------------
    @property
    def voice_path(self) -> Path:
        return self.root / "voice.md"

    @property
    def about_path(self) -> Path:
        return self.root / "about.md"

    @property
    def config_path(self) -> Path:
        return self.root / "config.json"

    @property
    def notes_path(self) -> Path:
        return self.root / "notes.md"

    @property
    def drafts_dir(self) -> Path:
        return self.root / "drafts"

    @property
    def samples_dir(self) -> Path:
        return self.root / "samples"

    def ensure(self) -> None:
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        self.samples_dir.mkdir(parents=True, exist_ok=True)
        if not self.voice_path.exists():
            self.voice_path.write_text(DEFAULT_VOICE, encoding="utf-8")
        if not self.about_path.exists():
            self.about_path.write_text(DEFAULT_ABOUT, encoding="utf-8")
        if not self.notes_path.exists():
            self.notes_path.write_text("# Notes & Ideas\n", encoding="utf-8")

    # --- voice profile ------------------------------------------------------
    def read_voice(self) -> str:
        return self.voice_path.read_text(encoding="utf-8")

    def write_voice(self, content: str) -> None:
        self.voice_path.write_text(content.rstrip() + "\n", encoding="utf-8")

    # --- about me -----------------------------------------------------------
    def read_about(self) -> str:
        return self.about_path.read_text(encoding="utf-8")

    def write_about(self, content: str) -> None:
        self.about_path.write_text(content.rstrip() + "\n", encoding="utf-8")

    # --- config (name, API key, preferences) ---------------------------------
    def load_config(self) -> dict:
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_config(self, updates: dict) -> dict:
        """Merge ``updates`` into the config; keys set to None are removed. File is owner-only."""
        config = {**self.load_config(), **updates}
        config = {k: v for k, v in config.items() if v not in (None, "")}
        fd = os.open(self.config_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, sort_keys=True)
        os.chmod(self.config_path, 0o600)
        return config

    def has_credentials(self) -> bool:
        return bool(
            self.load_config().get("api_key")
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        )

    def needs_setup(self) -> bool:
        return not self.load_config().get("name") or not self.has_credentials()

    # --- drafts -------------------------------------------------------------
    def _draft_file(self, name: str) -> Path:
        return self.drafts_dir / f"{slugify(name)}.md"

    def list_drafts(self) -> list[dict]:
        drafts = []
        for p in sorted(self.drafts_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
            text = p.read_text(encoding="utf-8")
            drafts.append(
                {
                    "name": p.stem,
                    "words": len(text.split()),
                    "modified": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                }
            )
        return drafts

    def read_draft(self, name: str) -> str:
        path = self._draft_file(name)
        if not path.exists():
            raise FileNotFoundError(f"No draft named '{slugify(name)}'.")
        return path.read_text(encoding="utf-8")

    def save_draft(self, name: str, content: str) -> Path:
        """Save a draft, keeping the previous version as ``<name>.v<N>.md.bak``."""
        path = self._draft_file(name)
        if path.exists():
            n = 1
            while (bak := path.with_name(f"{path.stem}.v{n}.md.bak")).exists():
                n += 1
            path.rename(bak)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        return path

    # --- samples ------------------------------------------------------------
    def add_sample(self, source: Path) -> Path:
        return self.add_sample_text(source.stem, source.read_text(encoding="utf-8"))

    def add_sample_text(self, name: str, text: str) -> Path:
        dest = self.samples_dir / f"{slugify(name)}.txt"
        dest.write_text(text, encoding="utf-8")
        return dest

    def list_versions(self, name: str) -> list[dict]:
        """Earlier saved versions of a draft, newest first."""
        stem = slugify(name)
        out = []
        for p in self.drafts_dir.glob(f"{stem}.v*.md.bak"):
            m = re.fullmatch(rf"{re.escape(stem)}\.v(\d+)\.md\.bak", p.name)
            if m:
                out.append({
                    "version": int(m.group(1)),
                    "words": len(p.read_text(encoding="utf-8").split()),
                    "modified": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                })
        return sorted(out, key=lambda v: -v["version"])

    def read_version(self, name: str, version: int) -> str:
        path = self.drafts_dir / f"{slugify(name)}.v{int(version)}.md.bak"
        if not path.exists():
            raise FileNotFoundError(f"No version {version} of '{slugify(name)}'.")
        return path.read_text(encoding="utf-8")

    def delete_draft(self, name: str) -> None:
        """Move a draft out of the list; the file is kept as a .deleted backup."""
        path = self._draft_file(name)
        if not path.exists():
            raise FileNotFoundError(f"No draft named '{slugify(name)}'.")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path.rename(path.with_name(f"{path.stem}.deleted-{stamp}.md.bak"))

    def list_samples(self) -> list[str]:
        return sorted(p.stem for p in self.samples_dir.glob("*.txt"))

    def read_sample(self, name: str) -> str:
        path = self.samples_dir / f"{slugify(name)}.txt"
        if not path.exists():
            raise FileNotFoundError(f"No sample named '{slugify(name)}'.")
        return path.read_text(encoding="utf-8")

    def samples_for_prompt(self, max_words: int = 8000) -> list[tuple[str, str]]:
        """Sample texts to show the model, newest first, trimmed to a total word budget."""
        paths = sorted(self.samples_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
        out, left = [], max_words
        for p in paths:
            if left <= 200:
                break
            words = p.read_text(encoding="utf-8").split(" ")
            text = " ".join(words[:left])
            left -= len(words[:left])
            out.append((p.stem, text))
        return out

    # --- notes --------------------------------------------------------------
    def read_notes(self) -> str:
        return self.notes_path.read_text(encoding="utf-8")

    def append_note(self, text: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self.notes_path.open("a", encoding="utf-8") as f:
            f.write(f"\n- [{stamp}] {text.strip()}\n")
