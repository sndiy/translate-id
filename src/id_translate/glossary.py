"""Glossary parsing, candidate-term scanning, and glossary compliance checks.

Glossary Markdown format (same as skills/translate-id/assets/glossary-template.md):
    ## Glosarium            table rows: | EN | ID | note |   (alternatives separated by "/")
    ## Terjemahan terlarang bullets:    - wrong → right
    ## Dikecualikan ...     bullets:    - term kept in English
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

EN_STOP = set(
    "the and of to is that with for are you this it as be was were by on at from or an not have has had "
    "they their there which will would can could should our your we he she his her but if so than then "
    "these those into about also more most such what when where who whom why how been being do does did "
    "done just only over under between each other any some all a in".split()
)


@dataclass
class Glossary:
    pairs: list[tuple[str, str]] = field(default_factory=list)
    forbidden: list[tuple[str, str]] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)


def parse_glossary(path: Path) -> Glossary:
    g = Glossary()
    section = ""
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            section = line.lower()
            continue
        stripped = line.strip()
        if "terlarang" in section or "forbidden" in section:
            m = re.match(r"[-*]\s*(.+?)\s*(?:→|->)\s*(.+)", stripped)
            if m:
                g.forbidden.append((m.group(1).strip(" `\"'"), m.group(2).strip(" `\"'")))
        elif "dikecualikan" in section or "excluded" in section:
            m = re.match(r"[-*]\s*(.+)", stripped)
            if m and not m.group(1).startswith("<"):
                g.excluded.append(m.group(1).strip(" `\"'"))
        elif ("glosarium" in section or "glossary" in section) and stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= 2 and cells[0] and not set(cells[0]) <= set("-: "):
                if cells[0].lower() in {"en", "inggris", "english", "sumber", "source"}:
                    continue
                g.pairs.append((cells[0], cells[1]))
    return g


def count_term(term: str, text: str) -> int:
    """Case-insensitive whole-word count ("art" does not match "part")."""
    return len(re.findall(rf"(?<!\w){re.escape(term.lower())}(?!\w)", text.lower()))


def scan_candidates(texts: Iterable[str], top: int = 40, min_count: int = 2) -> list[tuple[str, int]]:
    """Heuristic term candidates: capitalized phrases, acronyms, frequent content bigrams."""
    counts: Counter[str] = Counter()
    cap_phrase = re.compile(r"\b[A-Z][\w'-]+(?:\s+(?:of|and|for|the|[A-Z][\w'-]+))*\s+[A-Z][\w'-]+\b")
    acronym = re.compile(r"\b[A-Z]{2,}[0-9]*\b")
    word = re.compile(r"[A-Za-z][A-Za-z'-]+")
    for t in texts:
        for m in cap_phrase.finditer(t):
            counts[m.group(0)] += 1
        for m in acronym.finditer(t):
            counts[m.group(0)] += 1
        words = [w.lower() for w in word.findall(t)]
        for a, b in zip(words, words[1:]):
            if a not in EN_STOP and b not in EN_STOP and len(a) > 2 and len(b) > 2:
                counts[f"{a} {b}"] += 1
    return [(k, v) for k, v in counts.most_common() if v >= min_count][:top]


def check_pairs(glossary: Glossary, items: Iterable[tuple[str, str, str]]) -> list[str]:
    """items: (segment_id, source_text, translated_text). Returns issue strings."""
    issues: list[str] = []
    for sid, src, tgt in items:
        for bad, good in glossary.forbidden:
            if count_term(bad, tgt):
                issues.append(f"ERROR {sid}: forbidden translation {bad!r} (use {good!r})")
        for en, idn in glossary.pairs:
            alts = [a.strip() for a in idn.split("/") if a.strip()]
            if count_term(en, src) and not any(count_term(a, tgt) for a in alts):
                issues.append(f"WARN {sid}: source has {en!r} but translation lacks {idn!r}")
    return issues
