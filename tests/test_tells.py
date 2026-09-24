from quill.tells import analyze, find_tells, report

SLOP = """In today's fast-paced world, running is more than just a hobby — it's a journey. \
It's not about speed, it's about showing up. The result? A profound sense of clarity, \
reminding me that growth takes time. Ultimately, it's a testament to the power of consistency."""

HUMAN = """I ran four miles this morning and hated three of them. The fourth was fine. My left \
knee clicks on downhills now, which Dana says is normal for forty and which I say is the \
beginning of the end. Anyway. I kept going because the alternative was email."""


def kinds(text, samples=""):
    return {t.kind for t in find_tells(text, samples)}


def test_flags_the_classic_tells():
    found = kinds(SLOP)
    assert {"phrase", "contrast", "reveal", "word", "tail", "dash"} <= found
    assert analyze(SLOP)["score"] < 30


def test_plain_human_prose_is_clean():
    assert find_tells(HUMAN) == []
    assert analyze(HUMAN)["score"] == 100


def test_users_own_habits_are_not_flagged():
    text = "The landscape was flat. We walked for hours and nobody said much of anything at all."
    assert "word" in kinds(text)
    assert "word" not in kinds(text, samples="I love the landscape out west.")


def test_dashes_ok_when_the_user_writes_that_way():
    text = "I went back — twice — and it was worse — much worse — each time."
    assert "dash" in kinds(text)
    assert "dash" not in kinds(text, samples="Dashes — lots of them — are how I think — honestly — always — yes.")


def test_monotone_rhythm():
    same = " ".join(["The cat sat on the warm mat today."] * 10)
    assert "rhythm" in kinds(same)


def test_offsets_point_at_the_text():
    for t in find_tells(SLOP):
        if t.end > t.start:
            assert SLOP[t.start:t.end] == t.excerpt or t.kind in ("tail",)


def test_report_is_readable():
    assert "No AI tells" in report(HUMAN)
    assert "contrast" in report(SLOP)
