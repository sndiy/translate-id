"""PyMuPDF implementation of ``PdfEngine`` (optional extra ``[pdf]``).

PyMuPDF is dual-licensed under GNU AGPL-3.0 or an Artifex commercial license. It is never
vendored and is imported lazily only when PDF features are used.
"""

from __future__ import annotations

import html
import importlib.util
from io import BytesIO
from pathlib import Path

from id_translate.errors import DependencyMissingError, EncryptedInputError, InputError
from id_translate.pdf import PdfBlock, PdfEdit, PdfEngine, PdfRenderResult

MIN_FONT_SCALE = 0.90  # PLAN: auto-fit shrinks font by at most ~10%
SCAN_MIN_CHARS_PER_PAGE = 40
SCAN_PAGE_RATIO = 0.80


def _pymupdf():
    try:
        import pymupdf  # type: ignore

        return pymupdf
    except ImportError as exc:
        raise DependencyMissingError(
            "PyMuPDF is not installed. Install optional extra: pip install 'id-translate[pdf]'"
        ) from exc


def _int_to_rgb(color: int) -> tuple[float, float, float]:
    r = ((color >> 16) & 0xFF) / 255.0
    g = ((color >> 8) & 0xFF) / 255.0
    b = (color & 0xFF) / 255.0
    return (round(r, 3), round(g, 3), round(b, 3))


def _rgb_css(rgb: tuple[float, float, float]) -> str:
    return f"rgb({int(rgb[0] * 255)}, {int(rgb[1] * 255)}, {int(rgb[2] * 255)})"


def _join_block_lines(lines: list[dict]) -> str:
    parts: list[str] = []
    for ln in lines:
        s = "".join(sp.get("text", "") for sp in ln.get("spans", [])).strip()
        if not s:
            continue
        if parts and parts[-1].endswith("-") and not parts[-1].endswith(" -"):
            parts[-1] = parts[-1][:-1] + s
        else:
            parts.append(s)
    return " ".join(parts)


def _dominant_style(lines: list[dict]) -> tuple[float, tuple[float, float, float], bool, bool, bool]:
    best_len = -1
    size = 11.0
    color = (0.0, 0.0, 0.0)
    bold = italic = serif = False
    for ln in lines:
        for sp in ln.get("spans", []):
            txt = (sp.get("text") or "").strip()
            if len(txt) > best_len:
                best_len = len(txt)
                size = round(float(sp.get("size", 11.0)), 2)
                color = _int_to_rgb(int(sp.get("color", 0)))
                flags = int(sp.get("flags", 0))
                font_name = str(sp.get("font", "")).lower()
                bold = bool(flags & 16) or ("bold" in font_name)
                italic = bool(flags & 2) or ("italic" in font_name or "oblique" in font_name)
                serif = bool(flags & 4) or ("times" in font_name or "serif" in font_name)
    return size, color, bold, italic, serif


