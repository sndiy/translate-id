# Riset (Fase 0): spesifikasi dan konvensi yang relevan

Dokumen ini berisi **ringkasan temuan dengan kata-kata sendiri**, bukan salinan teks sumber.
Diriset 26 November 2026 lewat pencarian web; periksa ulang URL bila spesifikasi berubah.

## 1. Agent Skills (agentskills.io)

Sumber: https://agentskills.io/specification, https://github.com/agentskills/agentskills

- Satu skill = satu folder berisi `SKILL.md` wajib; folder opsional `scripts/` (kode yang dijalankan),
  `references/` (dokumen yang dibaca bila perlu), `assets/` (templat, data).
- Frontmatter YAML wajib `name` dan `description`.
  - `name`: maks 64 karakter, huruf kecil a–z, angka, tanda hubung; tidak diawali/diakhiri tanda
    hubung; tidak ada tanda hubung ganda; **harus sama dengan nama folder**.
  - `description`: 1–1024 karakter; menjelaskan apa yang dilakukan dan kapan dipakai (inilah yang
    dibaca agent untuk memutuskan aktivasi, jadi kata pemicu penting).
  - Opsional: `license`, `compatibility` (maks 500 karakter, kebutuhan lingkungan),
    `metadata` (peta kunci-nilai bebas), `allowed-tools` (eksperimental).
- Progressive disclosure tiga tahap: (1) saat mulai hanya metadata dimuat; (2) badan `SKILL.md`
  dimuat saat skill aktif; (3) berkas di `scripts/`, `references/`, `assets/` dimuat/dijalankan
  hanya bila diperlukan. Saran: `SKILL.md` di bawah ~500 baris; detail dipindah ke `references/`.
- Ada pustaka rujukan `skills-ref` dengan perintah validasi (`skills-ref validate <folder>`).

Implikasi untuk repo ini: skill `translate-id` sudah memenuhi aturan nama; validator sendiri
(`scripts/validate_skill.py`, Fase 2) mengecek aturan di atas tanpa bergantung pada `skills-ref`.
Skill sebaiknya memanggil CLI deterministik (`scripts/` atau paket), bukan berisi kode panjang.

## 2. Konvensi AGENTS.md

Sumber: https://agents.md, https://www.linuxfoundation.org/ (pengumuman Agentic AI Foundation)

- Markdown biasa tanpa skema atau kolom wajib; ibarat "README untuk agent": perintah setup, tes,
  lint, konvensi kode, larangan.
- Mendukung file bersarang: agent memakai `AGENTS.md` terdekat dari berkas yang sedang dikerjakan;
  instruksi eksplisit pengguna tetap diutamakan.
- Dikelola secara netral di bawah Agentic AI Foundation (Linux Foundation) dan dibaca banyak alat
  (Codex, Cursor, Copilot, Jules, Aider, dll.).
- Praktik baik yang sering disebut: perintah lebih dulu dari prosa, ringkas, larangan yang jelas,
  selalu diperbarui.

## 3. File runtime per agent (untuk "penunjuk tipis" di Fase 2)

| Agent | Lokasi instruksi | Catatan temuan | Sumber |
|---|---|---|---|
| Claude Code | `CLAUDE.md` | mendukung impor `@path` (mis. `@AGENTS.md`); dilaporkan juga membaca `AGENTS.md` bila tidak ada `CLAUDE.md` (perlu dicek per versi) | https://docs.claude.com/en/docs/claude-code/memory |
| Cursor | `.cursor/rules/*.mdc` | frontmatter `description`, `globs`, `alwaysApply`; `.md` biasa di folder itu diabaikan; `AGENTS.md` di akar juga dibaca | https://cursor.com/docs/context/rules |
| GitHub Copilot | `.github/copilot-instructions.md`, juga `AGENTS.md` | instruksi repo | https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot |
| Antigravity | `AGENTS.md`, `GEMINI.md`, `.agents/rules/*.md`, `.agents/skills/<nama>/SKILL.md` | penemuan hierarkis dari direktori kerja ke akar repo; skill dimuat progresif | panduan kustomisasi bawaan Antigravity |
| Codex (OpenAI) | `AGENTS.md` | file bersarang didukung | https://agents.md |

## 4. Struktur repo skills/rules populer (inspirasi struktur saja)

| Repo | Pola yang diamati | Lisensi (sebagaimana dilaporkan) |
|---|---|---|
| https://github.com/anthropics/skills | `skills/<nama>/SKILL.md` + `scripts/` + `references/`; folder `template/` dan `spec/` | Apache-2.0 untuk sebagian besar; skill dokumen (docx/pdf/pptx/xlsx) **source-available, bukan open source** → jangan dirujuk kodenya sama sekali |
| https://github.com/github/awesome-copilot | koleksi instructions, prompts, chat modes per berkas | MIT |
| https://github.com/PatrickJS/awesome-cursorrules | kumpulan aturan per framework dalam folder | lihat repo |
| https://github.com/openai/codex | contoh nyata AGENTS.md di repo besar | Apache-2.0 |

Pola umum yang layak ditiru **sebagai ide** (tanpa menyalin teks/kode): satu folder per skill,
`SKILL.md` pendek yang menunjuk ke `references/`, skrip siap pakai agar agent tidak menulis ulang
kode, berkas instruksi per-agent yang tipis.

## 5. Ide dari alat lokalisasi (konsep, bukan kode)

- XLIFF (standar OASIS, https://docs.oasis-open.org/xliff/xliff-core/v2.1/xliff-core-v2.1.html):
  unit terjemahan + kode inline yang dilindungi → ide kontrak segmen dan token `⟦P1⟧`.
- Gettext PO (https://www.gnu.org/software/gettext/manual/): bahasa Indonesia memakai
  `nplurals=1; plural=0;`.
- CLDR plural rules (https://cldr.unicode.org/index/cldr-spec/plural-rules): Indonesia hanya
  kategori `other`.
- Android resource strings (https://developer.android.com/guide/topics/resources/string-resource):
  escape `\'`, `\"`, `\@`, `\?`; folder `values-in` untuk Indonesia (kode lama "in").

## 6. PyMuPDF dan lisensi

- PyMuPDF berlisensi ganda: **GNU AGPL-3.0** atau **lisensi komersial Artifex**
  (https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright,
  https://artifex.com/licensing). Kewajiban AGPL antara lain berlaku saat mendistribusikan atau
  menyediakan perangkat lunak lewat jaringan; ini bukan nasihat hukum — pengguna bertanggung jawab
  menilai kepatuhannya sendiri.
- Fitur yang relevan (dicek pada versi 2.2 terpasang): `page.get_text("dict")` (blok/baris/span
  dengan bbox, font, ukuran, warna), redaksi dengan `images=PDF_REDACT_IMAGE_NONE` dan
  `graphics=PDF_REDACT_LINE_ART_NONE`, `insert_htmlbox` (menyematkan font yang dipakai).
- Keputusan default (PLAN): extra opsional `[pdf]`, tidak di-vendor, di balik antarmuka mesin PDF.
