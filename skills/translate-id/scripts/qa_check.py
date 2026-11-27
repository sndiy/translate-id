#!/usr/bin/env python3
"""
qa_check.py - Pemeriksaan otomatis hasil terjemahan Inggris -> Indonesia.

Pakai:
  python qa_check.py --source SUMBER --target HASIL [--glossary glossary.md]
                     [--report reports/qa.md] [--strict]

Format yang bisa dibaca: pdf, docx, pptx, xlsx, txt, md, srt, vtt, csv, json, html.
Pemeriksaan:
  1. Jumlah halaman (PDF) / slide (PPTX) / sheet (XLSX) sama
  2. Angka sama (dibandingkan tanpa pemisah ribuan/desimal)
  3. Placeholder sama: {x} {{x}} %s %1$s <tag>
  4. Semua URL sumber masih ada di hasil
  5. Terjemahan terlarang dari glosarium (bagian "Terjemahan terlarang")
  6. Istilah glosarium: istilah sumber ada tetapi padanan Indonesia tidak muncul
  7. Sisa bahasa Inggris (heuristik stopword)
  8. Rasio panjang teks hasil/sumber wajar
  9. Ejaan (jika hunspell + kamus id_ID terpasang; jika tidak, dilewati)
Hasil: ringkasan di layar + file laporan Markdown (tidak menimpa file lama).
Skrip ini heuristik: ia menemukan kecurigaan, bukan membuktikan terjemahan benar.
"""
import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path

EN_STOP = set("""the and of to is that with for are you this it as be was were by on at from or
an not have has had they their there which will would can could should our your we he she his her
but if so than then these those into about also more most such what when where who whom why how
been being do does did done just only over under between each other any some all""".split())
ID_STOP = set("""yang dan di ke dari untuk dengan pada adalah ini itu atau juga tidak akan dalam
bisa dapat oleh sebagai karena agar saat jika kami kita anda kamu mereka dia ada sudah telah
lebih sangat para sebuah seperti tetapi namun maka""".split())
URL_RE = re.compile(r"https?://[^\s)>\]\"']+")
PH_RE = re.compile(r"\{\{[^{}]+\}\}|\{[^{}\s]+\}|%\d*\$?[sdif]|</?[a-zA-Z][^>\s]*>")


def _read_text_file(p: Path) -> str:
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", "ignore")


def _xml_text(xml: str, tag: str) -> str:
    return " ".join(re.findall(rf"<{tag}[^>]*>([^<]*)</{tag}>", xml))


def extract(p: Path):
    """Kembalikan (teks_penuh, jumlah_unit, nama_unit)."""
    ext = p.suffix.lower()
    if ext == ".pdf":
        try:
            import pymupdf as fitz  # type: ignore
        except ImportError:
            import fitz  # type: ignore
        doc = fitz.open(p)
        return "\n".join(pg.get_text("text") for pg in doc), doc.page_count, "halaman"
    if ext == ".docx":
        with zipfile.ZipFile(p) as z:
            xml = z.read("word/document.xml").decode("utf8", "ignore")
        return _xml_text(xml, "w:t"), None, ""
    if ext == ".pptx":
        with zipfile.ZipFile(p) as z:
            names = sorted(n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n))
            text = "\n".join(_xml_text(z.read(n).decode("utf8", "ignore"), "a:t") for n in names)
        return text, len(names), "slide"
    if ext == ".xlsx":
        with zipfile.ZipFile(p) as z:
            wb = z.read("xl/workbook.xml").decode("utf8", "ignore")
            sheets = re.findall(r"<sheet ", wb)
            ss = z.read("xl/sharedStrings.xml").decode("utf8", "ignore") if "xl/sharedStrings.xml" in z.namelist() else ""
        return _xml_text(ss, "t"), len(sheets), "sheet"
    return _read_text_file(p), None, ""


def number_tokens(text: str) -> Counter:
    # "1,000" dan "1.000" sama-sama menjadi "1","000"; "3.5" dan "3,5" menjadi "3","5"
    return Counter(re.findall(r"\d+", text))


def parse_glossary(path: Path):
    pairs, forbidden = [], []
    section = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            section = line.lower()
            continue
        if "terlarang" in section:
            m = re.match(r"\s*[-*]\s*(.+?)\s*(?:→|->)\s*(.+)", line)
            if m:
                forbidden.append((m.group(1).strip(" `\"'"), m.group(2).strip(" `\"'")))
        elif "glosarium" in section and line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and cells[0] and not set(cells[0]) <= set("-: ") and cells[0].lower() not in {"en", "inggris", "english"}:
                pairs.append((cells[0], cells[1]))
    return pairs, forbidden


def english_leftovers(text: str, limit: int = 40):
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if len(s) < 25 or URL_RE.fullmatch(s):
            continue
        words = re.findall(r"[A-Za-z']+", s.lower())
        if len(words) < 6:
            continue
        en = sum(w in EN_STOP for w in words)
        idn = sum(w in ID_STOP for w in words)
        if en >= 3 and en / len(words) > 0.2 and en > idn:
            out.append(s[:140])
            if len(out) >= limit:
                break
    return out


