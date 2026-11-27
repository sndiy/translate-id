"""Shared helpers for text-based formats edited in place by character offsets.

Invariant: anything outside a translated segment's span is copied byte-for-byte, and a
segment whose translation equals its source text keeps its original bytes.
"""

from __future__ import annotations

import codecs
import logging
from dataclasses import dataclass
from pathlib import Path

from id_translate.errors import InputError, ValidationError
from id_translate.formats.base import ApplyOptions, FormatHandler, RenderReport
from id_translate.protect import restore
from id_translate.segments import Segment

log = logging.getLogger("id_translate")


@dataclass
class TextDoc:
    text: str  # decoded text with original newlines
    encoding: str
    bom: bytes
    newline: str


def read_text_doc(path: Path) -> TextDoc:
    raw = Path(path).read_bytes()
    for bom, enc in (
        (codecs.BOM_UTF8, "utf-8"),
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
    ):
        if raw.startswith(bom):
            body = raw[len(bom) :]
            text = body.decode(enc)
            break
    else:
        bom = b""
        try:
            text, enc = raw.decode("utf-8"), "utf-8"
        except UnicodeDecodeError:
            text, enc = raw.decode("cp1252"), "cp1252"
            log.warning("%s is not UTF-8; decoded as cp1252", path)
    newline = "\r\n" if "\r\n" in text else "\n"
    return TextDoc(text=text, encoding=enc, bom=bom, newline=newline)


def encode_text_doc(doc: TextDoc, text: str) -> bytes:
    try:
        return doc.bom + text.encode(doc.encoding)
    except UnicodeEncodeError as exc:
        raise ValidationError(f"translated text cannot be encoded as {doc.encoding}: {exc}") from exc


def splice(text: str, edits: list[tuple[int, int, str]]) -> str:
    """Apply non-overlapping (start, end, replacement) edits."""
    out: list[str] = []
    pos = 0
    for s, e, rep in sorted(edits, key=lambda x: (x[0], x[1])):
        if s < pos:
            raise ValidationError(f"overlapping edits at offset {s}")
        out.append(text[pos:s])
        out.append(rep)
        pos = e
    out.append(text[pos:])
    return "".join(out)


def to_segment_text(raw: str) -> str:
    return raw.replace("\r\n", "\n")


class InPlaceTextHandler(FormatHandler):
    """Base for formats whose segments are character spans of the decoded document.

    Subclasses implement ``parse`` returning segments with ``loc = {"start": int, "end": int}``
    and may override ``encode`` (escaping) and ``lang_edits`` (language markers).
    """

    stability = "beta"

    def parse(self, doc: TextDoc, path: Path) -> list[Segment]:
        raise NotImplementedError

    def encode(self, seg: Segment, final_text: str, doc: TextDoc) -> str:
        prefix = seg.style.get("cont_prefix", "")
        return final_text.replace("\n", doc.newline + prefix)

    def lang_edits(self, doc: TextDoc, options: ApplyOptions) -> list[tuple[int, int, str]]:
        return []

    def extract(self, path: Path) -> list[Segment]:
        try:
            doc = read_text_doc(path)
        except UnicodeDecodeError as exc:
            raise InputError(f"cannot decode {path}: {exc}") from exc
        return self.parse(doc, Path(path))

    def render(self, path, segments, translations, options):
        doc = read_text_doc(path)
        edits: list[tuple[int, int, str]] = []
        report = RenderReport()
        for seg in segments:
            tr = translations.get(seg.id)
            if tr is None or tr == seg.text:
                continue  # untouched: original bytes are kept
            final = restore(tr, seg.protect)
            edits.append((seg.loc["start"], seg.loc["end"], self.encode(seg, final, doc)))
        if options.set_lang:
            edits.extend(self.lang_edits(doc, options))
        return encode_text_doc(doc, splice(doc.text, edits)), report


def line_spans(text: str) -> list[tuple[int, int, int]]:
    """Return (start, end_without_newline, end_with_newline) for every line."""
    spans = []
    pos = 0
    n = len(text)
    while pos < n:
        nl = text.find("\n", pos)
        if nl == -1:
            spans.append((pos, n, n))
            break
        end = nl - 1 if nl > pos and text[nl - 1] == "\r" else nl
        spans.append((pos, end, nl + 1))
        pos = nl + 1
    return spans
