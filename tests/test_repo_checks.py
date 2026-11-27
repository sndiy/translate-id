"""Tests for repo-level Phase 4 checks: Markdown links, license notices, and CI/config YAML."""

import importlib.util

import yaml
from helpers import ROOT


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_markdown_links_check_passes_on_repo():
    mod = _load("scripts/check_markdown_links.py", "check_markdown_links")
    assert mod.main([]) == 0


def test_markdown_links_detects_broken_link(tmp_path):
    mod = _load("scripts/check_markdown_links.py", "check_markdown_links")
    md = tmp_path / "doc.md"
    md.write_text("See [broken](does-not-exist.md) and `[ignored](nope.md)`.\n", encoding="utf-8")
    errs = mod.check_file(md, tmp_path)
    assert len(errs) == 1 and "does-not-exist.md" in errs[0]


def test_license_notices_check_passes_on_repo():
    mod = _load("scripts/check_licenses.py", "check_licenses")
    assert mod.check_repo(ROOT) == []


def test_ci_precommit_and_citation_yaml_are_valid():
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    assert "jobs" in ci and {"lint-and-checks", "test", "test-pdf-optional"} <= set(ci["jobs"])
    matrix = ci["jobs"]["test"]["strategy"]["matrix"]["python-version"]
    assert matrix == ["3.10", "3.11", "3.12", "3.13"]

    pc = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    assert "repos" in pc and len(pc["repos"]) >= 2

    cff = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    assert cff["cff-version"] == "1.2.0" and cff["title"]