def spellcheck(text: str):
    if not shutil.which("hunspell"):
        return None, "hunspell tidak terpasang; ejaan dilewati"
    try:
        r = subprocess.run(["hunspell", "-d", "id_ID", "-l"], input=text, capture_output=True,
                           text=True, timeout=120)
    except Exception as e:  # noqa: BLE001
        return None, f"hunspell gagal: {e}"
    if r.returncode != 0 and not r.stdout:
        return None, "kamus id_ID tidak tersedia; ejaan dilewati"
    words = Counter(w for w in r.stdout.split() if len(w) > 2)
    return words.most_common(60), ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--glossary")
    ap.add_argument("--report")
    ap.add_argument("--strict", action="store_true", help="exit 1 jika ada ERROR")
    a = ap.parse_args()

    src_p, tgt_p = Path(a.source), Path(a.target)
    for p in (src_p, tgt_p):
        if not p.is_file():
            sys.exit(f"File tidak ditemukan: {p}")
    if src_p.resolve() == tgt_p.resolve():
        sys.exit("ERROR: sumber dan hasil adalah file yang sama.")

    src, sn, unit = extract(src_p)
    tgt, tn, _ = extract(tgt_p)
    errors, warns, notes = [], [], []

    # 1. unit
    if sn is not None and tn is not None:
        if sn != tn:
            errors.append(f"Jumlah {unit} berbeda: sumber {sn}, hasil {tn}.")
        else:
            notes.append(f"Jumlah {unit} sama: {sn}.")

    # 2. angka
    ns, nt = number_tokens(src), number_tokens(tgt)
    miss, extra = ns - nt, nt - ns
    if miss or extra:
        warns.append(
            "Angka tidak sama. Hilang di hasil: "
            f"{dict(list(miss.items())[:15])}; muncul baru: {dict(list(extra.items())[:15])}. "
            "Wajar bila kata-angka diubah menjadi digit atau sebaliknya; periksa manual.")
    else:
        notes.append("Semua angka cocok.")

    # 3. placeholder
    ps, pt = Counter(PH_RE.findall(src)), Counter(PH_RE.findall(tgt))
    if ps != pt:
        errors.append(f"Placeholder/tag tidak sama. Hilang: {dict((ps - pt))}; berlebih: {dict((pt - ps))}.")
    else:
        notes.append(f"Placeholder/tag cocok ({sum(ps.values())}).")

    # 4. URL
    us, ut = set(URL_RE.findall(src)), set(URL_RE.findall(tgt))
    lost = sorted(us - ut)
    if lost:
        errors.append(f"URL hilang/berubah ({len(lost)}): {lost[:5]}")
    else:
        notes.append(f"Semua URL utuh ({len(us)}).")

    # 5-6. glosarium
    if a.glossary:
        gp = Path(a.glossary)
        if gp.is_file():
            pairs, forbidden = parse_glossary(gp)
            low_t, low_s = tgt.lower(), src.lower()

            def count_word(term: str, text: str) -> int:
                # batas kata, agar "art" tidak cocok dengan "part"
                return len(re.findall(rf"(?<!\w){re.escape(term.lower())}(?!\w)", text))

            for bad, good in forbidden:
                c = count_word(bad, low_t)
                if c:
                    errors.append(f'Terjemahan terlarang "{bad}" muncul {c}x (seharusnya "{good}").')
            for en, idn in pairs:
                alts = [x.strip() for x in idn.split("/") if x.strip()]
                if count_word(en, low_s) and not any(count_word(x, low_t) for x in alts):
                    warns.append(f'Istilah "{en}" ada di sumber, tetapi "{idn}" tidak ditemukan di hasil.')
            notes.append(f"Glosarium dipakai: {len(pairs)} istilah, {len(forbidden)} terjemahan terlarang.")
        else:
            warns.append(f"Glosarium tidak ditemukan: {gp}")

    # 7. sisa Inggris
    left = english_leftovers(tgt)
    if left:
        warns.append(f"Kemungkinan sisa bahasa Inggris pada {len(left)}+ baris (contoh di bawah).")

    # 8. rasio panjang
    if len(src) > 200:
        r = len(tgt) / max(len(src), 1)
        if r < 0.75 or r > 1.6:
            warns.append(f"Rasio panjang hasil/sumber = {r:.2f} (biasanya sekitar 1,0-1,3). Cek teks hilang atau berlebih.")
        else:
            notes.append(f"Rasio panjang wajar: {r:.2f}.")

    # 9. ejaan
    sp, sp_note = spellcheck(tgt)
    if sp_note:
        notes.append(sp_note)
    elif sp:
        warns.append(f"Kata tidak dikenal kamus id_ID (teratas): {[w for w, _ in sp[:25]]}")

    lines = ["# Laporan QA terjemahan", "",
             f"- Sumber: `{src_p}`", f"- Hasil: `{tgt_p}`", "",
             f"**ERROR: {len(errors)} | PERINGATAN: {len(warns)}**", ""]
    for title, items in (("ERROR", errors), ("PERINGATAN", warns), ("CATATAN", notes)):
        lines.append(f"## {title}")
        lines += [f"- {x}" for x in items] or ["- (tidak ada)"]
        lines.append("")
    if left:
        lines += ["## Contoh baris yang masih tampak Inggris", *[f"- {x}" for x in left[:20]], ""]
    lines += ["> Laporan ini heuristik. Lulus QA bukan bukti terjemahan sempurna; "
              "tinjau halaman/segmen yang ditandai dan sampel acak secara manual."]
    report = "\n".join(lines)
    print(report)

    if a.report:
        rp = Path(a.report)
        i = 2
        while rp.exists():  # jangan menimpa laporan lama
            rp = rp.with_name(f"{Path(a.report).stem}-{i}{Path(a.report).suffix}")
            i += 1
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(report, encoding="utf-8")
        print(f"\nLaporan disimpan: {rp}")
    if a.strict and errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
