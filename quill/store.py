"""On-disk workspace: your voice profile, writing samples, drafts and notes.

Everything is plain Markdown/text under one directory (default ``~/.quill``,
override with ``QUILL_HOME``) so you can read, edit, and back it up yourself.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_VOICE = """# My Voice Profile

_No profile yet. Run `quill learn <files>` with a few samples of your own writing,
or tell Quill about your style in chat and ask it to update this profile._
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
        if not self.notes_path.exists():
            self.notes_path.write_text("# Notes & Ideas\n", encoding="utf-8")

    # --- voice profile ------------------------------------------------------
    def read_voice(self) -> str:
        return self.voice_path.read_text(encoding="utf-8")

    def write_voice(self, content: str) -> None:
        self.voice_path.write_text(content.rstrip() + "\n", encoding="utf-8")

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
        dest = self.samples_dir / f"{slugify(source.stem)}.txt"
        dest.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return dest

    def list_samples(self) -> list[str]:
        return sorted(p.stem for p in self.samples_dir.glob("*.txt"))

    def read_sample(self, name: str) -> str:
        path = self.samples_dir / f"{slugify(name)}.txt"
        if not path.exists():
            raise FileNotFoundError(f"No sample named '{slugify(name)}'.")
        return path.read_text(encoding="utf-8")

    # --- notes --------------------------------------------------------------
    def read_notes(self) -> str:
        return self.notes_path.read_text(encoding="utf-8")

    def append_note(self, text: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self.notes_path.open("a", encoding="utf-8") as f:
            f.write(f"\n- [{stamp}] {text.strip()}\n")
