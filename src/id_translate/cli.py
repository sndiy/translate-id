"""Command line interface: ``id-translate <command>``.

Commands: init, inspect, extract, batch, apply, compare, qa, verify, glossary-scan.
Run ``id-translate <command> --help`` for details. Exit codes: see id_translate.errors.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from id_translate import __version__
from id_translate.errors import ExitCode, IdTranslateError, InputError, UsageError
from id_translate.safety import (
    make_result_dir,
    read_manifest,
    record_output,
    sha256_file,
    unique_path,
    verify_result_dir,
    write_new_text,
)

log = logging.getLogger("id_translate")


def _setup_logging(verbose: int, quiet: bool, log_file: str | None) -> None:
    level = logging.WARNING if quiet else (logging.DEBUG if verbose else logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", handlers=handlers, force=True)


def _print(obj) -> None:
    text = obj if isinstance(obj, str) else json.dumps(obj, indent=2, ensure_ascii=False)
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    sys.stdout.flush()


# --------------------------------------------------------------------------- commands


def cmd_init(a) -> int:
    from id_translate.formats import handler_for_path

    src = Path(a.source)
    if not src.is_file():
        raise InputError(f"file not found: {src}")
    try:
        handler = handler_for_path(src)
    except IdTranslateError:
        handler = None
    if handler is not None and not handler.missing_dependencies():
        handler.check_access(src)  # refuse encrypted/DRM inputs up front
    d = make_result_dir(src, Path(a.out_root) if a.out_root else None, dry_run=a.dry_run)
    if a.dry_run:
        log.info("dry-run: would create %s", d)
    _print(str(d))
    return ExitCode.OK


def cmd_inspect(a) -> int:
    from id_translate.formats import handler_for_path
    from id_translate.memory import estimate_tokens

    src = Path(a.file)
    if not src.is_file():
        raise InputError(f"file not found: {src}")
    handler = handler_for_path(src, a.format)
    info: dict = {
        "file": str(src),
        "size_bytes": src.stat().st_size,
        "sha256": sha256_file(src),
        "format": handler.name,
        "stability": handler.stability,
        "missing_dependencies": handler.missing_dependencies(),
    }
    if not info["missing_dependencies"]:
        handler.check_access(src)
        info["encrypted"] = False
        info.update(handler.inspect_info(src))
        segs = handler.extract(src)
        pending = [s for s in segs if s.status == "pending"]
        info["segments"] = len(segs)
        info["segments_pending"] = len(pending)
        info["chars_pending"] = sum(len(s.text) for s in pending)
        info["estimated_input_tokens"] = sum(estimate_tokens(s.text) for s in pending)
        uc = handler.unit_count(src)
        if uc:
            info["units"] = {"count": uc[0], "unit": uc[1]}
    _print(info)
    if a.json:
        write_new_text(Path(a.json), json.dumps(info, indent=2, ensure_ascii=False))
    return ExitCode.OK


def cmd_extract(a) -> int:
    from id_translate.memory import estimate_tokens
    from id_translate.pipeline import extract_file
    from id_translate.segments import write_segments

    src = Path(a.source)
    if a.result:
        out = Path(a.result) / "work" / "segments.jsonl"
    elif a.out:
        out = Path(a.out)
    else:
        raise UsageError("give --result <result folder> or --out <segments.jsonl>")
    _, segments, meta = extract_file(src, a.format)
    pending = [s for s in segments if s.status == "pending"]
    summary = {
        "format": meta["format"],
        "segments": len(segments),
        "pending": len(pending),
        "skip": len(segments) - len(pending),
        "chars_pending": sum(len(s.text) for s in pending),
        "estimated_input_tokens": sum(estimate_tokens(s.text) for s in pending),
        "segments_file": str(out),
    }
    if a.dry_run:
        summary["dry_run"] = True
    else:
        write_segments(out, segments, meta)
    _print(summary)
    return ExitCode.OK


def cmd_batch(a) -> int:
    from id_translate.memory import TranslationMemory, plan_batches
    from id_translate.segments import read_segments, read_translations

    seg_path = Path(a.segments)
    work = seg_path.parent
    tr_dir = Path(a.translations) if a.translations else work / "translations"
    tm_path = Path(a.tm) if a.tm else work / "tm.jsonl"
    out_dir = Path(a.out_dir) if a.out_dir else work / "batches"
    segments = read_segments(seg_path)
    done = read_translations(tr_dir) if tr_dir.exists() else {}
    tm = TranslationMemory(tm_path)
    plan = plan_batches(segments, done, tm, a.max_tokens)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_dir = unique_path(out_dir / f"run-{stamp}")
    summary = {
        "pending_total": plan.pending_total,
        "already_translated": plan.already_done,
        "tm_hits": len(plan.tm_hits),
        "duplicates_skipped": plan.duplicates,
        "batches": len(plan.batches),
        "segments_in_batches": sum(len(b) for b in plan.batches),
        "estimated_input_tokens": plan.input_tokens,
        "estimated_output_tokens": plan.output_tokens,
        "batch_dir": str(run_dir),
        "translations_dir": str(tr_dir),
    }
    if a.dry_run:
        summary["dry_run"] = True
        _print(summary)
        return ExitCode.OK
    if plan.tm_hits:
        lines = "".join(json.dumps({"id": i, "text": t}, ensure_ascii=False) + "\n" for i, t in plan.tm_hits.items())
        write_new_text(unique_path(tr_dir / f"tm-{stamp}.jsonl"), lines)
    files = []
    for n, batch in enumerate(plan.batches, 1):
        name = f"batch-{n:04d}.jsonl"
        body = "".join(json.dumps({"id": s.id, "text": s.text}, ensure_ascii=False) + "\n" for s in batch)
        write_new_text(run_dir / name, body)
        files.append({"file": name, "segments": len(batch), "translations_file": str(tr_dir / name)})
    if files:
        index = {**summary, "files": files, "instructions": (
            "Translate each line's text into Indonesian. Keep every token like ⟦P1⟧ exactly once. "
            "Write {\"id\", \"text\"} JSONL lines to the matching translations_file."
        )}
        write_new_text(run_dir / "index.json", json.dumps(index, indent=2, ensure_ascii=False))
    _print(summary)
    return ExitCode.OK


def cmd_apply(a) -> int:
    from id_translate.formats.base import ApplyOptions
    from id_translate.memory import TranslationMemory
    from id_translate.pipeline import apply_translations
    from id_translate.segments import read_translations

    result_dir = Path(a.result) if a.result else None
    if result_dir:
        manifest = read_manifest(result_dir)
        source = Path(a.source) if a.source else Path(manifest["source_path"])
        seg_path = Path(a.segments) if a.segments else result_dir / "work" / "segments.jsonl"
        tr_path = Path(a.translations) if a.translations else result_dir / "work" / "translations"
        out = Path(a.out) if a.out else unique_path(result_dir / "output" / f"{source.stem}_ID{source.suffix}")
        tm_path = Path(a.tm) if a.tm else result_dir / "work" / "tm.jsonl"
    else:
        if not (a.source and a.segments and a.translations and a.out):
            raise UsageError("without --result you must give SOURCE, --segments, --translations and --out")
        source, seg_path, tr_path, out = Path(a.source), Path(a.segments), Path(a.translations), Path(a.out)
        tm_path = Path(a.tm) if a.tm else None
    translations = read_translations(tr_path)
    res = apply_translations(
        source,
        seg_path,
        translations,
        out,
        allow_partial=a.allow_partial,
        options=ApplyOptions(set_lang=not a.keep_lang),
        dry_run=a.dry_run,
        tm=TranslationMemory(tm_path) if tm_path and not a.dry_run else None,
    )
    summary = {
        "output": str(out),
        "written": res.written,
        "dry_run": a.dry_run,
        "translated": res.translated,
        "identical_to_source": res.unchanged_source,
        "propagated_from_duplicates": res.propagated,
        "skipped_non_text": res.skipped,
        "kept_source_ids": res.kept_source_ids,
        "problems": res.problems,
        "review_flags": res.report.flags,
        "notes": res.report.notes,
        "source_sha256_unchanged": True,
    }
    if res.written and result_dir:
        record_output(result_dir, out, {"kind": "apply"})
    report_path = Path(a.report) if a.report else (
        unique_path(result_dir / "reports" / "apply-report.json") if result_dir and not a.dry_run else None
    )
    if report_path:
        write_new_text(report_path, json.dumps(summary, indent=2, ensure_ascii=False))
        summary["report"] = str(report_path)
    _print(summary)
    return ExitCode.OK


def cmd_compare(a) -> int:
    from id_translate.compare import compare_files

    pages = [int(p) for p in a.pages.split(",")] if a.pages else [1]
    outs = compare_files(Path(a.source), Path(a.translated), Path(a.out), pages=pages, zoom=a.zoom)
    _print({"images": [str(p) for p in outs]})
    return ExitCode.OK


def cmd_qa(a) -> int:
    from id_translate.qa import run_qa

    src, tgt = Path(a.source), Path(a.target)
    for p in (src, tgt):
        if not p.is_file():
            raise InputError(f"file not found: {p}")
    if src.resolve() == tgt.resolve():
        raise UsageError("source and target are the same file")
    res = run_qa(src, tgt, Path(a.glossary) if a.glossary else None, a.format)
    md = res.to_markdown(src, tgt)
    _print(md)
    if a.report:
        rp = unique_path(Path(a.report))
        write_new_text(rp, md)
        log.info("report saved: %s", rp)
    if res.errors or (a.strict and res.warnings):
        return ExitCode.FAILED
    return ExitCode.OK


def cmd_verify(a) -> int:
    ok, messages = verify_result_dir(Path(a.result))
    _print("\n".join(messages))
    return ExitCode.OK if ok else ExitCode.FAILED


def cmd_glossary_scan(a) -> int:
    from id_translate.glossary import Glossary, check_pairs, count_term, parse_glossary, scan_candidates
    from id_translate.protect import restore, strip_tokens
    from id_translate.segments import read_segments, read_translations

    inp = Path(a.input)
    if inp.suffix == ".jsonl":
        segments = read_segments(inp)
    else:
        from id_translate.pipeline import extract_file

        _, segments, _ = extract_file(inp, a.format)
    texts = {s.id: strip_tokens(restore(s.text, s.protect)) for s in segments if s.status == "pending"}
    g = parse_glossary(Path(a.glossary)) if a.glossary else Glossary()
    known = {en.lower() for en, _ in g.pairs} | {x.lower() for x in g.excluded}
    cands = [(t, c) for t, c in scan_candidates(texts.values(), a.top, a.min_count) if t.lower() not in known]
    lines = ["# Pindai glosarium", "", f"- Masukan: `{inp}`", f"- Segmen: {len(texts)}", ""]
    if g.pairs:
        joined = "\n".join(texts.values())
        lines += ["## Istilah glosarium di sumber", "", "| EN | ID | kemunculan |", "|---|---|---|"]
        lines += [f"| {en} | {idn} | {count_term(en, joined)} |" for en, idn in g.pairs]
        lines.append("")
    lines += ["## Kandidat istilah (belum ada di glosarium)", "", "| Istilah | Kemunculan |", "|---|---|"]
    lines += [f"| {t} | {c} |" for t, c in cands] or ["| (tidak ada) | |"]
    issues: list[str] = []
    if a.translations:
        tr = read_translations(Path(a.translations))
        seg_by_id = {s.id: s for s in segments}
        items = [
            (i, texts[i], strip_tokens(restore(t, seg_by_id[i].protect))) for i, t in tr.items() if i in texts
        ]
        issues = check_pairs(g, items)
        lines += ["", "## Kepatuhan glosarium pada terjemahan", ""]
        lines += [f"- {x}" for x in issues] or ["- (tidak ada masalah)"]
    md = "\n".join(lines) + "\n"
    _print(md)
    if a.out:
        write_new_text(unique_path(Path(a.out)), md)
    return ExitCode.FAILED if any(x.startswith("ERROR") for x in issues) else ExitCode.OK


# --------------------------------------------------------------------------- parser


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):  # usage errors -> exit 2 with a short message
        self.print_usage(sys.stderr)
        self.exit(ExitCode.USAGE, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-v", "--verbose", action="count", default=0, help="debug logging")
    common.add_argument("-q", "--quiet", action="store_true", help="warnings and errors only")
    common.add_argument("--log-file", help="also append logs to this file")

    p = _Parser(prog="id-translate", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                parents=[common])
    p.add_argument("--version", action="version", version=f"id-translate {__version__}")
    sub = p.add_subparsers(dest="command", required=True, parser_class=_Parser)

    s = sub.add_parser("init", parents=[common], help="create a safe result folder (NOT a git repo)")
    s.add_argument("source")
    s.add_argument("--out-root", help="parent folder (default: hasil-terjemahan/ next to the source)")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("inspect", parents=[common], help="inspect a file (format, encryption, size, segments)")
    s.add_argument("file")
    s.add_argument("--format", help="force a format handler")
    s.add_argument("--json", help="also write the report to this NEW file")
    s.set_defaults(func=cmd_inspect)

    s = sub.add_parser("extract", parents=[common], help="extract segments to JSONL")
    s.add_argument("source")
    s.add_argument("--result", help="result folder from init (writes work/segments.jsonl)")
    s.add_argument("--out", help="explicit segments.jsonl path")
    s.add_argument("--format")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_extract)

    s = sub.add_parser("batch", parents=[common], help="plan token-budgeted batches of pending segments (resumable)")
    s.add_argument("segments")
    s.add_argument("--translations", help="existing translations dir (default: <work>/translations)")
    s.add_argument("--tm", help="translation memory JSONL (default: <work>/tm.jsonl)")
    s.add_argument("--out-dir", help="batch output dir (default: <work>/batches)")
    s.add_argument("--max-tokens", type=int, default=1500, help="estimated input tokens per batch")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_batch)

    s = sub.add_parser("apply", parents=[common], help="write a NEW translated file")
    s.add_argument("source", nargs="?")
    s.add_argument("--result", help="result folder from init (derives all paths)")
    s.add_argument("--segments")
    s.add_argument("--translations", help="translations JSONL file or directory")
    s.add_argument("--out", help="output path (must not exist)")
    s.add_argument("--tm", help="append applied pairs to this translation memory JSONL")
    s.add_argument("--report", help="write the apply report JSON to this NEW file")
    s.add_argument("--allow-partial", action="store_true", help="keep source text for missing/invalid segments")
    s.add_argument("--keep-lang", action="store_true", help="do not set the document language to id")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_apply)

    s = sub.add_parser("compare", parents=[common], help="render a side-by-side PNG (source | translation)")
    s.add_argument("source")
    s.add_argument("translated")
    s.add_argument("--out", required=True, help="PNG path (multiple pages get -p<N> suffixes)")
    s.add_argument("--pages", help="comma-separated 1-based pages (PDF), default 1")
    s.add_argument("--zoom", type=float, default=1.5)
    s.set_defaults(func=cmd_compare)

    s = sub.add_parser("qa", parents=[common], help="automated QA between source and translated file")
    s.add_argument("source")
    s.add_argument("target")
    s.add_argument("--glossary")
    s.add_argument("--report", help="Markdown report path (never overwritten; -N suffix added)")
    s.add_argument("--format")
    s.add_argument("--strict", action="store_true", help="warnings also fail (exit 1)")
    s.set_defaults(func=cmd_qa)

    s = sub.add_parser("verify", parents=[common], help="verify source and recorded outputs are unchanged")
    s.add_argument("result")
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser("glossary-scan", parents=[common], help="find term candidates and glossary violations")
    s.add_argument("input", help="source file or segments.jsonl")
    s.add_argument("--glossary")
    s.add_argument("--translations")
    s.add_argument("--top", type=int, default=40)
    s.add_argument("--min-count", type=int, default=2)
    s.add_argument("--format")
    s.add_argument("--out")
    s.set_defaults(func=cmd_glossary_scan)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    a = parser.parse_args(argv)
    _setup_logging(a.verbose, a.quiet, a.log_file)
    try:
        return int(a.func(a))
    except IdTranslateError as exc:
        log.error("%s", exc)
        return int(exc.exit_code)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
