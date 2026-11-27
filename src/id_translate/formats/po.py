"""GNU gettext PO/POT handler, edited in place.

Translated: ``msgstr`` / ``msgstr[N]`` values, extracted from ``msgid`` / ``msgid_plural``.
Never touched: comments, references, flags, ``msgctxt``, ``msgid``, header metadata
(except ``Language:`` / ``Plural-Forms:`` when ``set_lang`` is enabled).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from id_translate.formats.base import ApplyOptions
from id_translate.formats.textdoc import InPlaceTextHandler, TextDoc, line_spans, read_text_doc
from id_translate.protect import DEFAULT_OPTIONS, has_translatable_text, mask
from id_translate.segments import Segment

KW_RE = re.compile(r'^(msgctxt|msgid_plural|msgid|msgstr(?:\[\d+\])?)\s+("(?:\\.|[^"\\])*")\s*$')
CONT_RE = re.compile(r'^("(?:\\.|[^"\\])*")\s*$')
UNESC_MAP = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}


def _po_unescape(quoted: str) -> str:
    body = quoted[1:-1]
    return re.sub(r"\\([ntr\"\\])", lambda m: UNESC_MAP[m.group(1)], body)


def _po_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace("\n", "\\n")
    )


def _format_po_value(keyword: str, text: str, newline: str) -> str:
    if "\n" not in text:
        return f'{keyword} "{_po_escape(text)}"'
    parts = text.split("\n")
    lines = [f'{keyword} ""']
    for idx, part in enumerate(parts):
        suffix = "\\n" if idx < len(parts) - 1 else ""
        if part or suffix:
            lines.append(f'"{_po_escape(part)}{suffix}"')
    return newline.join(lines)


@dataclass
class _Field:
    keyword: str
    value: str
    start: int
    end: int


@dataclass
class _Entry:
    fields: dict[str, _Field]


def _parse_po(text: str) -> list[_Entry]:
    spans = line_spans(text)
    lines = [text[s:e] for s, e, _ in spans]
    n = len(lines)
    entries: list[_Entry] = []
    cur: dict[str, _Field] = {}
    i = 0
    while i < n:
        ln = lines[i].strip()
        if not ln:
            if cur:
                entries.append(_Entry(cur))
                cur = {}
            i += 1
            continue
        if ln.startswith("#"):
            i += 1
            continue
        m = KW_RE.match(ln)
        if not m:
            i += 1
            continue
        kw = m.group(1)
        f_start = spans[i][0]
        f_end = spans[i][1]
        parts = [_po_unescape(m.group(2))]
        j = i + 1
        while j < n:
            cm = CONT_RE.match(lines[j].strip())
            if not cm:
                break
            parts.append(_po_unescape(cm.group(1)))
            f_end = spans[j][1]
            j += 1
        cur[kw] = _Field(kw, "".join(parts), f_start, f_end)
        i = j
    if cur:
        entries.append(_Entry(cur))
    return entries


class PoHandler(InPlaceTextHandler):
    name = "po"
    extensions = (".po", ".pot")

    def parse(self, doc: TextDoc, path: Path) -> list[Segment]:
        segs: list[Segment] = []
        for entry in _parse_po(doc.text):
            mid = entry.fields.get("msgid")
            if mid is None:
                continue
            if mid.value == "" and "msgctxt" not in entry.fields:
                continue  # PO header
            ctx = entry.fields["msgctxt"].value if "msgctxt" in entry.fields else None
            if "msgstr" in entry.fields:
                target = entry.fields["msgstr"]
                src_text = mid.value
                masked, protect = mask(src_text, DEFAULT_OPTIONS)
                style = {"keyword": "msgstr"}
                if ctx:
                    style["context"] = ctx
                segs.append(
                    Segment(
                        id=f"po{len(segs) + 1:04d}",
                        type="message",
                        text=masked,
                        style=style,
                        loc={"start": target.start, "end": target.end, "keyword": "msgstr"},
                        protect=protect,
                        status="pending" if has_translatable_text(masked) else "skip",
                    )
                )
            else:
                plural_src = entry.fields.get("msgid_plural")
                for kw, target in sorted(entry.fields.items()):
                    if not kw.startswith("msgstr["):
                        continue
                    idx = int(kw[7:-1])
                    src_text = mid.value if idx == 0 or plural_src is None else plural_src.value
                    masked, protect = mask(src_text, DEFAULT_OPTIONS)
                    style = {"keyword": kw, "plural_index": idx}
                    if ctx:
                        style["context"] = ctx
                    segs.append(
                        Segment(
                            id=f"po{len(segs) + 1:04d}",
                            type="plural",
                            text=masked,
                            style=style,
                            loc={"start": target.start, "end": target.end, "keyword": kw},
                            protect=protect,
                            status="pending" if has_translatable_text(masked) else "skip",
                        )
                    )
        return segs

    def encode(self, seg: Segment, final_text: str, doc: TextDoc) -> str:
        return _format_po_value(seg.style["keyword"], final_text, doc.newline)

    def lang_edits(self, doc: TextDoc, options: ApplyOptions) -> list[tuple[int, int, str]]:
        for entry in _parse_po(doc.text):
            mid = entry.fields.get("msgid")
            mstr = entry.fields.get("msgstr")
            if mid and mid.value == "" and "msgctxt" not in entry.fields and mstr:
                hdr = mstr.value
                if "Language:" in hdr:
                    hdr = re.sub(r"Language:[^\n]*", f"Language: {options.lang}", hdr)
                if "Plural-Forms:" in hdr:
                    hdr = re.sub(r"Plural-Forms:[^\n]*", "Plural-Forms: nplurals=1; plural=0;", hdr)
                if hdr != mstr.value:
                    return [(mstr.start, mstr.end, _format_po_value("msgstr", hdr, doc.newline))]
                break
        return []

    def qa_text(self, path: Path) -> str:
        """Read translated msgstr when present, otherwise msgid."""
        lines: list[str] = []
        for entry in _parse_po(read_text_doc(path).text):
            mid = entry.fields.get("msgid")
            if mid is None or (mid.value == "" and "msgctxt" not in entry.fields):
                continue
            if "msgstr" in entry.fields:
                lines.append(entry.fields["msgstr"].value or mid.value)
            else:
                plural = entry.fields.get("msgid_plural")
                for kw, f in sorted(entry.fields.items()):
                    if kw.startswith("msgstr["):
                        idx = int(kw[7:-1])
                        fallback = mid.value if idx == 0 or plural is None else plural.value
                        lines.append(f.value or fallback)
        return "\n".join(lines)

    def unit_count(self, path: Path) -> tuple[int, str]:
        return len(self.extract(path)), "pesan"
