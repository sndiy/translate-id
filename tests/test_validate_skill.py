"""Tests for scripts/validate_skill.py and thin runtime rule pointers."""

import importlib.util

from helpers import ROOT

SPEC = importlib.util.spec_from_file_location("validate_skill", ROOT / "scripts" / "validate_skill.py")
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MOD)


def test_repo_skill_is_valid():
    assert MOD.main([str(ROOT / "skills")]) == 0


def test_invalid_names_and_folder_mismatch_fail(tmp_path):
    bad = tmp_path / "my-skill"
    bad.mkdir()
    (bad / "SKILL.md").write_text("---\nname: Bad--Name\ndescription: ok\n---\n# Hi\n", encoding="utf-8")
    errs = MOD.validate_skill_dir(bad)
    assert any("lowercase" in e for e in errs)
    assert any("folder name" in e for e in errs)


def test_long_description_and_over_500_lines_fail(tmp_path):
    d = tmp_path / "ok-name"
    d.mkdir()
    long_desc = "a" * 1025
    body = "\n".join(["line"] * 505)
    (d / "SKILL.md").write_text(f"---\nname: ok-name\ndescription: {long_desc}\n---\n{body}\n", encoding="utf-8")
    errs = MOD.validate_skill_dir(d)
    assert any("1024" in e for e in errs)
    assert any("500" in e for e in errs)


def test_broken_relative_link_fails(tmp_path):
    d = tmp_path / "link-test"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: link-test\ndescription: test\n---\nSee [ref](references/missing.md)\n",
        encoding="utf-8",
    )
    errs = MOD.validate_skill_dir(d)
    assert any("broken relative link" in e for e in errs)


def test_agents_md_is_single_source_with_git_rules():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Aturan Git" in agents and "pre-commit install" in agents
    for rel in ("CLAUDE.md", "GEMINI.md", ".cursor/rules/translate-id.mdc", ".github/copilot-instructions.md"):
        p = ROOT / rel
        assert p.is_file(), rel
        content = p.read_text(encoding="utf-8")
        assert "AGENTS.md" in content
        assert len(content.splitlines()) <= 12  # thin pointer only
