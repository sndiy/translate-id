"""Protect tokens: mask placeholders/URLs/code as ``⟦P1⟧`` before translation, restore after.

Token grammar: ``⟦`` + optional ``/`` + uppercase tag + number + ``⟧``.
    ⟦P3⟧          protected literal (restored from the segment's ``protect`` map)
    ⟦S2⟧…⟦/S2⟧    formatting span (handled by the format handler, e.g. OOXML runs)
    ⟦F1⟧          fixed inline object (tab, line break) handled by the format handler
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

TOKEN_RE = re.compile(r"⟦/?[A-Z]+\d+⟧")
LETTER_RE = re.compile(r"[^\W\d_]")

URL_RE = re.compile(r"(?:https?|ftp)://[^\s<>\"'`]+|www\.[A-Za-z0-9-]+\.[^\s<>\"'`]+")
EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
PLACEHOLDER_RES = (
    re.compile(r"\{\{[^{}]*\}\}"),  # {{name}}
    re.compile(r"\$\{[^{}]*\}"),  # ${name}
    re.compile(r"\{[A-Za-z0-9_.:-]*\}"),  # {name} {0} {}
    re.compile(r"%\([A-Za-z0-9_]+\)[-+#0]*\d*(?:\.\d+)?[sdifr]"),  # %(name)s
    re.compile(r"%(?:\d+\$)?[-+#0]*\d*(?:\.\d+)?(?:ll|l|h)?[sdifuxXeEgGc@]"),  # %s %1$s %.2f
    re.compile(r"(?<![\w$])\$[A-Za-z_][A-Za-z0-9_]*"),  # $var
)
TAG_RE = re.compile(r"</?[A-Za-z][\w:.-]*(?:\s+[^<>]*?)?\s*/?>")
WIN_PATH_RE = re.compile(r"(?<![\w])[A-Za-z]:\\[^\s<>\"'|*?]+")
POSIX_PATH_RE = re.compile(r"(?<![\w/.~])(?:~|\.{1,2})?/(?:[\w.-]+/)+[\w.-]*")
ICU_HEAD_RE = re.compile(r"\s*[A-Za-z0-9_]+\s*,\s*(plural|select|selectordinal)\s*,\s*(?:offset:\d+\s*)?")
ICU_SELECTOR_RE = re.compile(r"\s*(=\d+|[A-Za-z_][\w-]*)\s*\{")
URL_TRAIL = ".,;:!?'\"]}>"


@dataclass(frozen=True)
class MaskOptions:
    urls: bool = True
    emails: bool = True
    placeholders: bool = True
    icu: bool = True
    tags: bool = False
    paths: bool = True


DEFAULT_OPTIONS = MaskOptions()
MARKUP_OPTIONS = MaskOptions(tags=True)


class TokenError(ValueError):
    pass


def _match_brace(text: str, start: int, end: int | None = None) -> int | None:
    end = len(text) if end is None else end
    depth = 0
    for k in range(start, end):
        c = text[k]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return k
    return None


def _icu_spans(text: str, lo: int = 0, hi: int | None = None) -> list[tuple[int, int]]:
    hi = len(text) if hi is None else hi
    spans: list[tuple[int, int]] = []
    i = lo
    while i < hi:
        if text[i] == "{":
            j = _match_brace(text, i, hi)
            if j is None:
                i += 1
                continue
            m = ICU_HEAD_RE.match(text, i + 1, j)
            if m:
                spans.extend(_icu_complex(text, i, j, m))
                i = j + 1
                continue
        i += 1
    return spans


def _icu_complex(text: str, i: int, j: int, m: re.Match) -> list[tuple[int, int]]:
    plural = m.group(1) in {"plural", "selectordinal"}
    spans = [(i, m.end())]
    k = m.end()
    while k < j:
        sm = ICU_SELECTOR_RE.match(text, k, j)
        if not sm:
            break
        brace = sm.end() - 1
        close = _match_brace(text, brace, j)
        if close is None:
            return [(i, j + 1)]
        spans.append((k, sm.end()))
        inner_lo, inner_hi = sm.end(), close
        spans.extend(_icu_spans(text, inner_lo, inner_hi))
        if plural:
            depth = 0
            for q in range(inner_lo, inner_hi):
                c = text[q]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                elif c == "#" and depth == 0:
                    spans.append((q, q + 1))
        spans.append((close, close + 1))
        k = close + 1
    if text[k:j].strip():
        return [(i, j + 1)]  # malformed: protect the whole expression
    spans.append((k, j + 1))
    return spans


def _trim_url(text: str, s: int, e: int) -> int:
    while e > s and text[e - 1] in URL_TRAIL:
        e -= 1
    if text[e - 1 : e] == ")" and "(" not in text[s:e]:
        e -= 1
    return e


def find_protected_spans(
    text: str,
    options: MaskOptions = DEFAULT_OPTIONS,
    extra_spans: Iterable[tuple[int, int]] = (),
    extra_patterns: Sequence[re.Pattern] = (),
) -> list[tuple[int, int]]:
    """Return sorted, non-overlapping spans that must not be translated."""
    primary: list[tuple[int, int]] = [(s, e) for s, e in extra_spans if e > s]
    primary += [(m.start(), m.end()) for m in re.finditer("[⟦⟧]", text)]
    if options.icu:
        primary += _icu_spans(text)
    secondary: list[tuple[int, int]] = []
    for pat in extra_patterns:
        secondary += [(m.start(), m.end()) for m in pat.finditer(text)]
    if options.urls:
        for m in URL_RE.finditer(text):
            e = _trim_url(text, m.start(), m.end())
            if e > m.start():
                secondary.append((m.start(), e))
    if options.emails:
        secondary += [(m.start(), m.end()) for m in EMAIL_RE.finditer(text)]
    if options.tags:
        secondary += [(m.start(), m.end()) for m in TAG_RE.finditer(text)]
    if options.paths:
        for pat in (WIN_PATH_RE, POSIX_PATH_RE):
            for m in pat.finditer(text):
                e = m.end()
                while e > m.start() and text[e - 1] in ".,;:!?":
                    e -= 1
                if e > m.start():
                    secondary.append((m.start(), e))
    if options.placeholders:
        for pat in PLACEHOLDER_RES:
            secondary += [(m.start(), m.end()) for m in pat.finditer(text)]

    chosen: list[tuple[int, int]] = []

    def overlaps(s: int, e: int) -> bool:
        return any(s < ce and cs < e for cs, ce in chosen)

    for s, e in sorted(set(primary), key=lambda x: (x[0], -(x[1] - x[0]))):
        if not overlaps(s, e):
            chosen.append((s, e))
    for s, e in sorted(set(secondary), key=lambda x: (x[0], -(x[1] - x[0]))):
        if not overlaps(s, e):
            chosen.append((s, e))
    chosen.sort()
    merged: list[tuple[int, int]] = []
    for s, e in chosen:
        if merged and merged[-1][1] == s:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return merged


def mask(
    text: str,
    options: MaskOptions = DEFAULT_OPTIONS,
    *,
    start: int = 1,
    extra_spans: Iterable[tuple[int, int]] = (),
    extra_patterns: Sequence[re.Pattern] = (),
    protect: dict[str, str] | None = None,
) -> tuple[str, dict[str, str]]:
    """Replace protected spans with ``⟦Pn⟧`` tokens. Returns (masked_text, protect_map)."""
    protect = {} if protect is None else protect
    n = start
    out: list[str] = []
    pos = 0
    for s, e in find_protected_spans(text, options, extra_spans, extra_patterns):
        out.append(text[pos:s])
        while f"⟦P{n}⟧" in protect:
            n += 1
        tok = f"⟦P{n}⟧"
        protect[tok] = text[s:e]
        out.append(tok)
        n += 1
        pos = e
    out.append(text[pos:])
    return "".join(out), protect


def restore(text: str, protect: dict[str, str]) -> str:
    """Replace ``⟦Pn⟧`` tokens with their original literal. Other tokens are left alone."""
    return TOKEN_RE.sub(lambda m: protect.get(m.group(0), m.group(0)), text)


def check_tokens(source: str, translated: str) -> list[str]:
    """Compare token multisets and span order. Returns a list of problems (empty = OK)."""
    problems: list[str] = []
    src = Counter(TOKEN_RE.findall(source))
    tgt = Counter(TOKEN_RE.findall(translated))
    missing = src - tgt
    extra = tgt - src
    if missing:
        problems.append("missing tokens: " + " ".join(sorted(missing.elements())))
    if extra:
        problems.append("unexpected/duplicated tokens: " + " ".join(sorted(extra.elements())))
    if not problems:
        positions = {m.group(0): m.start() for m in TOKEN_RE.finditer(translated)}
        for tok, pos in positions.items():
            if tok.startswith("⟦/"):
                opener = "⟦" + tok[2:]
                if opener in positions and positions[opener] > pos:
                    problems.append(f"closing token {tok} appears before {opener}")
    return problems


def has_translatable_text(masked: str) -> bool:
    return bool(LETTER_RE.search(TOKEN_RE.sub("", masked)))


def strip_tokens(text: str) -> str:
    return TOKEN_RE.sub("", text)
