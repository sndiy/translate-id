"""Shared test helpers: pseudo-translation and generic round-trip runner."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from id_translate.formats.base import ApplyOptions
from id_translate.pipeline import apply_translations, extract_file
from id_translate.protect import TOKEN_RE, restore, strip_tokens
from id_translate.segments import Segment, write_segments

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def pseudo(text: str) -> str:
    """Pseudo-translation: ~30%+ longer, non-ASCII, tokens kept in place."""
    plain = strip_tokens(text)
    return "Ïd " + text + " " + "ž" * max(3, len(plain) // 3)


def identity(seg: Segment) -> str:
    return seg.text


def run_roundtrip(src: Path, tmp: Path, translate=identity, set_lang: bool = False, name: str = "out"):
    handler, segs, meta = extract_file(src)
    seg_path = tmp / f"{name}.segments.jsonl"
    write_segments(seg_path, segs, meta)
    translations = {s.id: translate(s) for s in segs if s.status == "pending"}
    out = tmp / f"{name}{src.suffix}"
    res = apply_translations(src, seg_path, translations, out, options=ApplyOptions(set_lang=set_lang))
    return handler, segs, out, res


def restored(seg: Segment) -> str:
    return restore(seg.text, seg.protect)


def assert_reextract_matches(handler, segs, out: Path, expected) -> None:
    """Re-extract the output and compare restored texts with ``expected(seg)`` per pending segment."""
    again = handler.extract(out)
    src_pending = [s for s in segs if s.status == "pending"]
    out_pending = [s for s in again if s.status == "pending"]
    assert len(out_pending) == len(src_pending), (len(out_pending), len(src_pending))
    for a, b in zip(src_pending, out_pending):
        want = expected(a)
        got = restored(b)
        assert got == want, f"{a.id}: {got!r} != {want!r}"


def expected_pseudo(seg: Segment) -> str:
    return restore(pseudo(seg.text), seg.protect)


def cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "id_translate", *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=cwd,
        check=False,
    )


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text)
