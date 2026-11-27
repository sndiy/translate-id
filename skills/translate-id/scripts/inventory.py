#!/usr/bin/env python3
"""
inventory.py - Inspeksi file SEBELUM menerjemahkan. Tidak mengubah file apa pun.

Pakai:  python inventory.py <file> [--json out.json]

Melaporkan: tipe, ukuran, enkripsi (PDF), jumlah halaman/slide/sheet, apakah ada
text layer, halaman yang kemungkinan hasil scan, font, jumlah gambar/link, dan
rekomendasi strategi. Dependensi opsional: PyMuPDF (pip install pymupdf).
"""
import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

TEXT_EXT = {".txt", ".md", ".markdown", ".srt", ".vtt", ".csv", ".tsv", ".json",
            ".yaml", ".yml", ".html", ".htm", ".xml", ".po", ".arb", ".strings",
            ".tex", ".rst"}


def detect_encoding(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            pass
    for enc in ("utf-16", "cp1252", "latin-1"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            pass
    return "unknown"


def inv_pdf(p: Path) -> dict:
    try:
        import pymupdf as fitz  # type: ignore
    except ImportError:
        try:
            import fitz  # type: ignore
        except ImportError:
            return {"error": "PyMuPDF tidak terpasang. Jalankan: pip install pymupdf"}
    doc = fitz.open(p)
    info = {
        "encrypted": bool(doc.is_encrypted),
        "needs_password": bool(doc.needs_pass),
        "pages": doc.page_count,
        "metadata": {k: v for k, v in (doc.metadata or {}).items() if v},
    }
    if doc.needs_pass:
        info["verdict"] = "BERHENTI: PDF terkunci. Jangan coba membuka/menghapus proteksi."
        return info
    sizes, fonts, low_text, imgs, links, chars = set(), {}, [], 0, 0, 0
    for i, page in enumerate(doc, 1):
        r = page.rect
        sizes.add((round(r.width, 1), round(r.height, 1)))
        text = page.get_text("text") or ""
        n = len(text.strip())
        chars += n
        if n < 40:
            low_text.append(i)
        imgs += len(page.get_images(full=True))
        links += len(page.get_links())
        for f in page.get_fonts(full=True):
            name = f[3]
            fonts[name] = fonts.get(name, 0) + 1
    info.update({
        "page_sizes": sorted(sizes),
        "text_chars": chars,
        "pages_with_little_text": low_text[:200],
        "pages_with_little_text_count": len(low_text),
        "images": imgs,
        "links": links,
        "fonts": dict(sorted(fonts.items(), key=lambda kv: -kv[1])[:25]),
    })
    ratio = len(low_text) / max(doc.page_count, 1)
    if chars == 0 or ratio > 0.8:
        info["verdict"] = ("Kemungkinan PDF hasil scan (tanpa text layer). Perlu OCR "
                           "(mis. ocrmypdf -l eng) sebelum diterjemahkan; layout fidelity rendah.")
    else:
        info["verdict"] = ("Ada text layer. Strategi: ekstrak per blok dengan bbox, terjemahkan, "
                           "redaksi teks lama tanpa menghapus gambar/vektor, tulis ulang di bbox yang sama.")
    return info


def inv_ooxml(p: Path, kind: str) -> dict:
    info: dict = {}
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        info["parts"] = len(names)
        info["media_files"] = sum(1 for n in names if "/media/" in n)
        if kind == "docx":
            xml = z.read("word/document.xml").decode("utf8", "ignore")
            info["paragraphs"] = xml.count("<w:p ") + xml.count("<w:p>")
            info["tables"] = xml.count("<w:tbl>")
            info["has_comments"] = "word/comments.xml" in names
            info["has_footnotes"] = "word/footnotes.xml" in names
            info["has_tracked_changes"] = bool(re.search(r"<w:(ins|del) ", xml))
            info["headers_footers"] = sum(1 for n in names if re.match(r"word/(header|footer)\d*\.xml", n))
            info["text_boxes"] = xml.count("<w:txbxContent")
        elif kind == "pptx":
            slides = [n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)]
            info["slides"] = len(slides)
            info["notes_slides"] = sum(1 for n in names if re.match(r"ppt/notesSlides/notesSlide\d+\.xml$", n))
            info["charts"] = sum(1 for n in names if n.startswith("ppt/charts/chart"))
            info["smartart"] = sum(1 for n in names if n.startswith("ppt/diagrams/data"))
        elif kind == "xlsx":
            wb = z.read("xl/workbook.xml").decode("utf8", "ignore")
            info["sheets"] = re.findall(r'<sheet [^>]*name="([^"]+)"', wb)
            if "xl/sharedStrings.xml" in names:
                ss = z.read("xl/sharedStrings.xml").decode("utf8", "ignore")
                info["shared_strings"] = ss.count("<si>")
            info["formulas_hint"] = any(
                b"<f>" in z.read(n) or b"<f " in z.read(n)
                for n in names if n.startswith("xl/worksheets/sheet"))
    info["verdict"] = ("Terjemahkan per run/sel dengan library OOXML; jangan ekspor ulang lewat PDF. "
                       "Lihat references/layout-by-format.md.")
    return info


def inv_text(p: Path) -> dict:
    raw = p.read_bytes()
    enc = detect_encoding(raw)
    text = raw.decode(enc if enc != "unknown" else "latin-1", "ignore")
    info = {
        "encoding": enc,
        "lines": text.count("\n") + 1,
        "chars": len(text),
        "bom": raw.startswith(b"\xef\xbb\xbf"),
        "crlf": b"\r\n" in raw,
        "code_fences": text.count("```") // 2,
        "urls": len(re.findall(r"https?://\S+", text)),
        "placeholders": len(re.findall(r"\{[^{}\s]+\}|%\d*\$?[sdif]|\{\{[^}]+\}\}", text)),
    }
    if p.suffix.lower() in {".srt", ".vtt"}:
        info["cues"] = len(re.findall(r"\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->", text))
    info["verdict"] = ("Pertahankan encoding, BOM, dan jenis baris baru yang sama. "
                       "Jangan terjemahkan kunci, kode, URL, atau placeholder.")
    return info


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--json")
    a = ap.parse_args()
    p = Path(a.file)
    if not p.is_file():
        sys.exit(f"File tidak ditemukan: {p}")
    ext = p.suffix.lower()
    out = {"file": str(p), "type": ext.lstrip("."), "size_bytes": p.stat().st_size}
    if ext == ".pdf":
        out.update(inv_pdf(p))
    elif ext in {".docx", ".pptx", ".xlsx"}:
        out.update(inv_ooxml(p, ext.lstrip(".")))
    elif ext == ".epub":
        with zipfile.ZipFile(p) as z:
            out["xhtml_files"] = sum(1 for n in z.namelist() if n.lower().endswith((".xhtml", ".html")))
        out["verdict"] = "Terjemahkan text node di tiap XHTML; ubah dc:language ke id."
    elif ext in TEXT_EXT:
        out.update(inv_text(p))
    else:
        out["verdict"] = "Tipe file belum dikenal. Laporkan ke pengguna sebelum melanjutkan."
    txt = json.dumps(out, indent=2, ensure_ascii=False)
    print(txt)
    if a.json:
        Path(a.json).write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
