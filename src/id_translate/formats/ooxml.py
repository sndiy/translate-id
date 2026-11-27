"""OOXML handlers (DOCX, PPTX, XLSX) built directly on zipfile + lxml.

Only text XML parts are modified; media, styles, themes, relationships, charts, animations,
and formulas are copied untouched. Encrypted Office files (OLE compound containers) are
refused before opening.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from id_translate.errors import InputError
from id_translate.formats.base import ApplyOptions, FormatHandler, RenderReport
from id_translate.protect import DEFAULT_OPTIONS, has_translatable_text, mask, restore
from id_translate.safety import check_ole_encrypted
from id_translate.segments import Segment

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
S_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

SPAN_RE = re.compile(r"⟦S(\d+)⟧(.*?)⟦/S\1⟧", re.S)


def _natural_key(name: str) -> list[int | str]:
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", name)]


def _open_zip(path: Path) -> zipfile.ZipFile:
    check_ole_encrypted(path)
    try:
        return zipfile.ZipFile(path, "r")
    except zipfile.BadZipFile as exc:
        raise InputError(f"not a valid OOXML/ZIP file: {path}") from exc


def _rewrite_zip(src_path: Path, updates: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with _open_zip(src_path) as zin, zipfile.ZipFile(buf, "w") as zout:
        for info in zin.infolist():
            data = updates.get(info.filename, zin.read(info.filename))
            new_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            new_info.compress_type = info.compress_type
            new_info.external_attr = info.external_attr
            zout.writestr(new_info, data)
    return buf.getvalue()


def _rpr_sig(run, rpr_tag: str) -> bytes:
    from lxml import etree

    rpr = run.find(rpr_tag)
    return etree.tostring(rpr) if rpr is not None else b""


def _group_runs(runs: list, rpr_tag: str, t_tag: str) -> list[list]:
    """Group consecutive runs sharing the same parent and formatting properties."""
    groups: list[list] = []
    prev_key = None
    for r in runs:
        t_el = r.find(t_tag)
        if t_el is None or t_el.text is None:
            continue
        key = (r.getparent(), _rpr_sig(r, rpr_tag))
        if groups and key == prev_key:
            groups[-1].append(r)
        else:
            groups.append([r])
            prev_key = key
    return groups


def _encode_groups(groups: list[list], t_tag: str) -> tuple[str, dict[str, str], int]:
    """Build masked text with ``⟦Sn⟧...⟦/Sn⟧`` tokens for styled run groups."""
    texts = ["".join((r.find(t_tag).text or "") for r in g) for g in groups]
    if len(groups) == 1:
        masked, protect = mask(texts[0], DEFAULT_OPTIONS)
        return masked, protect, 1
    protect: dict[str, str] = {}
    parts: list[str] = []
    next_p = 1
    for idx, txt in enumerate(texts, 1):
        m, protect = mask(txt, DEFAULT_OPTIONS, start=next_p, protect=protect)
        next_p = len(protect) + 1
        parts.append(f"⟦S{idx}⟧{m}⟦/S{idx}⟧")
    return "".join(parts), protect, len(groups)


def _apply_groups(
    groups: list[list],
    t_tag: str,
    translated: str,
    protect: dict[str, str],
    set_lang_fn=None,
) -> None:
    """Write translated text back into grouped runs, preserving formatting on each group."""
    if len(groups) == 1:
        final = restore(translated, protect)
        _set_group_text(groups[0], t_tag, final, set_lang_fn)
        return

    found: dict[int, str] = {}
    for m in SPAN_RE.finditer(translated):
        idx = int(m.group(1))
        found[idx] = restore(m.group(2), protect)

    if len(found) == len(groups):
        for idx, g in enumerate(groups, 1):
            _set_group_text(g, t_tag, found[idx], set_lang_fn)
    else:
        # Fallback: strip span markers and place all text in the first group.
        plain = restore(re.sub(r"⟦/?S\d+⟧", "", translated), protect)
        _set_group_text(groups[0], t_tag, plain, set_lang_fn)
        for g in groups[1:]:
            _set_group_text(g, t_tag, "", None)


def _set_group_text(group: list, t_tag: str, text: str, set_lang_fn=None) -> None:
    anchor = group[0]
    t_el = anchor.find(t_tag)
    if t_el is not None:
        t_el.text = text
        if text != text.strip() or "  " in text:
            t_el.set(XML_SPACE, "preserve")
    if set_lang_fn is not None:
        set_lang_fn(anchor)
    for extra in group[1:]:
        et = extra.find(t_tag)
        if et is not None:
            et.text = ""


class _OoxmlBase(FormatHandler):
    requires = ("lxml",)
    extra = "office"

    def check_access(self, path: Path) -> None:
        check_ole_encrypted(path)


# --------------------------------------------------------------------------- DOCX


class DocxHandler(_OoxmlBase):
    name = "docx"
    extensions = (".docx",)

    @staticmethod
    def _target_parts(names: list[str]) -> list[str]:
        pats = (
            r"^word/document\.xml$",
            r"^word/header\d*\.xml$",
            r"^word/footer\d*\.xml$",
            r"^word/footnotes\.xml$",
            r"^word/endnotes\.xml$",
            r"^word/comments\.xml$",
        )
        matched = [n for n in names if any(re.match(p, n) for p in pats)]
        return sorted(matched, key=_natural_key)

    @staticmethod
    def _paragraph_runs(p) -> list:
        """Return translatable <w:r> elements in paragraph p, skipping <w:del> and field codes."""
        r_tag = f"{{{W_NS}}}r"
        hl_tag = f"{{{W_NS}}}hyperlink"
        del_tag = f"{{{W_NS}}}del"
        fld_tag = f"{{{W_NS}}}fldChar"
        t_tag = f"{{{W_NS}}}t"
        in_field_code = False
        runs: list = []

        def visit(parent) -> None:
            nonlocal in_field_code
            for child in parent:
                if child.tag == del_tag:
                    continue
                if child.tag == hl_tag:
                    visit(child)
                    continue
                if child.tag == r_tag:
                    for fc in child.findall(fld_tag):
                        ftype = fc.get(f"{{{W_NS}}}fldCharType")
                        if ftype == "begin":
                            in_field_code = True
                        elif ftype in ("separate", "end"):
                            in_field_code = False
                    if not in_field_code and child.find(t_tag) is not None:
                        runs.append(child)

        visit(p)
        return runs

    @staticmethod
    def _set_run_lang(run) -> None:
        from lxml import etree

        rpr_tag = f"{{{W_NS}}}rPr"
        lang_tag = f"{{{W_NS}}}lang"
        rpr = run.find(rpr_tag)
        if rpr is None:
            rpr = etree.Element(rpr_tag)
            run.insert(0, rpr)
        lang = rpr.find(lang_tag)
        if lang is None:
            lang = etree.SubElement(rpr, lang_tag)
        lang.set(f"{{{W_NS}}}val", "id-ID")

    def inspect_info(self, path: Path) -> dict:
        with _open_zip(path) as z:
            names = z.namelist()
            xml = z.read("word/document.xml").decode("utf-8", "ignore") if "word/document.xml" in names else ""
            return {
                "parts": len(names),
                "tables": xml.count("<w:tbl>") + xml.count("<w:tbl "),
                "headers_footers": sum(1 for n in names if re.match(r"word/(header|footer)\d*\.xml$", n)),
                "has_comments": "word/comments.xml" in names,
                "has_footnotes": "word/footnotes.xml" in names,
                "has_tracked_changes": bool(re.search(r"<w:(ins|del)\b", xml)),
            }

    def extract(self, path: Path) -> list[Segment]:
        from lxml import etree

        p_tag = f"{{{W_NS}}}p"
        rpr_tag = f"{{{W_NS}}}rPr"
        t_tag = f"{{{W_NS}}}t"
        segs: list[Segment] = []
        with _open_zip(path) as z:
            for part in self._target_parts(z.namelist()):
                root = etree.fromstring(z.read(part))
                for p_idx, p in enumerate(root.iter(p_tag)):
                    groups = _group_runs(self._paragraph_runs(p), rpr_tag, t_tag)
                    if not groups:
                        continue
                    masked, protect, n_groups = _encode_groups(groups, t_tag)
                    segs.append(
                        Segment(
                            id=f"dx{len(segs) + 1:04d}",
                            type="paragraph",
                            text=masked,
                            style={"part": part, "groups": n_groups},
                            loc={"part": part, "p_index": p_idx},
                            protect=protect,
                            status="pending" if has_translatable_text(masked) else "skip",
                        )
                    )
        return segs

    def render(self, path, segments, translations, options: ApplyOptions):
        from lxml import etree

        p_tag = f"{{{W_NS}}}p"
        rpr_tag = f"{{{W_NS}}}rPr"
        t_tag = f"{{{W_NS}}}t"
        by_part: dict[str, dict[int, tuple[Segment, str]]] = {}
        for seg in segments:
            tr = translations.get(seg.id)
            if tr is None or (tr == seg.text and not options.set_lang):
                continue
            by_part.setdefault(seg.loc["part"], {})[seg.loc["p_index"]] = (seg, tr)

        updates: dict[str, bytes] = {}
        with _open_zip(path) as z:
            for part, edits in by_part.items():
                root = etree.fromstring(z.read(part))
                for p_idx, p in enumerate(root.iter(p_tag)):
                    if p_idx not in edits:
                        continue
                    seg, tr = edits[p_idx]
                    groups = _group_runs(self._paragraph_runs(p), rpr_tag, t_tag)
                    if not groups:
                        continue
                    _apply_groups(
                        groups,
                        t_tag,
                        tr,
                        seg.protect,
                        self._set_run_lang if options.set_lang else None,
                    )
                updates[part] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        return _rewrite_zip(path, updates), RenderReport()


# --------------------------------------------------------------------------- PPTX


class PptxHandler(_OoxmlBase):
    name = "pptx"
    extensions = (".pptx",)

    @staticmethod
    def _target_parts(names: list[str]) -> list[str]:
        slides = sorted(
            [n for n in names if re.match(r"^ppt/slides/slide\d+\.xml$", n)],
            key=_natural_key,
        )
        notes = sorted(
            [n for n in names if re.match(r"^ppt/notesSlides/notesSlide\d+\.xml$", n)],
            key=_natural_key,
        )
        return slides + notes

    @staticmethod
    def _set_run_lang(run) -> None:
        from lxml import etree

        rpr_tag = f"{{{A_NS}}}rPr"
        rpr = run.find(rpr_tag)
        if rpr is None:
            rpr = etree.Element(rpr_tag)
            run.insert(0, rpr)
        rpr.set("lang", "id-ID")

    def inspect_info(self, path: Path) -> dict:
        with _open_zip(path) as z:
            names = z.namelist()
            return {
                "slides": sum(1 for n in names if re.match(r"^ppt/slides/slide\d+\.xml$", n)),
                "notes_slides": sum(1 for n in names if re.match(r"^ppt/notesSlides/notesSlide\d+\.xml$", n)),
                "charts": sum(1 for n in names if n.startswith("ppt/charts/chart")),
                "smartart": sum(1 for n in names if n.startswith("ppt/diagrams/data")),
            }

    def unit_count(self, path: Path) -> tuple[int, str]:
        with _open_zip(path) as z:
            count = sum(1 for n in z.namelist() if re.match(r"^ppt/slides/slide\d+\.xml$", n))
        return count, "slide"

    def extract(self, path: Path) -> list[Segment]:
        from lxml import etree

        p_tag = f"{{{A_NS}}}p"
        r_tag = f"{{{A_NS}}}r"
        rpr_tag = f"{{{A_NS}}}rPr"
        t_tag = f"{{{A_NS}}}t"
        segs: list[Segment] = []
        with _open_zip(path) as z:
            for part in self._target_parts(z.namelist()):
                root = etree.fromstring(z.read(part))
                kind = "notes" if "notesSlides" in part else "slide_text"
                for p_idx, p in enumerate(root.iter(p_tag)):
                    runs = [c for c in p if c.tag == r_tag and c.find(t_tag) is not None]
                    groups = _group_runs(runs, rpr_tag, t_tag)
                    if not groups:
                        continue
                    masked, protect, n_groups = _encode_groups(groups, t_tag)
                    segs.append(
                        Segment(
                            id=f"px{len(segs) + 1:04d}",
                            type=kind,
                            text=masked,
                            style={"part": part, "groups": n_groups},
                            loc={"part": part, "p_index": p_idx},
                            protect=protect,
                            status="pending" if has_translatable_text(masked) else "skip",
                        )
                    )
        return segs

    def render(self, path, segments, translations, options: ApplyOptions):
        from lxml import etree

        p_tag = f"{{{A_NS}}}p"
        r_tag = f"{{{A_NS}}}r"
        rpr_tag = f"{{{A_NS}}}rPr"
        t_tag = f"{{{A_NS}}}t"
        by_part: dict[str, dict[int, tuple[Segment, str]]] = {}
        for seg in segments:
            tr = translations.get(seg.id)
            if tr is None or (tr == seg.text and not options.set_lang):
                continue
            by_part.setdefault(seg.loc["part"], {})[seg.loc["p_index"]] = (seg, tr)

        updates: dict[str, bytes] = {}
        with _open_zip(path) as z:
            for part, edits in by_part.items():
                root = etree.fromstring(z.read(part))
                for p_idx, p in enumerate(root.iter(p_tag)):
                    if p_idx not in edits:
                        continue
                    seg, tr = edits[p_idx]
                    runs = [c for c in p if c.tag == r_tag and c.find(t_tag) is not None]
                    groups = _group_runs(runs, rpr_tag, t_tag)
                    if not groups:
                        continue
                    _apply_groups(
                        groups,
                        t_tag,
                        tr,
                        seg.protect,
                        self._set_run_lang if options.set_lang else None,
                    )
                updates[part] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        return _rewrite_zip(path, updates), RenderReport()


# --------------------------------------------------------------------------- XLSX


class XlsxHandler(_OoxmlBase):
    name = "xlsx"
    extensions = (".xlsx",)

    def inspect_info(self, path: Path) -> dict:
        with _open_zip(path) as z:
            names = z.namelist()
            wb = z.read("xl/workbook.xml").decode("utf-8", "ignore") if "xl/workbook.xml" in names else ""
            sheets = re.findall(r'<sheet [^>]*name="([^"]+)"', wb)
            ss = z.read("xl/sharedStrings.xml").decode("utf-8", "ignore") if "xl/sharedStrings.xml" in names else ""
            has_f = any(
                (b"<f>" in data or b"<f " in data)
                for n in names
                if n.startswith("xl/worksheets/sheet")
                for data in (z.read(n),)
            )
            return {
                "sheets": sheets,
                "shared_strings": ss.count("<si>"),
                "formulas_hint": has_f,
            }

    def unit_count(self, path: Path) -> tuple[int, str]:
        with _open_zip(path) as z:
            wb = z.read("xl/workbook.xml").decode("utf-8", "ignore")
            sheets = re.findall(r"<sheet\b", wb)
        return len(sheets), "sheet"

    @staticmethod
    def _extract_si(el) -> tuple[str, dict[str, str], int]:
        t_tag = f"{{{S_NS}}}t"
        r_tag = f"{{{S_NS}}}r"
        rpr_tag = f"{{{S_NS}}}rPr"
        runs = [c for c in el if c.tag == r_tag and c.find(t_tag) is not None]
        if runs:
            groups = _group_runs(runs, rpr_tag, t_tag)
            if groups:
                return _encode_groups(groups, t_tag)
        t_el = el.find(t_tag)
        txt = (t_el.text or "") if t_el is not None else ""
        masked, protect = mask(txt, DEFAULT_OPTIONS)
        return masked, protect, 0

    @staticmethod
    def _apply_si(el, tr: str, protect: dict[str, str]) -> None:
        t_tag = f"{{{S_NS}}}t"
        r_tag = f"{{{S_NS}}}r"
        rpr_tag = f"{{{S_NS}}}rPr"
        runs = [c for c in el if c.tag == r_tag and c.find(t_tag) is not None]
        if runs:
            groups = _group_runs(runs, rpr_tag, t_tag)
            if groups:
                _apply_groups(groups, t_tag, tr, protect)
                return
        t_el = el.find(t_tag)
        if t_el is not None:
            final = restore(tr, protect)
            t_el.text = final
            if final != final.strip() or "\n" in final:
                t_el.set(XML_SPACE, "preserve")

    def extract(self, path: Path) -> list[Segment]:
        from lxml import etree

        si_tag = f"{{{S_NS}}}si"
        c_tag = f"{{{S_NS}}}c"
        f_tag = f"{{{S_NS}}}f"
        is_tag = f"{{{S_NS}}}is"
        segs: list[Segment] = []
        with _open_zip(path) as z:
            names = z.namelist()
            if "xl/sharedStrings.xml" in names:
                root = etree.fromstring(z.read("xl/sharedStrings.xml"))
                for idx, si in enumerate(root.findall(si_tag)):
                    masked, protect, n_groups = self._extract_si(si)
                    if not masked:
                        continue
                    segs.append(
                        Segment(
                            id=f"xl{len(segs) + 1:04d}",
                            type="shared_string",
                            text=masked,
                            style={"part": "xl/sharedStrings.xml", "groups": n_groups},
                            loc={"part": "xl/sharedStrings.xml", "si_index": idx},
                            protect=protect,
                            status="pending" if has_translatable_text(masked) else "skip",
                        )
                    )
            sheets = sorted(
                [n for n in names if re.match(r"^xl/worksheets/sheet\d+\.xml$", n)],
                key=_natural_key,
            )
            for part in sheets:
                root = etree.fromstring(z.read(part))
                for c in root.iter(c_tag):
                    if c.get("t") != "inlineStr" or c.find(f_tag) is not None:
                        continue  # never translate formula cells
                    is_el = c.find(is_tag)
                    if is_el is None:
                        continue
                    masked, protect, n_groups = self._extract_si(is_el)
                    if not masked:
                        continue
                    ref = c.get("r", "")
                    segs.append(
                        Segment(
                            id=f"xl{len(segs) + 1:04d}",
                            type="inline_cell",
                            text=masked,
                            style={"part": part, "cell": ref, "groups": n_groups},
                            loc={"part": part, "cell": ref},
                            protect=protect,
                            status="pending" if has_translatable_text(masked) else "skip",
                        )
                    )
        return segs

    def render(self, path, segments, translations, options: ApplyOptions):
        from lxml import etree

        si_tag = f"{{{S_NS}}}si"
        c_tag = f"{{{S_NS}}}c"
        is_tag = f"{{{S_NS}}}is"
        ss_edits: dict[int, tuple[Segment, str]] = {}
        inline_edits: dict[str, dict[str, tuple[Segment, str]]] = {}
        for seg in segments:
            tr = translations.get(seg.id)
            if tr is None or tr == seg.text:
                continue
            if seg.type == "shared_string":
                ss_edits[seg.loc["si_index"]] = (seg, tr)
            else:
                inline_edits.setdefault(seg.loc["part"], {})[seg.loc["cell"]] = (seg, tr)

        updates: dict[str, bytes] = {}
        with _open_zip(path) as z:
            if ss_edits and "xl/sharedStrings.xml" in z.namelist():
                root = etree.fromstring(z.read("xl/sharedStrings.xml"))
                for idx, si in enumerate(root.findall(si_tag)):
                    if idx in ss_edits:
                        seg, tr = ss_edits[idx]
                        self._apply_si(si, tr, seg.protect)
                updates["xl/sharedStrings.xml"] = etree.tostring(
                    root, xml_declaration=True, encoding="UTF-8", standalone=True
                )
            for part, cells in inline_edits.items():
                root = etree.fromstring(z.read(part))
                for c in root.iter(c_tag):
                    ref = c.get("r", "")
                    if ref in cells:
                        is_el = c.find(is_tag)
                        if is_el is not None:
                            seg, tr = cells[ref]
                            self._apply_si(is_el, tr, seg.protect)
                updates[part] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        return _rewrite_zip(path, updates), RenderReport()
