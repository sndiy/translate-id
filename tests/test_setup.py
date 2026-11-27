"""Tests for ``id-translate setup`` standalone workspace bootstrap."""

import json

from helpers import ROOT, cli

from id_translate.setup_ws import KIT_FILES


def test_setup_creates_standalone_workspace_without_overwriting(tmp_path):
    ws = tmp_path / "proyek-terjemahan"
    r = cli("setup", ws)
    assert r.returncode == 0, r.stderr
    info = json.loads(r.stdout)
    assert len(info["created"]) == len(KIT_FILES)
    assert info["skipped_existing"] == []
    assert (ws / "dokumen").is_dir()
    assert (ws / "AGENTS.md").is_file()
    assert (ws / "CLAUDE.md").is_file()
    assert (ws / "GEMINI.md").is_file()
    assert (ws / ".cursor/rules/translate-id.mdc").is_file()
    assert (ws / ".github/copilot-instructions.md").is_file()
    assert (ws / "skills/translate-id/SKILL.md").is_file()

    # Modify one file and run setup again -> must NEVER overwrite!
    (ws / "AGENTS.md").write_text("# custom user rule\n", encoding="utf-8")
    r2 = cli("setup", ws)
    assert r2.returncode == 0, r2.stderr
    info2 = json.loads(r2.stdout)
    assert info2["created"] == []
    assert len(info2["skipped_existing"]) == len(KIT_FILES)
    assert (ws / "AGENTS.md").read_text(encoding="utf-8") == "# custom user rule\n"


def test_setup_dry_run_creates_nothing(tmp_path):
    ws = tmp_path / "dry-ws"
    r = cli("setup", ws, "--dry-run")
    assert r.returncode == 0, r.stderr
    info = json.loads(r.stdout)
    assert info["dry_run"] is True and len(info["created"]) == len(KIT_FILES)
    assert not ws.exists()


def test_bundled_kit_data_matches_repo_sources():
    kit = ROOT / "src/id_translate/kit_data"
    for src_rel, dst_rel in KIT_FILES:
        bundled = kit / src_rel
        canonical = ROOT / dst_rel
        assert bundled.is_file(), bundled
        assert bundled.read_bytes() == canonical.read_bytes(), f"drift between {bundled} and {canonical}"