class PyMuPdfEngine(PdfEngine):
    name = "pymupdf"

    def is_available(self) -> bool:
        return importlib.util.find_spec("pymupdf") is not None

    def _open(self, path: Path):
        fitz = _pymupdf()
        try:
            doc = fitz.open(path)
        except Exception as exc:
            raise InputError(f"cannot open PDF {path}: {exc}") from exc
        if doc.is_encrypted or doc.needs_pass:
            doc.close()
            raise EncryptedInputError(
                f"{path.name} is encrypted or password-protected. Refusing to process; "
                "id-translate never removes passwords or DRM."
            )
        return doc

    def check_access(self, path: Path) -> None:
        doc = self._open(path)
        doc.close()

    def page_count(self, path: Path) -> int:
        doc = self._open(path)
        try:
            return doc.page_count
        finally:
            doc.close()

    def inspect(self, path: Path) -> dict:
        doc = self._open(path)
        try:
            low_text: list[int] = []
            fonts: dict[str, int] = {}
            imgs = links = chars = 0
            sizes: set[tuple[float, float]] = set()
            for idx, page in enumerate(doc, 1):
                r = page.rect
                sizes.add((round(r.width, 1), round(r.height, 1)))
                txt = (page.get_text("text") or "").strip()
                chars += len(txt)
                if len(txt) < SCAN_MIN_CHARS_PER_PAGE:
                    low_text.append(idx)
                imgs += len(page.get_images(full=True))
                links += len(page.get_links())
                for f in page.get_fonts(full=True):
                    fname = f[3]
                    fonts[fname] = fonts.get(fname, 0) + 1
            ratio = len(low_text) / max(doc.page_count, 1)
            is_scan = chars == 0 or ratio > SCAN_PAGE_RATIO
            verdict = (
                "Kemungkinan PDF hasil scan (tanpa text layer). Perlu OCR sebelum diterjemahkan; "
                "fidelity tata letak rendah dan OCR dapat salah baca."
                if is_scan
                else "Ada text layer. Strategi: ekstrak per blok dengan bbox, redaksi teks tanpa "
                "menghapus gambar/vektor, tulis ulang dengan font tertanam (auto-fit maks -10%)."
            )
            return {
                "pages": doc.page_count,
                "page_sizes": sorted(sizes),
                "text_chars": chars,
                "images": imgs,
                "links": links,
                "fonts": dict(sorted(fonts.items(), key=lambda kv: -kv[1])[:25]),
                "pages_with_little_text": low_text[:100],
                "is_likely_scan": is_scan,
                "verdict": verdict,
            }
        finally:
            doc.close()

    def extract_blocks(self, path: Path) -> list[PdfBlock]:
        doc = self._open(path)
        blocks: list[PdfBlock] = []
        try:
            for p_idx, page in enumerate(doc, 1):
                raw = page.get_text("dict")
                for b in raw.get("blocks", []):
                    if b.get("type") != 0:
                        continue
                    lines = b.get("lines", [])
                    text = _join_block_lines(lines)
                    if not text.strip():
                        continue
                    size, color, bold, italic, serif = _dominant_style(lines)
                    x0, y0, x1, y1 = (round(float(v), 2) for v in b["bbox"])
                    blocks.append(
                        PdfBlock(
                            page=p_idx,
                            block_no=int(b.get("number", len(blocks))),
                            bbox=(x0, y0, x1, y1),
                            text=text,
                            font_size=size,
                            color_rgb=color,
                            bold=bold,
                            italic=italic,
                            serif=serif,
                        )
                    )
            return blocks
        finally:
            doc.close()

    def extract_plain_text(self, path: Path) -> str:
        doc = self._open(path)
        try:
            return "\n".join(page.get_text("text") or "" for page in doc)
        finally:
            doc.close()

    def apply_edits(self, path: Path, edits: list[PdfEdit]) -> PdfRenderResult:
        fitz = _pymupdf()
        doc = self._open(path)
        flags: list[dict] = []
        notes: list[str] = []
        by_page: dict[int, list[PdfEdit]] = {}
        for ed in edits:
            by_page.setdefault(ed.page, []).append(ed)
        try:
            for page_no, page_edits in sorted(by_page.items()):
                page = doc[page_no - 1]
                # 1. Redact old text without painting white fill or removing images/vector graphics.
                for ed in page_edits:
                    rect = fitz.Rect(ed.bbox)
                    page.add_redact_annot(rect, fill=None)
                page.apply_redactions(
                    images=fitz.PDF_REDACT_IMAGE_NONE,
                    graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                )
                # 2. Rewrite each block in its bbox with embedded font and capped auto-fit (max -10%).
                for ed in page_edits:
                    rect = fitz.Rect(ed.bbox)
                    # Add a small vertical pad (2pt) for descenders/ascenders of replacement font.
                    work_rect = fitz.Rect(rect.x0, rect.y0, rect.x1, min(page.rect.y1 - 8, rect.y1 + 2.0))
                    family = "serif" if ed.serif else "sans-serif"
                    weight = "bold" if ed.bold else "normal"
                    style = "italic" if ed.italic else "normal"
                    css = (
                        f"* {{ font-family: {family}; font-size: {ed.font_size:.2f}pt; "
                        f"font-weight: {weight}; font-style: {style}; "
                        f"color: {_rgb_css(ed.color_rgb)}; line-height: 1.12; margin: 0; padding: 0; }}"
                    )
                    markup = html.escape(ed.text).replace("\n", "<br/>")
                    spare, used_scale = page.insert_htmlbox(
                        work_rect, markup, css=css, scale_low=MIN_FONT_SCALE
                    )
                    if spare < 0:
                        # Text still did not fit at -10% font size: NEVER truncate!
                        # Expand box downward to page bottom margin and flag page for manual review.
                        expanded = fitz.Rect(
                            work_rect.x0,
                            work_rect.y0,
                            work_rect.x1,
                            max(work_rect.y1, page.rect.y1 - 12),
                        )
                        css_min = (
                            f"* {{ font-family: {family}; font-size: {ed.font_size * MIN_FONT_SCALE:.2f}pt; "
                            f"font-weight: {weight}; font-style: {style}; "
                            f"color: {_rgb_css(ed.color_rgb)}; line-height: 0.98; margin: 0; padding: 0; }}"
                        )
                        spare2, _ = page.insert_htmlbox(expanded, markup, css=css_min, scale_low=0.0)
                        flags.append(
                            {
                                "page": page_no,
                                "segment_id": ed.segment_id,
                                "reason": "overflow_after_10pct_shrink",
                                "bbox": list(ed.bbox),
                                "expanded_fit": spare2 >= 0,
                            }
                        )
                    elif used_scale < 0.995:
                        notes.append(
                            f"Halaman {page_no} ({ed.segment_id}): ukuran huruf diturunkan "
                            f"{round((1 - used_scale) * 100, 1)}% agar muat di bbox."
                        )
            data = doc.tobytes(garbage=3, deflate=True)
            return PdfRenderResult(data=data, flags=flags, notes=notes)
        finally:
            doc.close()

    def side_by_side_png(self, source: Path, translated: Path, page_index: int, zoom: float = 1.5) -> bytes:
        fitz = _pymupdf()
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError as exc:
            raise DependencyMissingError(
                "compare requires Pillow: pip install 'id-translate[compare]'"
            ) from exc

        doc_s = self._open(source)
        doc_t = self._open(translated)
        try:
            if page_index < 0 or page_index >= doc_s.page_count or page_index >= doc_t.page_count:
                raise InputError(
                    f"page {page_index + 1} out of range (source: {doc_s.page_count}, "
                    f"translated: {doc_t.page_count})"
                )
            mat = fitz.Matrix(zoom, zoom)
            pix_s = doc_s[page_index].get_pixmap(matrix=mat, alpha=False)
            pix_t = doc_t[page_index].get_pixmap(matrix=mat, alpha=False)
            img_s = Image.frombytes("RGB", (pix_s.width, pix_s.height), pix_s.samples)
            img_t = Image.frombytes("RGB", (pix_t.width, pix_t.height), pix_t.samples)
        finally:
            doc_s.close()
            doc_t.close()

        header_h = 36
        gap = 12
        width = img_s.width + gap + img_t.width
        height = header_h + max(img_s.height, img_t.height)
        canvas = Image.new("RGB", (width, height), (245, 245, 245))
        draw = ImageDraw.Draw(canvas)
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except OSError:
            font = ImageFont.load_default()
        draw.text((12, 9), f"SUMBER — {source.name} (hal. {page_index + 1})", fill=(20, 20, 20), font=font)
        draw.text(
            (img_s.width + gap + 12, 9),
            f"HASIL — {translated.name} (hal. {page_index + 1})",
            fill=(20, 20, 20),
            font=font,
        )
        canvas.paste(img_s, (0, header_h))
        canvas.paste(img_t, (img_s.width + gap, header_h))
        draw.line([(img_s.width + gap // 2, 0), (img_s.width + gap // 2, height)], fill=(180, 180, 180), width=2)
        buf = BytesIO()
        canvas.save(buf, format="PNG")
        return buf.getvalue()
