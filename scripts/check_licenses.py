#!/usr/bin/env python3
"""Check dependency license hygiene and THIRD_PARTY_NOTICES.md completeness.

Verifies:
  1. Core ``dependencies`` in pyproject.toml has no copyleft/PyMuPDF requirement.
  2. ``pymupdf`` only appears in optional extras (``[pdf]`` / ``[all]``), never vendored.
  3. Every optional/dev dependency declared in pyproject.toml is documented in THIRD_PARTY_NOTICES.md.
  4. THIRD_PARTY_NOTICES.md, README.md, and docs/security-and-copyright.md clearly state the
     PyMuPDF AGPL-3.0 / Artifex commercial license notice.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore


def _pkg_name(spec: str) -> str:
    return re.split(r"[<>=!~;\[\s]", spec.strip(), maxsplit=1)[0].lower()


def _parse_pyproject(path: Path) -> tuple[list[str], dict[str, list[str]]]:
    raw = path.read_text(encoding="utf-8")
    if tomllib is not None:
        data = tomllib.loads(raw)
        proj = data.get("project", {})
        return list(proj.get("dependencies", [])), dict(proj.get("optional-dependencies", {}))
    # Minimal fallback for Python 3.10 without tomli
    deps: list[str] = []
    extras: dict[str, list[str]] = {}
    section = ""
    for line in raw.splitlines():
        s = line.strip()
        if s.startswith("["):
            section = s
            continue
        if section == "[project]" and s.startswith("dependencies"):
            deps = re.findall(r'"([^"]+)"', s)
        elif section == "[project.optional-dependencies]" and "=" in s and not s.startswith("#"):
            k, v = s.split("=", 1)
            extras[k.strip()] = re.findall(r'"([^"]+)"', v)
    return deps, extras


def check_repo(repo_root: Path) -> list[str]:
    errors: list[str] = []
    pp = repo_root / "pyproject.toml"
    notices = repo_root / "THIRD_PARTY_NOTICES.md"
    if not pp.is_file():
        return ["missing pyproject.toml"]
    if not notices.is_file():
        return ["missing THIRD_PARTY_NOTICES.md"]

    deps, extras = _parse_pyproject(pp)
    core_pkgs = {_pkg_name(d) for d in deps}
    if "pymupdf" in core_pkgs or "fitz" in core_pkgs:
        errors.append("pymupdf must remain an optional extra, never a core dependency")

    all_opt_pkgs = {_pkg_name(spec) for specs in extras.values() for spec in specs if spec.strip()}
    notices_text = notices.read_text(encoding="utf-8").lower()
    for pkg in sorted(all_opt_pkgs):
        if pkg and pkg not in notices_text:
            errors.append(f"dependency '{pkg}' from pyproject.toml is missing in THIRD_PARTY_NOTICES.md")

    for rel in ("THIRD_PARTY_NOTICES.md", "README.md", "docs/security-and-copyright.md"):
        p = repo_root / rel
        if not p.is_file():
            errors.append(f"missing {rel}")
            continue
        txt = p.read_text(encoding="utf-8")
        if "AGPL-3.0" not in txt or "Artifex" not in txt:
            errors.append(f"{rel} must state PyMuPDF AGPL-3.0 and Artifex commercial license notice")
        if "bebas masalah lisensi" in txt.lower():
            errors.append(f"{rel} must not claim 'bebas masalah lisensi'")

    # Ensure PyMuPDF is not vendored in src/
    for hit in (repo_root / "src").rglob("*fitz*"):
        errors.append(f"unexpected vendored fitz file: {hit}")
    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    errors = check_repo(repo_root)
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print("OK: dependency license inventory and PyMuPDF notices verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
