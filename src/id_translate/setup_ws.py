"""Bootstrap a standalone translation workspace without cloning the repository.

Copies ``AGENTS.md``, thin runtime pointers (``CLAUDE.md``, ``GEMINI.md``,
``.cursor/rules/translate-id.mdc``, ``.github/copilot-instructions.md``), and
``skills/translate-id/`` from bundled package data into a target directory.
Never overwrites existing files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from id_translate.safety import write_new_bytes

# (package-relative path inside kit_data, workspace-relative destination path)
KIT_FILES: tuple[tuple[str, str], ...] = (
    ("AGENTS.md", "AGENTS.md"),
    ("CLAUDE.md", "CLAUDE.md"),
    ("GEMINI.md", "GEMINI.md"),
    ("dot_cursor/rules/translate-id.mdc", ".cursor/rules/translate-id.mdc"),
    ("dot_github/copilot-instructions.md", ".github/copilot-instructions.md"),
    ("skills/translate-id/SKILL.md", "skills/translate-id/SKILL.md"),
    ("skills/translate-id/assets/glossary-template.md", "skills/translate-id/assets/glossary-template.md"),
    ("skills/translate-id/references/layout-by-format.md", "skills/translate-id/references/layout-by-format.md"),
    ("skills/translate-id/references/qa-checklist.md", "skills/translate-id/references/qa-checklist.md"),
    ("skills/translate-id/references/style-guide-id.md", "skills/translate-id/references/style-guide-id.md"),
)


@dataclass
class SetupResult:
    target_dir: Path
    created: list[str] = field(default_factory=list)
    skipped_existing: list[str] = field(default_factory=list)
    dry_run: bool = False


def setup_workspace(target_dir: Path, *, dry_run: bool = False) -> SetupResult:
    """Populate ``target_dir`` with AGENTS.md, runtime pointers, and skills/translate-id/."""
    dest_root = Path(target_dir).resolve()
    res = SetupResult(target_dir=dest_root, dry_run=dry_run)
    kit_root = resources.files("id_translate").joinpath("kit_data")

    if not dry_run:
        dest_root.mkdir(parents=True, exist_ok=True)
        (dest_root / "dokumen").mkdir(exist_ok=True)

    for src_rel, dst_rel in KIT_FILES:
        dst = dest_root / dst_rel
        if dst.exists():
            res.skipped_existing.append(dst_rel)
            continue
        if dry_run:
            res.created.append(dst_rel)
            continue
        data = kit_root.joinpath(*src_rel.split("/")).read_bytes()
        write_new_bytes(dst, data)
        res.created.append(dst_rel)
    return res
