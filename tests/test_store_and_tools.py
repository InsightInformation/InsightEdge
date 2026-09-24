import pytest

from quill.store import Workspace, slugify
from quill.tools import TOOLS, ToolInputError, run_tool, validate_input


@pytest.fixture
def ws(tmp_path):
    w = Workspace(tmp_path)
    w.ensure()
    return w


def test_slugify():
    assert slugify("  My Essay: Part 2! ") == "my-essay-part-2"
    assert slugify("../../etc/passwd") == "etc-passwd"
    assert slugify("!!!") == "untitled"


def test_save_draft_keeps_backups(ws):
    ws.save_draft("Morning Pages", "first")
    ws.save_draft("morning pages", "second")
    assert ws.read_draft("Morning Pages").strip() == "second"
    assert (ws.drafts_dir / "morning-pages.v1.md.bak").read_text().strip() == "first"
    assert [d["name"] for d in ws.list_drafts()] == ["morning-pages"]


def test_missing_draft(ws):
    with pytest.raises(FileNotFoundError):
        ws.read_draft("nope")


def test_samples_and_notes(ws, tmp_path):
    src = tmp_path / "Old Blog Post.txt"
    src.write_text("I write short sentences.")
    ws.add_sample(src)
    assert ws.list_samples() == ["old-blog-post"]
    assert ws.read_sample("old-blog-post") == "I write short sentences."
    ws.append_note("essay about bikes")
    assert "essay about bikes" in ws.read_notes()


def test_validate_input():
    assert validate_input("save_draft", {"name": "a", "content": "b"})
    with pytest.raises(ToolInputError):
        validate_input("save_draft", {"name": "a"})
    with pytest.raises(ToolInputError):
        validate_input("save_draft", {"name": "a", "content": 3})
    with pytest.raises(ToolInputError):
        validate_input("save_draft", {"name": "a", "content": "b", "x": 1})
    with pytest.raises(ToolInputError):
        validate_input("update_voice_profile", {"content": "   "})
    with pytest.raises(ToolInputError):
        validate_input("delete_everything", {})


def test_every_tool_has_a_handler(ws):
    sample_inputs = {"name": "x", "content": "hello", "text": "idea"}
    ws.save_draft("x", "draft")
    (ws.samples_dir / "x.txt").write_text("sample")
    for tool in TOOLS:
        props = tool["input_schema"]["properties"]
        data = {k: sample_inputs[k] for k in props}
        assert isinstance(run_tool(ws, tool["name"], validate_input(tool["name"], data)), str)


def test_versions_and_delete(ws):
    ws.save_draft("Essay", "one")
    ws.save_draft("Essay", "two")
    ws.save_draft("Essay", "three")
    assert [v["version"] for v in ws.list_versions("essay")] == [2, 1]
    assert ws.read_version("essay", 1).strip() == "one"
    ws.delete_draft("essay")
    assert ws.list_drafts() == []
    with pytest.raises(FileNotFoundError):
        ws.delete_draft("essay")


def test_save_draft_reports_tells(ws):
    out = run_tool(ws, "save_draft", {"name": "x", "content": "It's not about speed, it's about showing up."})
    assert "Saved" in out and "contrast" in out
    assert "No AI tells" in run_tool(ws, "save_draft", {"name": "y", "content": "I ran. It hurt."})


def test_samples_for_prompt_respects_budget(ws):
    ws.add_sample_text("a", "word " * 5000)
    ws.add_sample_text("b", "word " * 5000)
    total = sum(len(t.split()) for _, t in ws.samples_for_prompt(max_words=6000))
    assert total <= 6000
