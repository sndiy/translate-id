# terjemahan-id (`id-translate`) — English Summary

> Primary documentation is in Indonesian: [README.md](README.md)

`terjemahan-id` provides an `agentskills.io`-compliant skill (`skills/translate-id/`), a single-source
agent ruleset (`AGENTS.md`), and a deterministic Python CLI (`id-translate`) so AI coding agents
(Codex, Claude Code, Cursor, Antigravity, GitHub Copilot) translate documents into **Indonesian**
accurately, with layout preserved and **without ever overwriting source or previous output files**.

## Core Idea

Instead of having an AI agent rewrite fragile file-parsing scripts every session, the model only
translates masked text segments (`work/segments.jsonl`), while `id-translate` handles:

- Safe output directories (`hasil-terjemahan/<name>_ID_<timestamp>/`) with exclusive-create writes
  and SHA-256 source/output verification (`init`, `verify`).
- Refusing encrypted/DRM inputs (PDF, OLE-encrypted Office files, DRM EPUB) with exit code `4`.
- Placeholder, URL, email, path, tag, and ICU plural masking (`⟦P1⟧`) with validation before write.
- Resumable token-budgeted batching and append-only translation memory (`batch`).
- Format-aware extraction and re-application (`extract`, `apply`) for Markdown, TXT, SRT, VTT,
  JSON, ARB, YAML, PO/POT, Android `strings.xml`, DOCX, PPTX, XLSX, HTML, EPUB, and a beta PDF
  prototype (`[pdf]` extra).
- Heuristic QA (`qa`), glossary scanning (`glossary-scan`), and side-by-side PNG comparison (`compare`).

## Quick Start

```bash
pip install -e .
# Optional extras: pip install -e ".[office,yaml,compare]"  (and ".[pdf]" for PDF)

id-translate init document.md
id-translate extract document.md --result hasil-terjemahan/document_ID_<timestamp>
# Have the agent translate work/segments.jsonl -> work/translations/*.jsonl
id-translate apply --result hasil-terjemahan/document_ID_<timestamp>
id-translate qa document.md hasil-terjemahan/document_ID_<timestamp>/output/document_ID.md
id-translate verify hasil-terjemahan/document_ID_<timestamp>
```

## License & PyMuPDF Notice

- Repository license: **MIT** (see [LICENSE](LICENSE)).
- The default PDF backend uses **PyMuPDF** as an **optional** extra (`[pdf]`), never vendored.
  PyMuPDF is dual-licensed under **GNU AGPL-3.0** or an **Artifex commercial license**; users
  installing or distributing `[pdf]` are responsible for compliance. See
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and
  [docs/security-and-copyright.md](docs/security-and-copyright.md).
