"""HTML/XHTML handler using stdlib HTMLParser for exact in-place text and attribute edits.

Translated: text nodes (outside code/script/style/pre/kbd/svg/math) and display attributes
(``alt``, ``title``, ``placeholder``, ``aria-label``, and ``<meta name="description" content>``).
Never touched: tags, ids, classes, href/src, scripts, styles, code blocks, comments.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from pathlib import Path

from id_translate.formats.base import ApplyOptions
from id_translate.formats.textdoc import InPlaceTextHandler, TextDoc, line_spans
from id_translate.protect import DEFAULT_OPTIONS, has_translatable_text, mask
from id_translate.segments import Segment

SKIP_TAGS = {"script", "style", "code", "pre", "kbd", "samp", "var", "textarea", "svg", "math"}
DISPLAY_ATTRS = {"alt", "title", "placeholder", "aria-label"}
META_NAMES = {"description", "og:title", "og:description", "twitter:title", "twitter:description"}
HTML_TAG_RE = re.compile(r"<html\b([^>]*)>", re.I | re.S)
LANG_ATTR_RE = re.compile(r'\blang\s*=\s*(?:"[^"]*"|\'[^\']*\')', re.I)


def _find_attr_value_span(tag_text: str, attr: str) -> tuple[int, int] | None:
    """Return (inner_start, inner_end) relative to ``tag_text`` for ``attr="..."`` or ``attr='...'``."""
    m = re.search(rf"""\b{re.escape(attr)}\s*=\s*(?:"([^"]*)"|'([^']*)')""", tag_text, re.I | re.S)
    if not m:
        return None
    grp = 1 if m.group(1) is not None else 2
    return m.start(grp), m.end(grp)


class _HtmlScanner(HTMLParser):
    def __init__(self, text: str):
        super().__init__(convert_charrefs=False)
        self.text = text
        self.line_starts = [s for s, _, _ in line_spans(text)]
        self.skip_depth = 0
        self.items: list[tuple[int, int, str, str, str]] = []  # (start, end, kind, raw, tag)

    def _offset(self) -> int:
        line, col = self.getpos()
        if line - 1 < len(self.line_starts):
            return self.line_starts[line - 1] + col
        return len(self.text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        self._scan_attrs(t, attrs)
        if t in SKIP_TAGS:
            self.skip_depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._scan_attrs(tag.lower(), attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1

    def _scan_attrs(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw_tag = self.get_starttag_text()
        if not raw_tag:
            return
        base = self._offset()
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        wanted = [a for a in DISPLAY_ATTRS if a in attr_map and attr_map[a].strip()]
        if tag == "meta":
            meta_key = (attr_map.get("name") or attr_map.get("property") or "").lower()
            if meta_key in META_NAMES and attr_map.get("content", "").strip():
                wanted.append("content")
        for attr in wanted:
            sp = _find_attr_value_span(raw_tag, attr)
            if sp:
                s, e = base + sp[0], base + sp[1]
                self.items.append((s, e, "attr", self.text[s:e], f"{tag}@{attr}"))

    def handle_data(self, data: str) -> None:
        if self.skip_depth > 0 or not data.strip():
            return
        base = self._offset()
        # Verify exact match (HTMLParser may split around charrefs/entityrefs)
        lead = len(data) - len(data.lstrip())
        trail = len(data) - len(data.rstrip())
        s = base + lead
        e = base + len(data) - trail
        if e > s and self.text[s:e] == data.strip():
            self.items.append((s, e, "text", self.text[s:e], "text"))

    def handle_entityref(self, name: str) -> None:
        # Merge adjacent entity references with text node by skipping separate emission.
        pass

    def handle_charref(self, name: str) -> None:
        pass


def parse_html_segments(text: str, id_prefix: str = "ht", loc_extra: dict | None = None) -> list[Segment]:
    """Extract translatable text nodes and display attributes from HTML/XHTML source."""
    # Combine contiguous data + entityref/charref spans by scanning raw tags.
    scanner = _HtmlScanner(text)
    scanner.feed(text)
    scanner.close()

    # Merge contiguous text items separated only by HTML entities (e.g. "Salt &amp; pepper").
    merged: list[tuple[int, int, str, str, str]] = []
    entity_only = re.compile(r"^(?:&(?:#\d+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]*);|\s)+$")
    for item in sorted(scanner.items, key=lambda x: x[0]):
        if (
            merged
            and merged[-1][2] == "text"
            and item[2] == "text"
            and entity_only.match(text[merged[-1][1] : item[0]])
        ):
            prev = merged[-1]
            merged[-1] = (prev[0], item[1], "text", text[prev[0] : item[1]], "text")
        else:
            merged.append(item)

    segs: list[Segment] = []
    extra = loc_extra or {}
    for s, e, kind, raw, tag in merged:
        unesc = html.unescape(raw)
        masked, protect = mask(unesc, DEFAULT_OPTIONS)
        loc = {"start": s, "end": e, **extra}
        segs.append(
            Segment(
                id=f"{id_prefix}{len(segs) + 1:04d}",
                type=kind,
                text=masked,
                style={"tag": tag},
                loc=loc,
                protect=protect,
                status="pending" if has_translatable_text(masked) else "skip",
            )
        )
    return segs


def html_lang_edits(text: str, lang: str) -> list[tuple[int, int, str]]:
    m = HTML_TAG_RE.search(text)
    if not m:
        return []
    attrs = m.group(1)
    lm = LANG_ATTR_RE.search(attrs)
    if lm:
        s = m.start(1) + lm.start()
        e = m.start(1) + lm.end()
        return [(s, e, f'lang="{lang}"')]
    ins = m.start(1)
    return [(ins, ins, f' lang="{lang}"')]


class HtmlHandler(InPlaceTextHandler):
    name = "html"
    extensions = (".html", ".htm", ".xhtml")

    def parse(self, doc: TextDoc, path: Path) -> list[Segment]:
        return parse_html_segments(doc.text)

    def encode(self, seg: Segment, final_text: str, doc: TextDoc) -> str:
        return html.escape(final_text, quote=(seg.type == "attr"))

    def lang_edits(self, doc: TextDoc, options: ApplyOptions) -> list[tuple[int, int, str]]:
        return html_lang_edits(doc.text, options.lang)
