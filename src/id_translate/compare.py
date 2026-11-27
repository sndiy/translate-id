"""Side-by-side comparison images (source | translation).

PDF: pages are rendered by the PDF engine (PyMuPDF) — a true visual comparison.
Other formats: a text-panel image built with Pillow from the extracted text. This is NOT a
rendering of the document layout (no office renderer is bundled); it is labelled as such.
"""

from __future__ import annotations

import textwrap
from io import BytesIO
from pathlib import Path

from id_translate.errors import DependencyMissingError, InputError, OverwriteRefusedError
from id_translate.safety import write_new_bytes


def _outputs(out: Path, pages: list[int]) -> list[Path]:
    if len(pages) == 1:
        return [out]
    return [out.with_name(f"{out.stem}-p{p}{out.suffix}") for p in pages]


def compare_files(source: Path, translated: Path, out: Path, pages: list[int], zoom: float = 1.5) -> list[Path]:
    for p in (source, translated):
        if not Path(p).is_file():
            raise InputError(f"file not found: {p}")
    if out.suffix.lower() != ".png":
        raise InputError("--out must end with .png")
    outs = _outputs(out, pages)
    for o in outs:
        if o.exists():
            raise OverwriteRefusedError(f"refusing to overwrite existing file: {o}")
    if source.suffix.lower() == ".pdf":
        from id_translate.pdf import get_engine

        engine = get_engine()
        engine.check_access(source)
        engine.check_access(translated)
        for page, o in zip(pages, outs):
            write_new_bytes(o, engine.side_by_side_png(source, translated, page - 1, zoom))
        return outs
    from id_translate.formats import handler_for_path

    handler = handler_for_path(source)
    handler.ensure_available()
    left = handler.qa_text(source).splitlines()
    right = handler.qa_text(translated).splitlines()
    for page, o in zip(pages, outs):
        write_new_bytes(o, text_panels_png(left, right, page, f"{source.name}", f"{translated.name}"))
    return outs


def text_panels_png(left: list[str], right: list[str], page: int, ltitle: str, rtitle: str) -> bytes:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise DependencyMissingError(
            "compare for non-PDF formats needs Pillow: pip install 'id-translate[compare]'"
        ) from exc

    def load_font(size: int):
        for name in ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf", "LiberationSans-Regular.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    font, head = load_font(15), load_font(17)
    width, col_w, margin, line_h, per_page = 1400, 660, 30, 22, 45
    wrap = 78

    def wrapped(lines: list[str]) -> list[str]:
        out: list[str] = []
        for ln in lines:
            out += textwrap.wrap(ln, wrap) or [""]
        return out

    lw, rw = wrapped(left), wrapped(right)
    lo = (page - 1) * per_page
    lw, rw = lw[lo : lo + per_page], rw[lo : lo + per_page]
    height = margin * 3 + line_h * (max(len(lw), len(rw), 1) + 3)
    img = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(img)
    d.text((margin, margin), f"SUMBER: {ltitle}", fill="black", font=head)
    d.text((margin + col_w + 50, margin), f"HASIL: {rtitle}", fill="black", font=head)
    d.text(
        (margin, margin + line_h + 4),
        "(panel teks hasil ekstraksi, bukan render tata letak)",
        fill="gray",
        font=font,
    )
    d.line([(width // 2, margin), (width // 2, height - margin)], fill="#999999", width=2)
    y0 = margin + line_h * 3
    for k, ln in enumerate(lw):
        d.text((margin, y0 + k * line_h), ln, fill="black", font=font)
    for k, ln in enumerate(rw):
        d.text((margin + col_w + 50, y0 + k * line_h), ln, fill="black", font=font)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
