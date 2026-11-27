"""Subtitle handlers: SubRip (.srt) and WebVTT (.vtt), edited in place.

Translated: cue text only.
Never touched: cue indices/identifiers, timestamps, cue settings, WEBVTT header, NOTE/STYLE/REGION
blocks, inline formatting/voice/timestamp tags, and ASS override tags like ``{\\an8}``.
"""

from __future__ import annotations

import re
from pathlib import Path

from id_translate.formats.textdoc import InPlaceTextHandler, TextDoc, line_spans, read_text_doc
from id_translate.protect import MARKUP_OPTIONS, has_translatable_text, mask, strip_tokens
from id_translate.segments import Segment

SRT_TIME_RE = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})(.*)$"
)
VTT_TIME_RE = re.compile(
    r"^(?:(\d{2}):)?(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(?:(\d{2}):)?(\d{2}):(\d{2})\.(\d{3})(.*)$"
)
ASS_TAG_RE = re.compile(r"\{\\[^}]+\}")
VTT_TS_TAG_RE = re.compile(r"<\d{2}:\d{2}(?::\d{2})?\.\d{3}>")
TAG_STRIP_RE = re.compile(r"</?[^>]+>|\{\\[^}]+\}")

MAX_LINES = 2
MAX_LINE_CHARS = 42
MAX_CPS = 17.0


def _seconds(h: str | None, m: str, s: str, ms: str) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _duration(match: re.Match) -> float:
    t1 = _seconds(match.group(1), match.group(2), match.group(3), match.group(4))
    t2 = _seconds(match.group(5), match.group(6), match.group(7), match.group(8))
    return max(0.0, round(t2 - t1, 3))


class _SubtitleBase(InPlaceTextHandler):
    time_re: re.Pattern
    extra_patterns: tuple[re.Pattern, ...] = ()
    id_prefix: str = "sub"

    def _iter_cues(self, text: str):
        """Yield (cue_number, timing_line, duration_s, payload_start, payload_end, payload_lines)."""
        spans = line_spans(text)
        lines = [text[s:e] for s, e, _ in spans]
        n = len(lines)
        i = 0
        cue_no = 0
        while i < n:
            if not lines[i].strip():
                i += 1
                continue
            # Collect one block until blank line
            block_start = i
            while i < n and lines[i].strip():
                i += 1
            block_end = i
            # Skip WebVTT header / NOTE / STYLE / REGION blocks
            first = lines[block_start].strip()
            if first.startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
                continue
            # Locate the timing line in the block (line 0 or line 1)
            t_idx = None
            t_match = None
            for k in range(block_start, min(block_start + 2, block_end)):
                m = self.time_re.match(lines[k].strip())
                if m:
                    t_idx = k
                    t_match = m
                    break
            if t_idx is None or t_match is None or t_idx + 1 >= block_end:
                continue
            cue_no += 1
            p_start = spans[t_idx + 1][0]
            p_end = spans[block_end - 1][1]
            payload_lines = lines[t_idx + 1 : block_end]
            yield cue_no, lines[t_idx].strip(), _duration(t_match), p_start, p_end, payload_lines

    def parse(self, doc: TextDoc, path: Path) -> list[Segment]:
        segs: list[Segment] = []
        for cue_no, timing, dur, p_start, p_end, payload_lines in self._iter_cues(doc.text):
            raw = "\n".join(payload_lines)
            masked, protect = mask(raw, MARKUP_OPTIONS, extra_patterns=self.extra_patterns)
            segs.append(
                Segment(
                    id=f"{self.id_prefix}{cue_no:04d}",
                    type="cue",
                    text=masked,
                    style={"duration_s": dur, "max_lines": MAX_LINES, "max_line_chars": MAX_LINE_CHARS},
                    loc={"start": p_start, "end": p_end, "cue": cue_no, "timing": timing},
                    protect=protect,
                    status="pending" if has_translatable_text(masked) else "skip",
                )
            )
        return segs

    def encode(self, seg: Segment, final_text: str, doc: TextDoc) -> str:
        # Blank lines inside a cue would split the cue block and corrupt the file.
        cleaned = re.sub(r"\n{2,}", "\n", final_text.strip("\r\n"))
        return cleaned.replace("\n", doc.newline)

    def unit_count(self, path: Path) -> tuple[int, str]:
        doc = read_text_doc(path)
        return sum(1 for _ in self._iter_cues(doc.text)), "cue"

    def extra_qa(self, source: Path, target: Path) -> tuple[list[str], list[str], list[str]]:
        errors: list[str] = []
        warns: list[str] = []
        notes: list[str] = []
        src_cues = list(self._iter_cues(read_text_doc(source).text))
        tgt_cues = list(self._iter_cues(read_text_doc(target).text))
        if len(src_cues) == len(tgt_cues):
            bad_times = [
                sc[0] for sc, tc in zip(src_cues, tgt_cues) if sc[1] != tc[1]
            ]
            if bad_times:
                errors.append(f"Timestamp cue berubah pada cue: {bad_times[:10]}")
            else:
                notes.append(f"Semua timestamp cue utuh ({len(src_cues)} cue).")
        long_lines, many_lines, fast_cps = [], [], []
        for cue_no, _, dur, _, _, payload_lines in tgt_cues:
            plain_lines = [TAG_STRIP_RE.sub("", ln).strip() for ln in payload_lines]
            if len(plain_lines) > MAX_LINES:
                many_lines.append(cue_no)
            if any(len(ln) > MAX_LINE_CHARS for ln in plain_lines):
                long_lines.append(cue_no)
            total_chars = sum(len(ln) for ln in plain_lines)
            if dur > 0 and (total_chars / dur) > MAX_CPS:
                fast_cps.append(cue_no)
        if many_lines:
            warns.append(f"{len(many_lines)} cue melebihi {MAX_LINES} baris: {many_lines[:10]}")
        if long_lines:
            warns.append(f"{len(long_lines)} cue melebihi {MAX_LINE_CHARS} karakter/baris: {long_lines[:10]}")
        if fast_cps:
            warns.append(f"{len(fast_cps)} cue kecepatan baca > {int(MAX_CPS)} kar/detik: {fast_cps[:10]}")
        return errors, warns, notes

    def qa_text(self, path: Path) -> str:
        segs = self.extract(path)
        return "\n".join(TAG_STRIP_RE.sub("", strip_tokens(s.text)) for s in segs)


class SrtHandler(_SubtitleBase):
    name = "srt"
    extensions = (".srt",)
    time_re = SRT_TIME_RE
    extra_patterns = (ASS_TAG_RE,)
    id_prefix = "srt"


class VttHandler(_SubtitleBase):
    name = "vtt"
    extensions = (".vtt",)
    time_re = VTT_TIME_RE
    extra_patterns = (VTT_TS_TAG_RE,)
    id_prefix = "vtt"
