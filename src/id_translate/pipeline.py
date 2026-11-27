"""Extract and apply pipelines shared by the CLI and tests."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from id_translate.errors import InputError, SafetyError, ValidationError
from id_translate.formats import handler_for_path
from id_translate.formats.base import ApplyOptions, FormatHandler, RenderReport
from id_translate.memory import TranslationMemory, normalize_key
from id_translate.protect import check_tokens
from id_translate.safety import ensure_distinct_output, sha256_file, write_new_bytes
from id_translate.segments import Segment, read_meta, read_segments, write_segments

log = logging.getLogger("id_translate")


def prepare_handler(source: Path, fmt: str | None = None) -> FormatHandler:
    source = Path(source)
    if not source.is_file():
        raise InputError(f"file not found: {source}")
    handler = handler_for_path(source, fmt)
    handler.ensure_available()
    handler.check_access(source)
    return handler


def extract_file(source: Path, fmt: str | None = None) -> tuple[FormatHandler, list[Segment], dict]:
    source = Path(source)
    handler = prepare_handler(source, fmt)
    digest = sha256_file(source)
    segments = handler.extract(source)
    if sha256_file(source) != digest:
        raise SafetyError(f"source changed during extraction: {source}")
    meta = {
        "format": handler.name,
        "source_path": str(source.resolve()),
        "source_name": source.name,
        "source_size_bytes": source.stat().st_size,
        "source_sha256": digest,
    }
    return handler, segments, meta


def extract_to(source: Path, out_segments: Path, fmt: str | None = None) -> tuple[list[Segment], dict]:
    _, segments, meta = extract_file(source, fmt)
    write_segments(out_segments, segments, meta)
    return segments, meta


@dataclass
class ApplyResult:
    output: Path | None
    written: bool
    translated: int = 0
    unchanged_source: int = 0
    skipped: int = 0
    propagated: int = 0
    kept_source_ids: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    report: RenderReport = field(default_factory=RenderReport)
    source_sha256: str = ""
    output_sha256: str = ""


def apply_translations(
    source: Path,
    segments_path: Path,
    translations: dict[str, str],
    out: Path,
    *,
    allow_partial: bool = False,
    options: ApplyOptions | None = None,
    dry_run: bool = False,
    tm: TranslationMemory | None = None,
) -> ApplyResult:
    options = options or ApplyOptions()
    source, out = Path(source), Path(out)
    segments = read_segments(segments_path)
    meta = read_meta(segments_path)
    handler = prepare_handler(source, meta.get("format"))
    before = sha256_file(source)
    if before != meta.get("source_sha256"):
        raise SafetyError(
            "source file differs from the one segments were extracted from (SHA-256 mismatch); "
            "re-run extract"
        )
    ensure_distinct_output(source, out)
    if out.suffix.lower() != source.suffix.lower():
        log.warning("output extension %s differs from source %s", out.suffix, source.suffix)

    result = ApplyResult(output=out, written=False, source_sha256=before)
    by_text: dict[str, str] = {}
    for seg in segments:
        tr = translations.get(seg.id)
        if seg.status == "pending" and tr is not None and not check_tokens(seg.text, tr):
            by_text.setdefault(normalize_key(seg.text), tr)

    final: dict[str, str] = {}
    missing: list[str] = []
    for seg in segments:
        if seg.status == "skip":
            result.skipped += 1
            continue
        tr = translations.get(seg.id)
        if tr is None:
            tr = by_text.get(normalize_key(seg.text))
            if tr is not None:
                result.propagated += 1
        if tr is None:
            missing.append(seg.id)
            continue
        problems = check_tokens(seg.text, tr)
        if problems:
            result.problems.append(f"{seg.id}: " + "; ".join(problems))
            continue
        final[seg.id] = tr
        if tr == seg.text:
            result.unchanged_source += 1
        else:
            result.translated += 1

    if missing and not allow_partial:
        shown = ", ".join(missing[:20]) + (" ..." if len(missing) > 20 else "")
        raise ValidationError(f"{len(missing)} segment(s) have no translation: {shown} (use --allow-partial)")
    if result.problems and not allow_partial:
        raise ValidationError("token validation failed:\n  " + "\n  ".join(result.problems[:30]))
    bad_ids = [p.split(":", 1)[0] for p in result.problems]
    result.kept_source_ids = missing + bad_ids

    data, report = handler.render(source, segments, final, options)
    result.report = report
    if sha256_file(source) != before:
        raise SafetyError(f"source changed while rendering: {source}")
    if not dry_run:
        write_new_bytes(out, data)
        result.written = True
        from id_translate.safety import sha256_bytes

        result.output_sha256 = sha256_bytes(data)
        if tm is not None:
            seg_by_id = {s.id: s for s in segments}
            tm.add_many([(seg_by_id[i].text, t) for i, t in final.items() if t != seg_by_id[i].text])
    return result
