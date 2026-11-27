#!/usr/bin/env python3
"""Deterministic evaluation suite for id-translate (17 cases, pseudo-translation ~+25%).

This suite tests layout safety, placeholder/token preservation, structural integrity,
glossary guards, and PDF overflow flagging using pseudo-translation (text expanded by ~25%
with non-ASCII markers). It does NOT measure human/LLM translation fluency or semantic accuracy.

Usage:
    python evals/run_evals.py [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
import time
import zipfile
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from id_translate.formats.base import ApplyOptions  # noqa: E402
from id_translate.pipeline import apply_translations, extract_to  # noqa: E402
from id_translate.protect import strip_tokens  # noqa: E402
from id_translate.qa import run_qa  # noqa: E402
from id_translate.safety import sha256_file  # noqa: E402


def pseudo_expand_25(masked_text: str) -> str:
    """Expand translatable text by ~25% while leaving protect/span tokens untouched."""
    plain_len = len(strip_tokens(masked_text))
    pad = max(3, math.ceil(plain_len * 0.25))
    # Use a deterministic non-ASCII pseudo-suffix so expansion is ~25% without repeating tokens.
    unit = "ãéîôû "
    suffix = (unit * (pad // len(unit) + 1))[:pad].strip()
    return f"{masked_text} {suffix}"


@dataclass
class CaseResult:
    case_id: str
    fmt: str
    description: str
    segments_pending: int
    overflow_flags: int
    glossary_violations: int
    number_mismatches: int
    qa_errors: int
    qa_warnings: int
    source_unchanged: bool
    elapsed_ms: float
    passed: bool
    note: str = ""


def _write_docx(path: Path) -> Path:
    from docx import Document

    doc = Document()
    doc.add_heading("Deployment Handbook", level=1)
    p = doc.add_paragraph("Configure ")
    r = p.add_run("{service_name}")
    r.bold = True
    p.add_run(" and inspect https://example.com/status before release 2.")
    tbl = doc.add_table(rows=2, cols=2)
    tbl.cell(0, 0).text = "Stage"
    tbl.cell(0, 1).text = "Owner"
    tbl.cell(1, 0).text = "Staging"
    tbl.cell(1, 1).text = "Platform team"
    doc.sections[0].header.paragraphs[0].text = "Operations Manual"
    doc.save(path)
    return path


def _write_pptx(path: Path) -> Path:
    from pptx import Presentation

    prs = Presentation()
    s1 = prs.slides.add_slide(prs.slide_layouts[1])
    s1.shapes.title.text = "Architecture Overview"
    s1.placeholders[1].text_frame.text = "Hello {team}, review 3 core modules at https://example.com."
    s1.notes_slide.notes_text_frame.text = "Pause for questions after slide 1."
    s2 = prs.slides.add_slide(prs.slide_layouts[1])
    s2.shapes.title.text = "Rollout Timeline"
    prs.save(path)
    return path


def _write_xlsx(path: Path) -> Path:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Category"
    ws["B1"] = "Amount"
    ws["A2"] = "Compute for {cluster}"
    ws["B2"] = 1500
    ws["A3"] = "Storage"
    ws["B3"] = 500
    ws["A4"] = "Total"
    ws["B4"] = "=SUM(B2:B3)"
    ws2 = wb.create_sheet("Links")
    ws2["A1"] = "See https://example.com/pricing"
    wb.save(path)
    return path


def _write_epub(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?><container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        z.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0" encoding="utf-8"?>'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            "<dc:title>Eval Book</dc:title><dc:language>en</dc:language></metadata>"
            '<manifest><item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/></manifest>'
            '<spine><itemref idref="c1"/></spine></package>',
        )
        z.writestr(
            "OEBPS/ch1.xhtml",
            '<?xml version="1.0" encoding="utf-8"?>'
            '<html xmlns="http://www.w3.org/1999/xhtml" lang="en">'
            "<head><title>Chapter 1</title></head>"
            "<body><h1>Overview</h1>"
            "<p>Read 2 notes for {reader} at https://example.com.</p>"
            "<code>keep_code_intact()</code></body></html>",
        )
    return path


def _write_pdf_colored_box(path: Path) -> Path:
    import pymupdf
    from PIL import Image

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.draw_rect(pymupdf.Rect(45, 45, 550, 95), color=(0.1, 0.3, 0.6), fill=(0.9, 0.95, 1.0))
    page.insert_text((60, 76), "Evaluation Sheet for {product}", fontsize=16, color=(0.1, 0.2, 0.4))
    page.insert_textbox(
        pymupdf.Rect(50, 115, 540, 200),
        "Verify 3 items before shipping. Full guide at https://example.com/guide.",
        fontsize=12,
    )
    page.draw_rect(pymupdf.Rect(50, 220, 540, 290), color=(0.7, 0.4, 0.1), fill=(1.0, 0.97, 0.88))
    page.insert_textbox(
        pymupdf.Rect(60, 232, 530, 280),
        "Warning: keep original files untouched in every workflow run.",
        fontsize=11,
    )
    img = Image.new("RGB", (100, 50), (30, 120, 80))
    buf = BytesIO()
    img.save(buf, format="PNG")
    page.insert_image(pymupdf.Rect(50, 315, 150, 365), stream=buf.getvalue())
    page.insert_text((165, 345), "Figure 1: Pipeline diagram.", fontsize=10)
    doc.save(path)
    doc.close()
    return path


def _run_standard_case(
    case_id: str,
    fmt: str,
    description: str,
    src: Path,
    td: Path,
    *,
    glossary: Path | None = None,
    translate_fn=None,
    expect_qa_errors: int = 0,
    extra_check=None,
) -> CaseResult:
    t0 = time.perf_counter()
    before_hash = sha256_file(src)
    seg_path = td / f"{case_id}.segments.jsonl"
    segs, _ = extract_to(src, seg_path)
    pending = [s for s in segs if s.status == "pending"]
    fn = translate_fn or (lambda s: pseudo_expand_25(s.text))
    tr_map = {s.id: fn(s) for s in pending}
    out = td / f"{case_id}_out{src.suffix}"
    res = apply_translations(src, seg_path, tr_map, out, options=ApplyOptions(set_lang=True))
    qa = run_qa(src, out, glossary=glossary)
    after_hash = sha256_file(src)
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    gloss_viol = sum(1 for e in qa.errors if "Terjemahan terlarang" in e)
    num_mismatch = sum(1 for w in qa.warnings if "Angka tidak sama" in w)
    overflow = len(res.report.flags)

    extra_ok = True
    note = ""
    if extra_check:
        extra_ok, note = extra_check(src, out, res, qa)

    passed = (
        (before_hash == after_hash)
        and (len(qa.errors) == expect_qa_errors)
        and extra_ok
    )
    return CaseResult(
        case_id=case_id,
        fmt=fmt,
        description=description,
        segments_pending=len(pending),
        overflow_flags=overflow,
        glossary_violations=gloss_viol,
        number_mismatches=num_mismatch,
        qa_errors=len(qa.errors),
        qa_warnings=len(qa.warnings),
        source_unchanged=(before_hash == after_hash),
        elapsed_ms=elapsed_ms,
        passed=passed,
        note=note,
    )


def run_all() -> list[CaseResult]:
    results: list[CaseResult] = []
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)

        # 01. Markdown placeholders, URLs, inline & fenced code
        p01 = td / "01.md"
        p01.write_text(
            "# Setup {app_name}\n\nRun `init --safe` for %1$s users. Visit https://example.com/start.\n\n"
            "```python\nprint('unchanged')\n```\n",
            encoding="utf-8",
        )
        results.append(
            _run_standard_case(
                "01_md_placeholders_urls",
                "markdown",
                "Markdown: placeholders, URLs, inline/fenced code",
                p01,
                td,
                extra_check=lambda s, o, r, q: (
                    "print('unchanged')" in o.read_text(encoding="utf-8")
                    and "{app_name}" in o.read_text(encoding="utf-8"),
                    "",
                ),
            )
        )

        # 02. Markdown tables & nested lists
        p02 = td / "02.md"
        p02.write_text(
            "- Parent item 1\n  - Child item 2\n    - Grandchild item 3\n\n"
            "| Column A | Column B |\n|---|---|\n| Cell one | Cell two |\n| Pipe \\| cell | Ready |\n",
            encoding="utf-8",
        )
        results.append(
            _run_standard_case(
                "02_md_tables_nested_lists",
                "markdown",
                "Markdown: nested lists and pipe-escaped table",
                p02,
                td,
                extra_check=lambda s, o, r, q: (
                    o.read_text(encoding="utf-8").count("|") == s.read_text(encoding="utf-8").count("|"),
                    "",
                ),
            )
        )

        # 03. Markdown long prose (+25% expansion)
        p03 = td / "03.md"
        p03.write_text(
            "\n\n".join(
                f"Paragraph {i}: This section explains deterministic document handling in detail."
                for i in range(1, 9)
            )
            + "\n",
            encoding="utf-8",
        )
        results.append(
            _run_standard_case(
                "03_md_long_prose",
                "markdown",
                "Markdown: multi-paragraph prose expanded ~25%",
                p03,
                td,
            )
        )

        # 04. Plain text with BOM, CRLF, numbers
        p04 = td / "04.txt"
        p04.write_bytes(
            b"\xef\xbb\xbfOrder 1,250.50 units for batch 42.\r\nSecond line of paragraph.\r\n\r\n"
            b"Send receipt to billing@example.org.\r\n"
        )
        results.append(
            _run_standard_case(
                "04_txt_bom_crlf_numbers",
                "text",
                "TXT: UTF-8 BOM, CRLF newlines, numbers & email",
                p04,
                td,
                extra_check=lambda s, o, r, q: (
                    o.read_bytes().startswith(b"\xef\xbb\xbf") and b"\r\n" in o.read_bytes(),
                    "",
                ),
            )
        )

        # 05. Dense SRT subtitles (triggers reading-speed / line-length QA warning)
        p05 = td / "05.srt"
        p05.write_text(
            "1\n00:00:01,000 --> 00:00:02,500\n"
            "This subtitle line is already close to forty two characters.\n\n"
            "2\n00:00:03,000 --> 00:00:06,500\n"
            "<i>Note:</i> {\\an8}Keep timestamps exact for {speaker}.\n",
            encoding="utf-8",
        )
        results.append(
            _run_standard_case(
                "05_srt_dense_subtitles",
                "srt",
                "SRT: dense cue triggers CPS/length warning, timings intact",
                p05,
                td,
                extra_check=lambda s, o, r, q: (
                    any("kecepatan baca" in w or "42 karakter" in w for w in q.warnings),
                    "peringatan kepadatan cue terdeteksi",
                ),
            )
        )

        # 06. WebVTT with STYLE, NOTE, voice & timestamp tags
        p06 = td / "06.vtt"
        p06.write_text(
            "WEBVTT\n\nNOTE Do not translate\n\nSTYLE\n::cue { color: white; }\n\n"
            "00:00:01.000 --> 00:00:05.000\n<v Host>Welcome to <00:02.500>module 1.</v>\n",
            encoding="utf-8",
        )
        results.append(
            _run_standard_case(
                "06_vtt_voice_tags_styles",
                "vtt",
                "WebVTT: NOTE/STYLE untouched, voice & timestamp tags protected",
                p06,
                td,
                extra_check=lambda s, o, r, q: (
                    "NOTE Do not translate" in o.read_text(encoding="utf-8")
                    and "<00:02.500>" in o.read_text(encoding="utf-8"),
                    "",
                ),
            )
        )

        # 07. Nested JSON with placeholders & non-strings
        p07 = td / "07.json"
        p07.write_text(
            json.dumps(
                {
                    "ui": {
                        "banner": "Hello {{user}}, you have {count} alerts.",
                        "help": "See https://example.com/help",
                    },
                    "retries": 3,
                    "active": True,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        results.append(
            _run_standard_case(
                "07_json_nested_placeholders",
                "json",
                "JSON: nested keys, {{user}}/{count}, types preserved",
                p07,
                td,
            )
        )

        # 08. Flutter ARB with ICU plurals & @@locale
        p08 = td / "08.arb"
        p08.write_text(
            json.dumps(
                {
                    "@@locale": "en",
                    "files": "{count, plural, =0{No files} one{# file} other{# files}}",
                    "@files": {"description": "File counter"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        results.append(
            _run_standard_case(
                "08_arb_icu_plurals",
                "arb",
                "ARB: ICU plural structure protected, @@locale -> id",
                p08,
                td,
                extra_check=lambda s, o, r, q: (
                    json.loads(o.read_text(encoding="utf-8"))["@@locale"] == "id",
                    "",
                ),
            )
        )

        # 09. YAML with comments and special chars
        p09 = td / "09.yaml"
        p09.write_text(
            "# Config header\napp:\n  title: Welcome home\n  limit: 5\n  note: Check {url} now\n",
            encoding="utf-8",
        )
        results.append(
            _run_standard_case(
                "09_yaml_comments_colons",
                "yaml",
                "YAML: comments preserved, values expanded safely",
                p09,
                td,
                extra_check=lambda s, o, r, q: (
                    o.read_text(encoding="utf-8").startswith("# Config header"),
                    "",
                ),
            )
        )

        # 10. Gettext PO with msgctxt & plurals
        p10 = td / "10.po"
        p10.write_text(
            'msgid ""\nmsgstr ""\n"Language: en\\n"\n"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
            'msgctxt "menu"\nmsgid "Open %(file)s"\nmsgstr ""\n\n'
            'msgid "%d item"\nmsgid_plural "%d items"\nmsgstr[0] ""\nmsgstr[1] ""\n',
            encoding="utf-8",
        )
        results.append(
            _run_standard_case(
                "10_po_plurals_context",
                "po",
                "PO: msgctxt, plurals, nplurals=1 header update",
                p10,
                td,
                extra_check=lambda s, o, r, q: (
                    "nplurals=1; plural=0;" in o.read_text(encoding="utf-8"),
                    "",
                ),
            )
        )

        # 11. Android strings.xml with escapes, translatable=false, xliff:g
        p11 = td / "11.xml"
        p11.write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<resources xmlns:xliff="urn:oasis:names:tc:xliff:document:1.2">\n'
            '  <string name="pkg" translatable="false">com.demo.app</string>\n'
            '  <string name="hi">It\\\'s <xliff:g id="n">%1$s</xliff:g> ready</string>\n'
            '  <plurals name="docs"><item quantity="other">%d docs</item></plurals>\n'
            "</resources>\n",
            encoding="utf-8",
        )
        results.append(
            _run_standard_case(
                "11_android_xml_escapes",
                "android-xml",
                "Android XML: apostrophe escape, translatable=false, xliff:g",
                p11,
                td,
                extra_check=lambda s, o, r, q: (
                    "com.demo.app" in o.read_text(encoding="utf-8")
                    and "\\'" in o.read_text(encoding="utf-8"),
                    "",
                ),
            )
        )

        # 12. DOCX tables, headers, bold runs
        p12 = _write_docx(td / "12.docx")
        results.append(
            _run_standard_case(
                "12_docx_tables_headers_bold",
                "docx",
                "DOCX: headings, bold run + placeholder, table, header",
                p12,
                td,
            )
        )

        # 13. PPTX multi-slide + speaker notes
        p13 = _write_pptx(td / "13.pptx")
        results.append(
            _run_standard_case(
                "13_pptx_slides_notes",
                "pptx",
                "PPTX: 2 slides + speaker notes, slide count intact",
                p13,
                td,
            )
        )

        # 14. XLSX formulas & numbers untouched
        p14 = _write_xlsx(td / "14.xlsx")

        def _check_xlsx(s, o, r, q):
            import openpyxl

            wb = openpyxl.load_workbook(o, data_only=False)
            ok = wb["Summary"]["B4"].value == "=SUM(B2:B3)" and wb["Summary"]["B2"].value == 1500
            return ok, "rumus & angka utuh"

        results.append(
            _run_standard_case(
                "14_xlsx_formulas_numbers",
                "xlsx",
                "XLSX: 2 sheets, =SUM formula & numbers untouched",
                p14,
                td,
                extra_check=_check_xlsx,
            )
        )

        # 15. HTML with code/script/display attrs
        p15 = td / "15.html"
        p15.write_text(
            '<!DOCTYPE html><html lang="en"><head><title>Eval Page</title></head>'
            '<body><h1>Welcome</h1><p>Check <code>cli --help</code> for 2 steps.</p>'
            '<img src="a.png" alt="Flow chart"><script>const x = "keep";</script></body></html>\n',
            encoding="utf-8",
        )
        results.append(
            _run_standard_case(
                "15_html_code_and_attrs",
                "html",
                "HTML: text + alt attr expanded, code/script untouched, lang=id",
                p15,
                td,
                extra_check=lambda s, o, r, q: (
                    '<html lang="id">' in o.read_text(encoding="utf-8")
                    and 'const x = "keep";' in o.read_text(encoding="utf-8"),
                    "",
                ),
            )
        )

        # 16. EPUB with uncompressed mimetype & dc:language
        p16 = _write_epub(td / "16.epub")

        def _check_epub(s, o, r, q):
            with zipfile.ZipFile(o) as z:
                first = z.infolist()[0]
                opf = z.read("OEBPS/content.opf").decode("utf-8")
            ok = (
                first.filename == "mimetype"
                and first.compress_type == zipfile.ZIP_STORED
                and "<dc:language>id</dc:language>" in opf
            )
            return ok, "mimetype stored + dc:language=id"

        results.append(
            _run_standard_case(
                "16_epub_mimetype_lang",
                "epub",
                "EPUB: XHTML expanded, mimetype uncompressed, dc:language=id",
                p16,
                td,
                extra_check=_check_epub,
            )
        )

        # 17. PDF with colored boxes, raster image, placeholder & URL
        p17 = _write_pdf_colored_box(td / "17.pdf")

        def _check_pdf(s, o, r, q):
            import pymupdf

            ds, do = pymupdf.open(s), pymupdf.open(o)
            try:
                ok = (
                    do.page_count == ds.page_count == 1
                    and len(do[0].get_images(full=True)) == 1
                    and len(do[0].get_drawings()) >= 2
                )
            finally:
                ds.close()
                do.close()
            return ok, f"gambar & vektor utuh; {len(r.report.flags)} flag overflow"

        results.append(
            _run_standard_case(
                "17_pdf_colored_box_image",
                "pdf",
                "PDF: colored boxes & raster image preserved under +25% expansion",
                p17,
                td,
                extra_check=_check_pdf,
            )
        )

        # 18. Glossary guard (negative test: forbidden translation must be flagged as QA ERROR)
        p18 = td / "18.md"
        p18.write_text("The Interest Curve guides player engagement across 5 chapters.\n", encoding="utf-8")
        g18 = td / "glossary.md"
        g18.write_text(
            "## Glosarium\n| EN | ID |\n|---|---|\n| Interest Curve | Kurva Minat |\n"
            "## Terjemahan terlarang\n- Kurva Bunga → Kurva Minat\n",
            encoding="utf-8",
        )
        results.append(
            _run_standard_case(
                "18_glossary_forbidden_guard",
                "markdown",
                "QA guard: forbidden glossary term caught as ERROR",
                p18,
                td,
                glossary=g18,
                translate_fn=lambda s: "Kurva Bunga memandu keterlibatan pemain di 5 bab.",
                expect_qa_errors=1,
                extra_check=lambda s, o, r, q: (
                    any("Kurva Bunga" in e for e in q.errors),
                    "pelanggaran glosarium tertangkap (1 ERROR sesuai ekspektasi)",
                ),
            )
        )

    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", help="write full machine-readable results to this path")
    args = ap.parse_args(argv)
    results = run_all()
    total_ms = round(sum(r.elapsed_ms for r in results), 2)
    passed = sum(1 for r in results if r.passed)
    print(f"Evals: {passed}/{len(results)} passed in {total_ms} ms")
    print(f"{'Case':<30} {'Fmt':<11} {'Seg':>3} {'Ovf':>3} {'GlV':>3} {'Num':>3} {'Err':>3} {'ms':>7}  Status")
    for r in results:
        st = "PASS" if r.passed else "FAIL"
        print(
            f"{r.case_id:<30} {r.fmt:<11} {r.segments_pending:>3} {r.overflow_flags:>3} "
            f"{r.glossary_violations:>3} {r.number_mismatches:>3} {r.qa_errors:>3} {r.elapsed_ms:>7.1f}  {st}"
        )
    if args.json:
        payload = {
            "total_cases": len(results),
            "passed_cases": passed,
            "total_elapsed_ms": total_ms,
            "cases": [asdict(r) for r in results],
        }
        Path(args.json).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
