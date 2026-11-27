"""EPUB handler built on stdlib zipfile + HtmlHandler.

Translated: XHTML/HTML content documents inside the EPUB container.
Preserves ``mimetype`` as the first uncompressed ZIP entry, updates ``lang="id"`` on ``<html>``
and ``<dc:language>id</dc:language>`` in OPF when ``set_lang`` is enabled.
Refuses DRM-protected EPUBs before reading content.
"""

from __future__ import annotations

import html
import io
import re
import zipfile
from pathlib import Path

from id_translate.errors import InputError
from id_translate.formats.base import ApplyOptions, FormatHandler, RenderReport
from id_translate.formats.html import html_lang_edits, parse_html_segments
from id_translate.formats.textdoc import splice
from id_translate.protect import restore
from id_translate.safety import check_epub_drm
from id_translate.segments import Segment

DC_LANG_RE = re.compile(r"(<dc:language\b[^>]*>)(.*?)(</dc:language>)", re.I | re.S)


def _open_epub(path: Path) -> zipfile.ZipFile:
    check_epub_drm(path)
    try:
        return zipfile.ZipFile(path, "r")
    except zipfile.BadZipFile as exc:
        raise InputError(f"not a valid EPUB/ZIP file: {path}") from exc


def _xhtml_parts(names: list[str]) -> list[str]:
    return sorted(n for n in names if n.lower().endswith((".xhtml", ".html", ".htm")))


def _rewrite_epub(src_path: Path, updates: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with _open_epub(src_path) as zin, zipfile.ZipFile(buf, "w") as zout:
        infos = zin.infolist()
        # EPUB spec: mimetype must be first and uncompressed (ZIP_STORED).
        mime = [i for i in infos if i.filename == "mimetype"]
        rest = [i for i in infos if i.filename != "mimetype"]
        for info in mime + rest:
            data = updates.get(info.filename, zin.read(info.filename))
            new_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            new_info.compress_type = zipfile.ZIP_STORED if info.filename == "mimetype" else info.compress_type
            new_info.external_attr = info.external_attr
            zout.writestr(new_info, data)
    return buf.getvalue()


class EpubHandler(FormatHandler):
    name = "epub"
    extensions = (".epub",)

    def check_access(self, path: Path) -> None:
        check_epub_drm(path)

    def inspect_info(self, path: Path) -> dict:
        with _open_epub(path) as z:
            names = z.namelist()
            return {
                "parts": len(names),
                "xhtml_files": len(_xhtml_parts(names)),
                "opf_files": [n for n in names if n.lower().endswith(".opf")],
            }

    def unit_count(self, path: Path) -> tuple[int, str]:
        with _open_epub(path) as z:
            return len(_xhtml_parts(z.namelist())), "dokumen XHTML"

    def extract(self, path: Path) -> list[Segment]:
        segs: list[Segment] = []
        with _open_epub(path) as z:
            for part in _xhtml_parts(z.namelist()):
                text = z.read(part).decode("utf-8", "replace")
                part_segs = parse_html_segments(text, id_prefix="ep", loc_extra={"part": part})
                for s in part_segs:
                    s.id = f"ep{len(segs) + 1:04d}"
                    segs.append(s)
        return segs

    def render(self, path, segments, translations, options: ApplyOptions):
        by_part: dict[str, list[tuple[Segment, str]]] = {}
        for seg in segments:
            tr = translations.get(seg.id)
            if tr is None or tr == seg.text:
                continue
            by_part.setdefault(seg.loc["part"], []).append((seg, tr))

        updates: dict[str, bytes] = {}
        with _open_epub(path) as z:
            names = z.namelist()
            for part in _xhtml_parts(names):
                edits_list = by_part.get(part, [])
                if not edits_list and not options.set_lang:
                    continue
                text = z.read(part).decode("utf-8", "replace")
                edits: list[tuple[int, int, str]] = []
                for seg, tr in edits_list:
                    final = restore(tr, seg.protect)
                    rep = html.escape(final, quote=(seg.type == "attr"))
                    edits.append((seg.loc["start"], seg.loc["end"], rep))
                if options.set_lang:
                    edits.extend(html_lang_edits(text, options.lang))
                if edits:
                    updates[part] = splice(text, edits).encode("utf-8")

            if options.set_lang:
                for n in names:
                    if n.lower().endswith(".opf"):
                        opf = z.read(n).decode("utf-8", "replace")
                        new_opf = DC_LANG_RE.sub(rf"\g<1>{options.lang}\g<3>", opf)
                        if new_opf != opf:
                            updates[n] = new_opf.encode("utf-8")
        return _rewrite_epub(path, updates), RenderReport()
