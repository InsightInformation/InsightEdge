"""Find the patterns that make prose read as machine-written.

Plain heuristics, no API call: stock vocabulary, "it's not X, it's Y" framing, em-dash
habits, reflexive triads, participle tails, rhetorical-question reveals, sign-posting,
and sentences that are all the same length. When the user's own samples use a word or
habit freely, it's their voice, not a tell, so it isn't flagged.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import asdict, dataclass

# word -> plainer alternatives
STOCK_WORDS = {
    "delve": "dig into, look at", "delves": "digs into", "delving": "digging into",
    "tapestry": "mix, web", "testament": "proof, sign", "realm": "world, area",
    "landscape": "field, scene", "embark": "start", "embarked": "started",
    "foster": "build, grow", "fosters": "builds", "fostering": "building",
    "leverage": "use", "leveraging": "using", "robust": "strong, solid",
    "seamless": "smooth", "seamlessly": "smoothly", "pivotal": "key",
    "crucial": "important, key", "vibrant": "lively, busy", "intricate": "detailed, tangled",
    "nuanced": "subtle", "multifaceted": "complicated", "meticulous": "careful",
    "meticulously": "carefully", "elevate": "raise, improve", "elevates": "raises",
    "unlock": "open, get", "unleash": "release", "harness": "use", "resonate": "land, stick",
    "resonates": "lands", "profound": "deep", "profoundly": "deeply",
    "underscore": "show", "underscores": "shows", "showcase": "show", "showcases": "shows",
    "showcasing": "showing", "bustling": "busy", "beacon": "(say what it is)",
    "symphony": "(say what it is)", "labyrinth": "maze", "ever-evolving": "changing",
    "ever-changing": "changing", "game-changer": "(say what changed)",
    "game-changing": "(say what changed)", "cutting-edge": "new",
    "holistic": "whole", "synergy": "(cut)", "paradigm": "model, pattern",
    "transformative": "(say what changed)", "invaluable": "useful, essential",
    "commendable": "good", "noteworthy": "(cut)", "moreover": "and, also",
    "furthermore": "and, also", "additionally": "also", "notably": "(cut)",
    "navigate": "handle, get through", "navigating": "handling",
    "journey": "(say what actually happened)", "embrace": "accept, welcome",
    "embracing": "accepting", "enhance": "improve", "enhances": "improves",
    "utilize": "use", "utilizes": "uses", "myriad": "many", "plethora": "lots",
    "captivating": "(show it)", "breathtaking": "(show it)", "unwavering": "steady",
    "indelible": "lasting", "poignant": "(show it)", "palpable": "(show it)",
    "whimsical": "(show it)", "enigmatic": "strange", "tapestries": "(cut)",
    "interplay": "mix", "juxtaposition": "contrast", "serendipitous": "lucky",
    "boasts": "has", "nestled": "sits, is", "thrilled": "glad", "insightful": "smart",
}

STOCK_PHRASES = [
    (r"in today'?s (fast-paced|digital|modern|ever[- ]changing) world", "Stock opener. Start with the actual subject."),
    (r"it'?s (important|worth|crucial) (to note|noting|to remember|remembering)", "Sign-posting. Just say the thing."),
    (r"\b(in conclusion|in summary|to sum up|all in all)\b", "Essay-template closer. End on something concrete."),
    (r"\bat the end of the day\b", "Cliché closer."),
    (r"\bplays? an? (crucial|pivotal|vital|key|important) role\b", "Vague. Say what it actually does."),
    (r"\ba testament to\b", "Stock phrase."),
    (r"\b(rich|vibrant|intricate) tapestry\b", "Stock phrase."),
    (r"\bnavigat\w* the (complexities|challenges|intricacies)\b", "Stock phrase."),
    (r"\b(let'?s|let us) (dive|delve) (in|into)\b", "Presenter voice."),
    (r"\bdeep dive\b", "Business-speak."),
    (r"\bwhether you'?re an? .{3,40}? or an? ", "Brochure framing."),
    (r"\bserves? as a (reminder|testament)\b", "Stock phrase."),
    (r"\bstands? as a\b", "Stock phrase. Try 'is'."),
    (r"\bnot only\b.{3,80}?\bbut also\b", "Textbook construction."),
    (r"\bI hope this (helps|finds you)\b", "Assistant sign-off."),
    (r"\bfeel free to\b", "Assistant phrasing."),
    (r"\bthe (power|beauty|magic) of\b", "Vague abstraction."),
    (r"\bhere'?s the (thing|kicker|truth|catch)\b", "Faux-casual reveal."),
    (r"\bthe truth is\b", "Faux-candid reveal."),
    (r"\blet that sink in\b", "LinkedIn cliché."),
    (r"\band that'?s (okay|ok|alright)\b", "Therapy-speak closer."),
    (r"\b(great|excellent) question\b", "Assistant voice."),
    (r"^(certainly|absolutely|of course)[!,.]", "Assistant voice."),
    (r"\bin (a|this) world (where|of)\b", "Movie-trailer framing."),
    (r"\b(more|now) than ever\b", "Empty intensifier."),
    (r"\ba (reminder|testament) that\b", "Moralizing."),
    (r"\bmore than just an?\b", "Inflation. Say what it is."),
    (r"\b(unlock|unleash)(ing)? (the|your) (full )?potential\b", "Self-help cliché."),
    (r"\b(delicate|fine) balance\b", "Stock phrase."),
    (r"\bever-(evolving|changing|growing)\b", "Stock phrase."),
    (r"\bsend(s|ing)? shivers down\b", "Cliché."),
    (r"\ba (sense|feeling) of (belonging|wonder|purpose|community)\b", "Abstract. Show the moment instead."),
    (r"\b(ultimately|in the end),", "Tidy wrap-up. Does the piece need the moral?"),
    (r"\bthat'?s what (makes|made) .{2,40}? so\b", "Summing-up line."),
]

CONTRAST_PATTERNS = [
    r"\b(it|this|that)(?:'s| is| was|’s)(?: not| n't|n’t) (?:just |only |merely |about )?[^.;:!?]{1,60}[,;—–-]+\s*(?:it|this|that)(?:'s| is| was|’s)\b",
    r"\b(?:is|was|are|were)(?:n't|n’t| not) (?:just |only |merely )?about [^.;!?]{1,60}[.;,—–-]+\s*(?:it|this|that|they)(?:'s| is| was| are|’s)? ?(?:about\b)?",
    r"\bnot because [^.;!?]{1,60}, but because\b",
    r"\b(?:isn't|isn’t|wasn't|wasn’t|aren't|aren’t) [^.;!?]{1,40}\. (?:it|this|that|they)(?:'s| is| was| are|’s) ",
    r"\bnot (?:a|an) \w+[,;] (?:but )?(?:a|an) \w+\b",
    r"\bless (?:about|a matter of) [^.;!?]{1,40} (?:and|than) more (?:about|a matter of)\b",
]

REVEAL_RE = re.compile(
    r"(?:^|[.!]\s+)((?:the|my|his|her|their|our|and|but)?\s?(?:result|answer|catch|problem|kicker|twist|"
    r"secret|reason|lesson|takeaway|verdict|best part|worst part|irony|honestly|truth|point|outcome)\?)",
    re.I | re.M,
)
TAIL_RE = re.compile(
    r",\s(highlighting|underscoring|emphasizing|emphasising|showcasing|reflecting|symbolizing|"
    r"reinforcing|ensuring|fostering|cementing|solidifying|illustrating|demonstrating|signaling|"
    r"signalling|marking|reminding (?:us|me|them|everyone)|creating a|adding a|making it)\b",
    re.I,
)
TRIAD_RE = re.compile(r"\b(\w+(?:\s\w+)?), (\w+(?:\s\w+)?),? and (\w+(?:\s\w+)?)\b")
EM_DASH_RE = re.compile(r"—|–|\s--\s")
SENT_SPLIT_RE = re.compile(r"(?<=[.!?])[\"”’)]*\s+(?=[\"“‘(]?[A-Z0-9])")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")
LIST_LINE_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+", re.M)
HEADER_RE = re.compile(r"^#{1,6}\s", re.M)


@dataclass
class Tell:
    kind: str
    message: str
    excerpt: str
    start: int
    end: int
    severity: int = 2  # 1 = minor, 2 = noticeable, 3 = dead giveaway


def _words(text: str) -> list[str]:
    return WORD_RE.findall(text)


def _voice_vocab(samples: str) -> set[str]:
    """Words the user genuinely uses: those are theirs, not tells."""
    return {w.lower() for w in _words(samples)}


def _rate(pattern: re.Pattern, text: str) -> float:
    n = len(_words(text))
    return len(pattern.findall(text)) / n * 1000 if n else 0.0


def _strip_markdown(text: str) -> str:
    return re.sub(r"[*_`#>]", " ", text)


def find_tells(text: str, samples: str = "") -> list[Tell]:
    tells: list[Tell] = []
    lower = text.lower()
    voice = _voice_vocab(samples) if samples else set()

    for m in WORD_RE.finditer(text):
        w = m.group(0).lower().strip("'’")
        if w in STOCK_WORDS and w not in voice:
            tells.append(Tell("word", f"“{m.group(0)}” is a stock AI word. Try: {STOCK_WORDS[w]}.",
                              m.group(0), m.start(), m.end(), 2))

    for pattern, why in STOCK_PHRASES:
        for m in re.finditer(pattern, text, re.I | re.M):
            if samples and re.search(pattern, samples, re.I | re.M):
                continue
            tells.append(Tell("phrase", why, m.group(0), m.start(), m.end(), 3))

    for pattern in CONTRAST_PATTERNS:
        for m in re.finditer(pattern, text, re.I):
            tells.append(Tell("contrast", "“It's not X, it's Y” framing. The most recognizable AI move. "
                              "State the point directly.", m.group(0), m.start(), m.end(), 3))

    for m in REVEAL_RE.finditer(text):
        g = m.group(1)
        s = m.start(1)
        tells.append(Tell("reveal", "Rhetorical-question reveal (“The result?”). Just say it.", g, s, s + len(g), 3))

    for m in TAIL_RE.finditer(text):
        end = text.find(".", m.end())
        end = end if 0 <= end - m.start() < 120 else m.end()
        tells.append(Tell("tail", f"Trailing “, {m.group(1)}…” clause that explains the sentence's significance. "
                          "Cut it or make it its own sentence.", text[m.start():end], m.start(), end, 2))

    # Em dashes: flag when used more than the user does (or at all heavily with no samples).
    dashes = list(EM_DASH_RE.finditer(text))
    words = len(_words(text))
    if dashes and words:
        mine = _rate(EM_DASH_RE, samples) if samples else 0.0
        theirs = len(dashes) / words * 1000
        if theirs > max(4.0, mine * 1.5):
            for m in dashes:
                tells.append(Tell("dash", f"Em dash #{dashes.index(m) + 1} of {len(dashes)}. Heavy dash use is a strong AI "
                                  "signal. Use a period, comma, or parentheses.", m.group(0), m.start(), m.end(), 2))

    # Reflexive triads ("clear, concise, and compelling").
    triads = [m for m in TRIAD_RE.finditer(text) if len(m.group(0)) < 70]
    if words and len(triads) / max(words, 1) * 1000 > (_rate(TRIAD_RE, samples) * 1.5 if samples else 0) + 4:
        for m in triads:
            tells.append(Tell("triad", "Another list of three. Groups of three on autopilot read as generated. "
                              "Use two, or one good one.", m.group(0), m.start(), m.end(), 1))

    # Rhythm: sentences that are all about the same length.
    body = _strip_markdown(text)
    sentences = [s for s in SENT_SPLIT_RE.split(body) if len(_words(s)) >= 2]
    if len(sentences) >= 8:
        lengths = [len(_words(s)) for s in sentences]
        mean = statistics.mean(lengths)
        cv = statistics.pstdev(lengths) / mean if mean else 1
        if cv < 0.38:
            tells.append(Tell("rhythm", f"Monotone rhythm: most sentences run {int(mean)}±{int(statistics.pstdev(lengths))} "
                              "words. Mix in a very short one and a long, winding one.", "", 0, 0, 2))

    # Over-formatting prose.
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) >= 6:
        listy = len(LIST_LINE_RE.findall(text)) + len(HEADER_RE.findall(text))
        if listy / len(lines) > 0.4 and not (samples and LIST_LINE_RE.search(samples)):
            tells.append(Tell("format", "Mostly bullets and headers. Personal writing lives in paragraphs.", "", 0, 0, 2))

    # Paragraph closers that land on a moral.
    for m in re.finditer(r"(?:^|\n)[^\n]*?([^.!?\n]{0,80}\b(?:remind(?:s|ed)? (?:us|me)|what (?:truly|really) matters|"
                         r"that'?s the (?:real )?(?:lesson|point)|the real (?:lesson|gift|takeaway))[^.!?\n]*[.!])", text, re.I):
        tells.append(Tell("moral", "Paragraph ends on a moral. Trust the reader and cut it.",
                          m.group(1).strip(), m.start(1), m.end(1), 2))

    if lower.lstrip().startswith(("here's a draft", "here is a draft", "sure", "certainly", "absolutely")):
        tells.append(Tell("preamble", "Assistant preamble before the piece.", text[:40], 0, min(40, len(text)), 3))

    # De-duplicate overlapping findings, keep the most severe.
    # Drop a finding that sits inside a more severe (or same-kind) one.
    tells.sort(key=lambda t: (-t.severity, t.start))
    out: list[Tell] = []
    for t in tells:
        if t.end and any(o.end and o.start <= t.start and t.end <= o.end and (o.severity > t.severity or o.kind == t.kind)
                         for o in out):
            continue
        out.append(t)
    return sorted(out, key=lambda t: (t.start, -t.severity))


def score(text: str, tells: list[Tell]) -> int:
    """0-100, higher = reads more human. Penalty scales with density, not raw count."""
    words = max(len(_words(text)), 1)
    weight = sum(t.severity for t in tells)
    density = weight / words * 100  # severity points per 100 words
    return max(0, min(100, round(100 - density * 18)))


def analyze(text: str, samples: str = "") -> dict:
    tells = find_tells(text, samples)
    return {
        "score": score(text, tells),
        "words": len(_words(text)),
        "tells": [asdict(t) for t in tells],
    }


def report(text: str, samples: str = "", limit: int = 25) -> str:
    """A compact plain-text report for the agent."""
    result = analyze(text, samples)
    tells = result["tells"]
    if not tells:
        return f"Human-sounding score {result['score']}/100. No AI tells found."
    lines = [f"Human-sounding score {result['score']}/100. {len(tells)} tell(s) found (fix the severity-3 ones first):"]
    for t in sorted(tells, key=lambda t: -t["severity"])[:limit]:
        ex = f" “{t['excerpt'][:90]}”" if t["excerpt"] else ""
        lines.append(f"- [{t['severity']}] {t['kind']}:{ex} {t['message']}")
    if len(tells) > limit:
        lines.append(f"- …and {len(tells) - limit} more.")
    return "\n".join(lines)
