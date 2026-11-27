#!/usr/bin/env python3
"""Check that all local Markdown links and image paths resolve to existing files.

Usage:
    python scripts/check_markdown_links.py [paths ...]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"(`+)[^`]*?\1")
MD_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\)")
SKIP_DIRS = {".git", ".venv", "venv", "hasil-terjemahan", "__pycache__", "build", "dist", ".pytest_cache", "fixtures"}


def _strip_code(text: str) -> list[tuple[int, str]]:
    """Yield (1-based line_no, line_without_inline_code) outside fenced code blocks."""
    out: list[tuple[int, str]] = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    for lineno, line in enumerate(text.splitlines(), 1):
        m = FENCE_RE.match(line)
        if m:
            tok = m.group(1)
            if not in_fence:
                in_fence, fence_char, fence_len = True, tok[0], len(tok)
                continue
            if tok[0] == fence_char and len(tok) >= fence_len:
                in_fence = False
                continue
        if in_fence:
            continue
        out.append((lineno, INLINE_CODE_RE.sub("", line)))
    return out


def check_file(md_path: Path, repo_root: Path) -> list[str]:
    errors: list[str] = []
    text = md_path.read_text(encoding="utf-8")
    for lineno, line in _strip_code(text):
        for target in MD_LINK_RE.findall(line):
            raw = target.strip("<>")
            if not raw or raw.startswith(("#", "http://", "https://", "mailto:", "tel:")):
                continue
            rel = unquote(raw.split("#", 1)[0].split("?", 1)[0])
            if not rel:
                continue
            resolved = (repo_root / rel.lstrip("/")) if rel.startswith("/") else (md_path.parent / rel)
            if not resolved.exists():
                errors.append(f"{md_path.relative_to(repo_root)}:{lineno}: broken link '{raw}'")
    return errors


def discover_md_files(roots: list[Path], repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for r in roots:
        if r.is_file() and r.suffix.lower() == ".md":
            files.append(r)
        elif r.is_dir():
            for p in sorted(r.rglob("*.md")):
                if any(part in SKIP_DIRS for part in p.relative_to(repo_root).parts):
                    continue
                files.append(p)
    return sorted(set(files))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*", help="files or directories to scan (default: repo root)")
    args = ap.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    roots = [Path(p).resolve() for p in args.paths] if args.paths else [repo_root]
    md_files = discover_md_files(roots, repo_root)
    errors: list[str] = []
    for f in md_files:
        errors.extend(check_file(f, repo_root))
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"OK: checked {len(md_files)} Markdown file(s), 0 broken local links.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
