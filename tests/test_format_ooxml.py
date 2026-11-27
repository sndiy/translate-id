"""Round-trip and safety tests for DOCX, PPTX, and XLSX (using self-generated fixtures)."""

import zipfile

import openpyxl
import pytest
from docx import Document
from helpers import assert_reextract_matches, cli, expected_pseudo, pseudo, run_roundtrip
from pptx import Presentation

from id_translate.qa import run_qa
from id_translate.safety import OLE_MAGIC


def _make_docx(path):
    doc = Document()
    doc.add_heading("Project Guide", level=1)
    p = doc.add_paragraph("Hello ")
    r = p.add_run("{user}")
    r.bold = True
    p.add_run(", visit https://example.com today.")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Feature"
    table.cell(0, 1).text = "Notes"
    table.cell(1, 0).text = "Export"
    table.cell(1, 1).text = "Ready"
    doc.sections[0].header.paragraphs[0].text = "Internal Draft"
    doc.save(path)
    return path


def _make_pptx(path):
    prs = Presentation()
    s1 = prs.slides.add_slide(prs.slide_layouts[1])
    s1.shapes.title.text = "Quarterly Review"
    tf = s1.placeholders[1].text_frame
    tf.text = "Welcome {team} to the meeting."
    p2 = tf.add_paragraph()
    p2.text = "See https://example.com for slides."
    s1.notes_slide.notes_text_frame.text = "Remind audience about Q4 goals."
    s2 = prs.slides.add_slide(prs.slide_layouts[1])
    s2.shapes.title.text = "Next Steps"
    prs.save(path)
    return path


def _make_xlsx(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Budget"
    ws["A1"] = "Item"
    ws["B1"] = "Cost"
    ws["A2"] = "Hosting for {app}"
    ws["B2"] = 1200
    ws["A3"] = "Support"
    ws["B3"] = 300
    ws["A4"] = "Total"
    ws["B4"] = "=SUM(B2:B3)"
    ws2 = wb.create_sheet("Notes")
    ws2["A1"] = "Visit https://example.com"
    wb.save(path)
    return path


def test_docx_roundtrip_identity_and_longer(tmp_path):
    src = _make_docx(tmp_path / "sample.docx")
    h, segs, out, _ = run_roundtrip(src, tmp_path)
    assert out.read_bytes() == src.read_bytes()
    assert any("Internal Draft" in s.text for s in segs)

    h, segs, out2, _ = run_roundtrip(
        src, tmp_path, translate=lambda s: pseudo(s.text), set_lang=True, name="long"
    )
    d = Document(out2)
    assert d.paragraphs[0].text.startswith("Ïd Project Guide")
    assert "{user}" in d.paragraphs[1].text and "https://example.com" in d.paragraphs[1].text
    assert any(r.bold for r in d.paragraphs[1].runs)  # bold run preserved
    assert d.tables[0].cell(1, 0).text.startswith("Ïd Export")
    assert d.sections[0].header.paragraphs[0].text.startswith("Ïd Internal Draft")
    with zipfile.ZipFile(out2) as z:
        assert 'w:val="id-ID"' in z.read("word/document.xml").decode("utf-8")
    assert run_qa(src, out2).errors == []


def test_pptx_roundtrip_identity_and_longer(tmp_path):
    src = _make_pptx(tmp_path / "sample.pptx")
    h, segs, out, _ = run_roundtrip(src, tmp_path)
    assert out.read_bytes() == src.read_bytes()
    assert h.unit_count(src) == (2, "slide")

    h, segs, out2, _ = run_roundtrip(
        src, tmp_path, translate=lambda s: pseudo(s.text), set_lang=True, name="long"
    )
    prs = Presentation(out2)
    assert len(prs.slides) == 2
    assert prs.slides[0].shapes.title.text.startswith("Ïd Quarterly Review")
    assert "{team}" in prs.slides[0].placeholders[1].text_frame.text
    assert "Q4 goals" in prs.slides[0].notes_slide.notes_text_frame.text
    assert prs.slides[0].notes_slide.notes_text_frame.text.startswith("Ïd ")
    with zipfile.ZipFile(out2) as z:
        assert 'lang="id-ID"' in z.read("ppt/slides/slide1.xml").decode("utf-8")
    assert_reextract_matches(h, segs, out2, expected_pseudo)
    assert run_qa(src, out2).errors == []


def test_xlsx_roundtrip_preserves_formulas_and_numbers(tmp_path):
    src = _make_xlsx(tmp_path / "sample.xlsx")
    h, segs, out, _ = run_roundtrip(src, tmp_path)
    assert out.read_bytes() == src.read_bytes()
    assert h.unit_count(src) == (2, "sheet")
    assert all("=SUM" not in s.text for s in segs)

    h, segs, out2, _ = run_roundtrip(src, tmp_path, translate=lambda s: pseudo(s.text), name="long")
    wb = openpyxl.load_workbook(out2, data_only=False)
    assert wb.sheetnames == ["Budget", "Notes"]
    ws = wb["Budget"]
    assert ws["A2"].value.startswith("Ïd Hosting for {app}")
    assert ws["B2"].value == 1200
    assert ws["B4"].value == "=SUM(B2:B3)"  # formula untouched!
    assert "https://example.com" in wb["Notes"]["A1"].value
    assert_reextract_matches(h, segs, out2, expected_pseudo)
    assert run_qa(src, out2).errors == []


@pytest.mark.parametrize("ext", [".docx", ".pptx", ".xlsx"])
def test_encrypted_office_files_are_refused(tmp_path, ext):
    p = tmp_path / f"locked{ext}"
    p.write_bytes(OLE_MAGIC + b"\x00" * 504)
    before = p.read_bytes()
    for cmd in (["inspect", p], ["extract", p, "--out", tmp_path / "s.jsonl"], ["init", p]):
        r = cli(*cmd)
        assert r.returncode == 4, (cmd, r.stderr)
        assert "encrypted" in r.stderr.lower() or "ole" in r.stderr.lower()
    assert p.read_bytes() == before
    assert not (tmp_path / "s.jsonl").exists()
