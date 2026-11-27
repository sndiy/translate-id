"""Tests for the PDF prototype, PyMuPDF backend, pluggable engine abstraction, and compare PNG."""

import json
from io import BytesIO
from pathlib import Path

import pymupdf
import pytest
from helpers import cli, run_roundtrip
from PIL import Image

from id_translate.errors import EncryptedInputError
from id_translate.formats.base import ApplyOptions
from id_translate.formats.pdf import PdfHandler
from id_translate.pdf import PdfBlock, PdfEngine, PdfRenderResult
from id_translate.qa import run_qa


def _make_sample_pdf(path: Path) -> Path:
    """Create a self-made PDF with title, body, colored callout box, raster image, placeholder & URL."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)

    # Colored header banner (vector graphic)
    page.draw_rect(pymupdf.Rect(45, 45, 550, 100), color=(0.15, 0.35, 0.65), fill=(0.90, 0.94, 0.99), width=1.2)
    page.insert_text((60, 80), "Quick Start Guide for {app_name}", fontsize=18, color=(0.1, 0.2, 0.4))

    # Body paragraph
    page.insert_textbox(
        pymupdf.Rect(50, 125, 540, 210),
        "This document explains how to prepare files safely before translation. "
        "Visit https://example.com/docs for full instructions and examples.",
        fontsize=12,
    )

    # Colored callout box (must survive redaction!)
    page.draw_rect(pymupdf.Rect(50, 230, 540, 310), color=(0.75, 0.50, 0.10), fill=(1.0, 0.97, 0.88), width=1.0)
    page.insert_textbox(
        pymupdf.Rect(62, 244, 528, 300),
        "Important: never overwrite original files. Keep backup copies in a separate folder.",
        fontsize=11,
        color=(0.35, 0.22, 0.05),
    )

    # Embedded raster image (must survive redaction!)
    img = Image.new("RGB", (120, 60), (40, 130, 90))
    buf = BytesIO()
    img.save(buf, format="PNG")
    page.insert_image(pymupdf.Rect(50, 335, 170, 395), stream=buf.getvalue())
    page.insert_text((185, 365), "Figure 1: Safe output workflow.", fontsize=10)

    doc.save(path)
    doc.close()
    return path


def _make_encrypted_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_text((50, 72), "Secret content", fontsize=12)
    doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner")
    doc.close()
    return path


def _make_scan_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    p = doc.new_page()
    img = Image.new("RGB", (200, 100), (220, 220, 220))
    buf = BytesIO()
    img.save(buf, format="PNG")
    p.insert_image(pymupdf.Rect(50, 50, 250, 150), stream=buf.getvalue())
    doc.save(path)
    doc.close()
    return path


def test_pdf_roundtrip_preserves_pages_vectors_images_and_placeholders(tmp_path):
    src = _make_sample_pdf(tmp_path / "sample.pdf")
    h, segs, out, res = run_roundtrip(src, tmp_path)
    assert h.unit_count(out) == (1, "halaman")
    assert "{app_name}" not in segs[0].text
    assert any("https://example.com/docs" in s.protect.values() for s in segs)

    # Verify images and vector drawings survived redaction + rewrite
    d_src, d_out = pymupdf.open(src), pymupdf.open(out)
    try:
        assert d_out.page_count == d_src.page_count == 1
        assert len(d_out[0].get_images(full=True)) == len(d_src[0].get_images(full=True)) == 1
        assert len(d_out[0].get_drawings()) >= len(d_src[0].get_drawings()) >= 2
        text_out = d_out[0].get_text("text")
        assert "{app_name}" in text_out and "https://example.com/docs" in text_out
        assert len(d_out[0].get_fonts()) >= 1
    finally:
        d_src.close()
        d_out.close()
    assert run_qa(src, out).errors == []


def test_pdf_overflow_is_flagged_and_never_truncated(tmp_path):
    src = _make_sample_pdf(tmp_path / "sample.pdf")
    tail_marker = "AKHIR_TEKS_UTUH_999"
    h, segs, out, res = run_roundtrip(
        src,
        tmp_path,
        translate=lambda s: s.text + " " + ("teks panjang tambahan untuk menguji batas kotak " * 12) + tail_marker,
        name="overflow",
    )
    assert len(res.report.flags) >= 1
    assert any(f["reason"] == "overflow_after_10pct_shrink" for f in res.report.flags)
    d = pymupdf.open(out)
    try:
        full_text = d[0].get_text("text")
        assert tail_marker in full_text  # text was NOT truncated
    finally:
        d.close()


def test_encrypted_pdf_is_refused(tmp_path):
    src = _make_encrypted_pdf(tmp_path / "locked.pdf")
    before = src.read_bytes()
    h = PdfHandler()
    with pytest.raises(EncryptedInputError):
        h.check_access(src)
    for cmd in (["inspect", src], ["extract", src, "--out", tmp_path / "s.jsonl"], ["init", src]):
        r = cli(*cmd)
        assert r.returncode == 4, (cmd, r.stderr)
    assert src.read_bytes() == before
    assert not (tmp_path / "s.jsonl").exists()


def test_scanned_pdf_is_flagged_in_inspect(tmp_path):
    src = _make_scan_pdf(tmp_path / "scan.pdf")
    r = cli("inspect", src)
    assert r.returncode == 0, r.stderr
    info = json.loads(r.stdout)
    assert info["is_likely_scan"] is True
    assert "OCR" in info["verdict"]


def test_pluggable_pdf_engine_abstraction(tmp_path):
    """PdfHandler works with any PdfEngine implementation without changing segment contract."""

    class DummyEngine(PdfEngine):
        name = "dummy"

        def is_available(self) -> bool:
            return True

        def check_access(self, path: Path) -> None:
            pass

        def inspect(self, path: Path) -> dict:
            return {"pages": 1, "is_likely_scan": False}

        def page_count(self, path: Path) -> int:
            return 1

        def extract_blocks(self, path: Path) -> list[PdfBlock]:
            return [PdfBlock(1, 0, (10, 10, 200, 40), "Hello {name}", 12.0, (0, 0, 0))]

        def extract_plain_text(self, path: Path) -> str:
            return "Hello {name}"

        def apply_edits(self, path: Path, edits) -> PdfRenderResult:
            return PdfRenderResult(data=edits[0].text.encode("utf-8"))

        def side_by_side_png(self, source, translated, page_index, zoom=1.5) -> bytes:
            return b""

    dummy_file = tmp_path / "x.pdf"
    dummy_file.write_bytes(b"%PDF-1.4\n")
    h = PdfHandler(engine=DummyEngine())
    segs = h.extract(dummy_file)
    assert len(segs) == 1 and segs[0].text == "Hello ⟦P1⟧"
    data, _ = h.render(dummy_file, segs, {segs[0].id: "Halo ⟦P1⟧"}, ApplyOptions())
    assert data == b"Halo {name}"


def test_pdf_compare_produces_side_by_side_png(tmp_path):
    src = _make_sample_pdf(tmp_path / "src.pdf")
    _, _, out, _ = run_roundtrip(src, tmp_path, translate=lambda s: "Terjemahan: " + s.text, name="tgt")
    png = tmp_path / "compare.png"
    r = cli("compare", src, out, "--out", png, "--pages", "1")
    assert r.returncode == 0, r.stderr
    assert png.is_file() and png.stat().st_size > 1000
    with Image.open(png) as im:
        assert im.width > im.height  # side-by-side landscape image
