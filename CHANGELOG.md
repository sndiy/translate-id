# Changelog

Semua perubahan penting pada proyek ini dicatat di sini. Format mengikuti
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) dan penomoran versi mengikuti
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Paket Python `id_translate` dan CLI `id-translate` (`init`, `inspect`, `extract`, `batch`,
  `apply`, `compare`, `qa`, `verify`, `glossary-scan`) dengan dukungan `--dry-run` dan exit code terstruktur.
- Invarian keselamatan: pembuatan file eksklusif (`open(..., "xb")`), `MANIFEST.json` + hash SHA-256
  sumber/hasil, penolakan PDF terenkripsi, Office OLE terenkripsi, dan EPUB ber-DRM.
- Kontrak segmen JSONL (`id-translate/segments@1`) dengan masking token pelindung (`⟦P1⟧`) untuk
  placeholder, URL, email, path, tag, dan ICU plural, plus batching berbasis estimasi token dan
  translation memory JSONL.
- Handler format (status `beta`): Markdown, TXT, SRT, WebVTT, JSON, ARB, YAML, PO/POT, Android
  `strings.xml`, DOCX, PPTX, XLSX, HTML, EPUB, serta prototipe PDF di balik abstraksi `PdfEngine`
  (backend opsional PyMuPDF `[pdf]`).
- Skill `skills/translate-id/SKILL.md` sesuai spesifikasi `agentskills.io`, validator
  `scripts/validate_skill.py`, aturan tunggal `AGENTS.md` (termasuk aturan Git), dan penunjuk tipis
  untuk Claude Code, Gemini/Antigravity, Cursor, dan GitHub Copilot.
- Dokumentasi lengkap (`README.md`, `README.en.md`, `docs/`, `docs/claims.md`, demo visual
  `docs/demo/pdf-compare.png`), berkas komunitas, `THIRD_PARTY_NOTICES.md`, workflow CI GitHub
  Actions, dan konfigurasi `pre-commit`.
- Suite evaluasi deterministik (`evals/run_evals.py`, 18 kasus dengan pseudo-translation ~+25%)
  beserta laporan angka nyata di `docs/evals.md`.
- Dokumen persiapan rilis `v0.1.0`: `docs/releases/v0.1.0.md`, `docs/release-checklist.md`, dan
  `docs/known-issues.md`.
