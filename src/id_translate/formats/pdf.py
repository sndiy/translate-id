"""PDF handler built on the pluggable ``PdfEngine`` abstraction.

Default engine: optional PyMuPDF extra ``[pdf]`` (AGPL-3.0 or Artifex commercial license;
never vendored). Encrypted/password-protected PDFs are refused. Scanned PDFs (no text layer)
are flagged during ``inspect`` and require OCR before translation (lower layout fidelity).
"""

from __future__ import annotations

from pathlib import Path

from id_translate.formats.base import ApplyOptions, FormatHandler, RenderReport
from id_translate.pdf import PdfEdit, PdfEngine, get_engine
from id_translate.protect import DEFAULT_OPTIONS, has_translatable_text, mask, restore
from id_translate.segments import Segment


class PdfHandler(FormatHandler):
    name = "pdf"
    extensions = (".pdf",)
    stability = "beta"
    extra = "pdf"

    def __init__(self, engine: PdfEngine | None = None):
        self._engine = engine

    def _get_engine(self) -> PdfEngine:
        return self._engine if self._engine is not None else get_engine()

    def missing_dependencies(self) -> list[str]:
        if self._engine is not None:
            return [] if self._engine.is_available() else [self._engine.name]
        try:
            get_engine()
            return []
        except Exception:
            return ["pymupdf"]

    def check_access(self, path: Path) -> None:
        self._get_engine().check_access(path)

    def inspect_info(self, path: Path) -> dict:
        return self._get_engine().inspect(path)

    def unit_count(self, path: Path) -> tuple[int, str]:
        return self._get_engine().page_count(path), "halaman"

    def extract(self, path: Path) -> list[Segment]:
        blocks = self._get_engine().extract_blocks(path)
        segs: list[Segment] = []
        for idx, b in enumerate(blocks, 1):
            masked, protect = mask(b.text, DEFAULT_OPTIONS)
            segs.append(
                Segment(
                    id=f"pdf{idx:04d}",
                    type="block",
                    text=masked,
                    style={
                        "font_size": b.font_size,
                        "color_rgb": list(b.color_rgb),
                        "bold": b.bold,
                        "italic": b.italic,
                        "serif": b.serif,
                    },
                    loc={"page": b.page, "block_no": b.block_no, "bbox": list(b.bbox)},
                    protect=protect,
                    status="pending" if has_translatable_text(masked) else "skip",
                )
            )
        return segs

    def render(self, path, segments, translations, options: ApplyOptions):
        edits: list[PdfEdit] = []
        for seg in segments:
            tr = translations.get(seg.id)
            if tr is None:
                continue
            final = restore(tr, seg.protect)
            edits.append(
                PdfEdit(
                    page=int(seg.loc["page"]),
                    segment_id=seg.id,
                    bbox=tuple(float(v) for v in seg.loc["bbox"]),
                    text=final,
                    font_size=float(seg.style.get("font_size", 11.0)),
                    color_rgb=tuple(float(v) for v in seg.style.get("color_rgb", [0.0, 0.0, 0.0])),
                    bold=bool(seg.style.get("bold", False)),
                    italic=bool(seg.style.get("italic", False)),
                    serif=bool(seg.style.get("serif", False)),
                )
            )
        if not edits:
            return Path(path).read_bytes(), RenderReport()
        res = self._get_engine().apply_edits(path, edits)
        return res.data, RenderReport(flags=res.flags, notes=res.notes)

    def qa_text(self, path: Path) -> str:
        return self._get_engine().extract_plain_text(path)
