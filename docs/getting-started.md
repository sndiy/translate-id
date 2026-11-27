# Panduan Mulai (Getting Started)

## 1. Prasyarat
- Python 3.10 atau lebih baru.
- Dependensi inti CLI: **tidak ada** (hanya pustaka standar Python untuk MD/TXT, SRT/VTT, JSON/ARB,
  PO/POT, Android XML, HTML, EPUB).

## 2. Instalasi

```bash
# Inti saja
pip install -e .

# Tambah dukungan format sesuai kebutuhan
pip install -e ".[office]"   # DOCX, PPTX, XLSX (lxml)
pip install -e ".[yaml]"     # YAML (PyYAML)
pip install -e ".[compare]"  # Gambar perbandingan PNG (Pillow)
pip install -e ".[pdf]"      # PDF (PyMuPDF — AGPL-3.0 / komersial Artifex)
```

> **Catatan Python 3.15+ dan PyMuPDF 2.2:** wheel PyMuPDF 2.2 meminta `onnxruntime` yang belum
> tersedia di Python 3.15. Jika instalasi `[pdf]` gagal karena `onnxruntime`, pasang wheel PyMuPDF
> dengan `pip install --no-deps pymupdf` lalu pasang extra lain seperti biasa.

## 3. Menyiapkan folder kerja agent (tanpa perlu `git clone`)

Jalankan satu perintah untuk menyiapkan folder kerja terjemahan yang terisolasi di mana saja:

```bash
id-translate setup ./terjemahan-saya
```

Perintah ini menyalin [AGENTS.md](../AGENTS.md), penunjuk tipis runtime berikut, folder
`skills/translate-id/`, dan folder kosong `dokumen/` — tanpa pernah menimpa file yang sudah ada:

| Agent | Berkas |
|---|---|
| Codex / umum | `AGENTS.md` |
| Claude Code | `CLAUDE.md` (memakai `@AGENTS.md`) |
| Antigravity / Gemini | `GEMINI.md` dan `AGENTS.md` |
| Cursor | `.cursor/rules/translate-id.mdc` |
| GitHub Copilot | `.github/copilot-instructions.md` |

Buka `./terjemahan-saya` di AI agent Anda, taruh dokumen di `dokumen/`, lalu minta agent menerjemahkan.
Skill utama ada di `skills/translate-id/` ([SKILL.md](../skills/translate-id/SKILL.md)).

## 4. Alur kerja 5 tahap

1. **Inisialisasi & ekstraksi:** `id-translate init <file>`, `id-translate inspect <file>`,
   `id-translate extract <file> --result <folder>`.
2. **Glosarium:** `id-translate glossary-scan <folder>/work/segments.jsonl` → lengkapi
   `<folder>/glossary.md` → minta persetujuan pengguna.
3. **Pilot:** terjemahkan ±10 segmen/halaman ke `<folder>/work/translations/pilot.jsonl`, jalankan
   `id-translate apply --result <folder> --allow-partial` dan `id-translate compare` → minta
   persetujuan pengguna.
4. **Terjemahan penuh:** `id-translate batch <folder>/work/segments.jsonl`, terjemahkan per batch
   (bisa dilanjutkan kapan saja), lalu `id-translate apply --result <folder>`.
5. **QA & verifikasi:** `id-translate qa`, tinjau visual + sampel terjemah-balik, lalu
   `id-translate verify <folder>`.
