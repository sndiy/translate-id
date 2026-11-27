#!/usr/bin/env python3
"""Validate Agent Skills directories against the agentskills.io specification.

Usage:
    python scripts/validate_skill.py [skills_dir_or_skill_path ...]

Checks per skill directory:
  - SKILL.md exists and has valid YAML frontmatter delimited by ``---``
  - ``name``: required, 1-64 chars, lowercase a-z/0-9/single hyphen, matches folder name
  - ``description``: required, 1-1024 chars, non-empty
  - ``compatibility`` (optional): 1-500 chars
  - Only specification-defined top-level keys are used
  - SKILL.md is under 500 lines (progressive disclosure guideline)
  - Relative Markdown links in SKILL.md resolve to existing files
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ALLOWED_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
MAX_NAME_LEN = 64
MAX_DESC_LEN = 1024
MAX_COMPAT_LEN = 500
MAX_LINES = 500


def _parse_frontmatter(raw: str) -> tuple[dict | None, str, str | None]:
    """Return (frontmatter_dict, body, error_message)."""
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "", "SKILL.md must begin with YAML frontmatter delimiter '---'"
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return None, "", "unterminated YAML frontmatter (missing closing '---')"
    fm_text = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1 :])
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(fm_text)
    except ImportError:
        data = _minimal_yaml_load(fm_text)
    except Exception as exc:
        return None, "", f"invalid YAML frontmatter: {exc}"
    if not isinstance(data, dict):
        return None, "", "YAML frontmatter must be a mapping"
    return data, body, None


def _minimal_yaml_load(text: str) -> dict:
    """Fallback parser for simple key: value and folded/literal blocks when PyYAML is absent."""
    result: dict = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip() or ln.lstrip().startswith("#"):
            i += 1
            continue
        if ":" not in ln or ln[0].isspace():
            i += 1
            continue
        k, v = ln.split(":", 1)
        key = k.strip()
        val = v.strip()
        if val in (">", ">-", "|", "|-"):
            block: list[str] = []
            i += 1
            while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            joiner = " " if val.startswith(">") else "\n"
            result[key] = joiner.join(b for b in block if b).strip()
        else:
            result[key] = val.strip("\"'")
            i += 1
    return result


def validate_skill_dir(skill_dir: Path) -> list[str]:
    """Validate one skill folder. Returns a list of error strings (empty = valid)."""
    errors: list[str] = []
    skill_dir = Path(skill_dir)
    if not skill_dir.is_dir():
        return [f"{skill_dir}: not a directory"]
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return [f"{skill_dir}: missing SKILL.md"]

    raw = skill_md.read_text(encoding="utf-8")
    line_count = len(raw.splitlines())
    if line_count > MAX_LINES:
        errors.append(f"{skill_md}: {line_count} lines exceeds limit of {MAX_LINES}")

    fm, body, err = _parse_frontmatter(raw)
    if err:
        return [*errors, f"{skill_md}: {err}"]
    assert fm is not None

    unknown = sorted(set(fm.keys()) - ALLOWED_KEYS)
    if unknown:
        errors.append(f"{skill_md}: unsupported frontmatter key(s): {', '.join(unknown)}")

    name = fm.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append(f"{skill_md}: missing or empty 'name'")
    else:
        if len(name) > MAX_NAME_LEN:
            errors.append(f"{skill_md}: 'name' length {len(name)} > {MAX_NAME_LEN}")
        if not NAME_RE.match(name):
            errors.append(
                f"{skill_md}: 'name' {name!r} must be lowercase alphanumeric with single hyphens"
            )
        if name != skill_dir.name:
            errors.append(f"{skill_md}: 'name' {name!r} does not match folder name {skill_dir.name!r}")

    desc = fm.get("description")
    if not isinstance(desc, str) or not desc.strip():
        errors.append(f"{skill_md}: missing or empty 'description'")
    elif len(desc.strip()) > MAX_DESC_LEN:
        errors.append(f"{skill_md}: 'description' length {len(desc.strip())} > {MAX_DESC_LEN}")

    compat = fm.get("compatibility")
    if compat is not None:
        if not isinstance(compat, str) or not compat.strip():
            errors.append(f"{skill_md}: 'compatibility' must be a non-empty string if present")
        elif len(compat.strip()) > MAX_COMPAT_LEN:
            errors.append(f"{skill_md}: 'compatibility' length {len(compat.strip())} > {MAX_COMPAT_LEN}")

    # Check relative links inside SKILL.md body
    for target in LINK_RE.findall(body):
        href = target.split("#", 1)[0].strip()
        if not href or href.startswith(("http://", "https://", "mailto:")):
            continue
        if not (skill_dir / href).exists():
            errors.append(f"{skill_md}: broken relative link '{target}'")

    return errors


def discover_skill_dirs(paths: list[Path]) -> list[Path]:
    found: list[Path] = []
    for p in paths:
        if (p / "SKILL.md").is_file():
            found.append(p)
        elif p.is_dir():
            for child in sorted(p.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    found.append(child)
        else:
            found.append(p)
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="skill directories or parent skills/ folders (default: skills)")
    args = ap.parse_args(argv)
    roots = [Path(x) for x in args.paths] if args.paths else [Path("skills")]
    skill_dirs = discover_skill_dirs(roots)
    if not skill_dirs:
        print("ERROR: no skill directories found", file=sys.stderr)
        return 1
    all_errors: list[str] = []
    for sd in skill_dirs:
        errs = validate_skill_dir(sd)
        if errs:
            all_errors.extend(errs)
        else:
            print(f"OK: {sd}")
    for e in all_errors:
        print(f"ERROR: {e}", file=sys.stderr)
    return 1 if all_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
