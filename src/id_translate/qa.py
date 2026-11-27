"""Automated QA between a source file and its translated output (heuristics, not proof)."""

from __future__ import annotations

import re
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from id_translate.formats import handler_for_path
from id_translate.glossary import count_term, parse_glossary

EN_STOP = set(
    "the and of to is that with for are you this it as be was were by on at from or an not have has had "
    "they their there which will would can could should our your we he she his her but if so than then "
    "these those into about also more most such what when where who whom why how been being do does did "
    "done just only over under between each other any some all".split()
)
ID_STOP = set(
    "yang dan di ke dari untuk dengan pada adalah ini itu atau juga tidak akan dalam bisa dapat oleh "
    "sebagai karena agar saat jika kami kita anda kamu mereka dia ada sudah telah lebih sangat para "
    "sebuah seperti tetapi namun maka".split()
)
URL_RE = re.compile(r"https?://[^\s)>\]\"']+")
PH_RE = re.compile(r"\{\{[^{}]+\}\}|\{[^{}\s]+\}|%\d*\$?[sdif]|</?[a-zA-Z][^>\s]*>")


@dataclass
class QAResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    leftovers: list[str] = field(default_factory=list)

    def to_markdown(self, source: Path, target: Path) -> str:
        lines = [
            "# Laporan QA terjemahan",
            "",
            f"- Sumber: `{source}`",
            f"- Hasil: `{target}`",
            "",
            f"**ERROR: {len(self.errors)} | PERINGATAN: {len(self.warnings)}**",
            "",
        ]
        for title, items in (("ERROR", self.errors), ("PERINGATAN", self.warnings), ("CATATAN", self.notes)):
            lines.append(f"## {title}")
            lines += [f"- {x}" for x in items] or ["- (tidak ada)"]
            lines.append("")
        if self.leftovers:
            lines += ["## Contoh baris yang masih tampak Inggris", *[f"- {x}" for x in self.leftovers[:20]], ""]
        lines.append(
            "> Laporan ini heuristik. Lulus QA bukan bukti terjemahan sempurna; tinjau segmen yang "
            "ditandai dan sampel acak secara manual."
        )
        return "\n".join(lines) + "\n"


def english_leftovers(text: str, limit: int = 40) -> list[str]:
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


def spellcheck(text: str) -> tuple[list[tuple[str, int]] | None, str]:
    exe = shutil.which("hunspell")
    if not exe:
        return None, "hunspell tidak terpasang; ejaan dilewati"
    try:
        r = subprocess.run(
            [exe, "-d", "id_ID", "-l"], input=text, capture_output=True, text=True, timeout=120, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"hunspell gagal: {exc}"
    if r.returncode != 0 and not r.stdout:
        return None, "kamus id_ID tidak tersedia; ejaan dilewati"
    return Counter(w for w in r.stdout.split() if len(w) > 2).most_common(60), ""


def run_qa(source: Path, target: Path, glossary: Path | None = None, fmt: str | None = None) -> QAResult:
    source, target = Path(source), Path(target)
    handler = handler_for_path(source, fmt)
    handler.ensure_available()
    res = QAResult()
    src, tgt = handler.qa_text(source), handler.qa_text(target)

    su, tu = handler.unit_count(source), handler.unit_count(target)
    if su and tu:
        if su[0] != tu[0]:
            res.errors.append(f"Jumlah {su[1]} berbeda: sumber {su[0]}, hasil {tu[0]}.")
        else:
            res.notes.append(f"Jumlah {su[1]} sama: {su[0]}.")

    ns, nt = Counter(re.findall(r"\d+", src)), Counter(re.findall(r"\d+", tgt))
    miss, extra = ns - nt, nt - ns
    if miss or extra:
        res.warnings.append(
            f"Angka tidak sama. Hilang di hasil: {dict(list(miss.items())[:15])}; muncul baru: "
            f"{dict(list(extra.items())[:15])}. Wajar bila format angka berubah; periksa manual."
        )
    else:
        res.notes.append("Semua angka cocok.")

    ps, pt = Counter(PH_RE.findall(src)), Counter(PH_RE.findall(tgt))
    if ps != pt:
        res.errors.append(f"Placeholder/tag tidak sama. Hilang: {dict(ps - pt)}; berlebih: {dict(pt - ps)}.")
    else:
        res.notes.append(f"Placeholder/tag cocok ({sum(ps.values())}).")

    us, ut = set(URL_RE.findall(src)), set(URL_RE.findall(tgt))
    lost = sorted(us - ut)
    if lost:
        res.errors.append(f"URL hilang/berubah ({len(lost)}): {lost[:5]}")
    else:
        res.notes.append(f"Semua URL utuh ({len(us)}).")

    if glossary:
        gp = Path(glossary)
        if gp.is_file():
            g = parse_glossary(gp)
            for bad, good in g.forbidden:
                c = count_term(bad, tgt)
                if c:
                    res.errors.append(f'Terjemahan terlarang "{bad}" muncul {c}x (seharusnya "{good}").')
            for en, idn in g.pairs:
                alts = [x.strip() for x in idn.split("/") if x.strip()]
                if count_term(en, src) and not any(count_term(x, tgt) for x in alts):
                    res.warnings.append(f'Istilah "{en}" ada di sumber, tetapi "{idn}" tidak ditemukan di hasil.')
            res.notes.append(f"Glosarium dipakai: {len(g.pairs)} istilah, {len(g.forbidden)} terjemahan terlarang.")
        else:
            res.warnings.append(f"Glosarium tidak ditemukan: {gp}")

    res.leftovers = english_leftovers(tgt)
    if res.leftovers:
        res.warnings.append(f"Kemungkinan sisa bahasa Inggris pada {len(res.leftovers)}+ baris.")

    if len(src) > 200:
        r = len(tgt) / max(len(src), 1)
        if r < 0.75 or r > 1.6:
            res.warnings.append(f"Rasio panjang hasil/sumber = {r:.2f} (biasanya 1,0–1,3).")
        else:
            res.notes.append(f"Rasio panjang wajar: {r:.2f}.")

    e, w, n = handler.extra_qa(source, target)
    res.errors += e
    res.warnings += w
    res.notes += n

    sp, sp_note = spellcheck(tgt)
    if sp_note:
        res.notes.append(sp_note)
    elif sp:
        res.warnings.append(f"Kata tidak dikenal kamus id_ID (teratas): {[w for w, _ in sp[:25]]}")
    return res
