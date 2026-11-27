"""Android strings.xml handler, edited in place.

Translated: ``<string>``, ``<string-array>/<item>``, and ``<plurals>/<item>`` inner content
unless ``translatable="false"`` is set.
Never touched: ``name`` / ``quantity`` / ``translatable`` attributes, XML comments, inline
formatting tags (``<b>``, ``<i>``, ``<u>``, ``<xliff:g ...>``), placeholders.
Handles Android escaping (``\\'``, ``\\"``, ``\\@``, ``\\?``, XML entities).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from id_translate.errors import InputError
from id_translate.formats.textdoc import InPlaceTextHandler, TextDoc, read_text_doc
from id_translate.protect import MARKUP_OPTIONS, has_translatable_text, mask, restore
from id_translate.segments import Segment

STRING_RE = re.compile(r"<string\b([^>]*)>(.*?)</string>", re.S)
GROUP_RE = re.compile(r"<(string-array|plurals)\b([^>]*)>(.*?)</\1>", re.S)
ITEM_RE = re.compile(r"<item\b([^>]*)>(.*?)</item>", re.S)
ATTR_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
INLINE_TAG_RE = re.compile(r"</?[A-Za-z][\w:.-]*(?:\s+[^<>]*?)?\s*/?>")


def _attrs(raw: str) -> dict[str, str]:
    return dict(ATTR_RE.findall(raw))


def _android_unescape(raw: str) -> str:
    # Unescape Android backslash escapes and XML entities outside inline tags.
    parts = re.split(f"({INLINE_TAG_RE.pattern})", raw)
    out = []
    for idx, p in enumerate(parts):
        if idx % 2 == 1:
            out.append(p)
        else:
            p = (
                p.replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&quot;", '"')
                .replace("&apos;", "'")
                .replace("&amp;", "&")
            )
            p = re.sub(r"\\(['\"@?])", r"\1", p)
            out.append(p)
    return "".join(out)


def _android_escape(text: str) -> str:
    # Escape text segments while leaving inline XML tags intact.
    parts = re.split(f"({INLINE_TAG_RE.pattern})", text)
    out = []
    for idx, p in enumerate(parts):
        if idx % 2 == 1:
            out.append(p)
        else:
            p = p.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            p = p.replace("'", "\\'").replace('"', '\\"')
            if idx == 0 and p.startswith(("@", "?")):
                p = "\\" + p
            out.append(p)
    return "".join(out)


class AndroidXmlHandler(InPlaceTextHandler):
    name = "android-xml"
    extensions = (".xml",)

    def sniff(self, path: Path) -> bool:
        try:
            head = Path(path).read_bytes()[:2048].decode("utf-8", "ignore")
        except OSError:
            return False
        return "<resources" in head

    def parse(self, doc: TextDoc, path: Path) -> list[Segment]:
        try:
            ET.fromstring(doc.text)
        except ET.ParseError as exc:
            raise InputError(f"invalid Android XML: {exc}") from exc

        comments = [m.span() for m in COMMENT_RE.finditer(doc.text)]

        def in_comment(pos: int) -> bool:
            return any(a <= pos < b for a, b in comments)

        found: list[tuple[int, int, str, dict]] = []
        for m in STRING_RE.finditer(doc.text):
            if in_comment(m.start()):
                continue
            attrs = _attrs(m.group(1))
            if attrs.get("translatable", "true").lower() == "false":
                continue
            found.append((m.start(2), m.end(2), "string", {"name": attrs.get("name", "")}))

        for gm in GROUP_RE.finditer(doc.text):
            if in_comment(gm.start()):
                continue
            gtype = gm.group(1)
            gattrs = _attrs(gm.group(2))
            if gattrs.get("translatable", "true").lower() == "false":
                continue
            base = gm.start(3)
            for idx, im in enumerate(ITEM_RE.finditer(gm.group(3))):
                iattrs = _attrs(im.group(1))
                style = {"name": gattrs.get("name", ""), "index": idx}
                if "quantity" in iattrs:
                    style["quantity"] = iattrs["quantity"]
                found.append((base + im.start(2), base + im.end(2), gtype, style))

        found.sort(key=lambda x: x[0])
        segs: list[Segment] = []
        for s, e, kind, style in found:
            raw = doc.text[s:e]
            unesc = _android_unescape(raw)
            masked, protect = mask(unesc, MARKUP_OPTIONS)
            segs.append(
                Segment(
                    id=f"ax{len(segs) + 1:04d}",
                    type=kind,
                    text=masked,
                    style=style,
                    loc={"start": s, "end": e, **style},
                    protect=protect,
                    status="pending" if has_translatable_text(masked) else "skip",
                )
            )
        return segs

    def encode(self, seg: Segment, final_text: str, doc: TextDoc) -> str:
        return _android_escape(final_text)

    def extra_qa(self, source: Path, target: Path) -> tuple[list[str], list[str], list[str]]:
        try:
            s_root = ET.fromstring(read_text_doc(source).text)
            t_root = ET.fromstring(read_text_doc(target).text)
        except ET.ParseError as exc:
            return [f"Android XML hasil tidak valid: {exc}"], [], []
        s_names = [(el.tag, el.attrib.get("name")) for el in s_root]
        t_names = [(el.tag, el.attrib.get("name")) for el in t_root]
        if s_names != t_names:
            return ["Daftar elemen/atribut name di Android XML berubah."], [], []
        return [], [], [f"Struktur Android XML utuh ({len(s_names)} entri)."]

    def qa_text(self, path: Path) -> str:
        return "\n".join(restore(s.text, s.protect) for s in self.extract(path))
