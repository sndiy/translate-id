# PLAN.md — Mengubah terjemahan-id-kit menjadi repo produksi

## Tujuan
Repo open-source siap produksi: panduan, skill, dan rules untuk AI agent (Codex, Claude Code, Cursor,
Antigravity, dan sejenisnya) agar menerjemahkan dokumen ke BAHASA INDONESIA dengan akurat, tata letak
terjaga, dan tanpa menimpa file asli. Berguna dan mudah dipercaya orang lain.

## Aturan kerja (berlaku di semua tugas)
1. Semua konten ORISINAL. Boleh meriset struktur repo agent-skills/rules populer sebagai inspirasi,
   tetapi JANGAN menyalin teks, kode, atau struktur kalimat mereka. Ide yang dipinjam dicatat di
   docs/credits.md dengan atribusi dan lisensinya.
2. Tidak ada klaim palsu: tanpa jumlah bintang, badge CI yang belum ada, benchmark yang belum
   dijalankan, atau fitur yang belum diuji. Setiap klaim di README harus punya bukti (tes, demo nyata,
   atau dokumen) yang dipetakan di docs/claims.md. Status format jujur: stable / beta / planned.
3. Jangan menyimpan file berhak cipta di repo. Fixture buatan sendiri atau berlisensi bebas yang jelas.
   Jangan pernah memasukkan dokumen sumber atau hasil terjemahan karya berhak cipta ke repo.
4. LICENSE: JANGAN dibuat. Tulis rekomendasi awal (MIT) di docs/license-decision.md dan tunggu aku.
5. GIT — AKU YANG MENGERJAKAN, BUKAN KAMU:
   - JANGAN menjalankan perintah git yang mengubah status: init, add, commit, branch, checkout,
     switch, merge, rebase, reset, stash, tag, push, pull, remote, clean, dan sejenisnya.
   - JANGAN membuat repositori git sendiri. Jika folder .git belum ada, biarkan.
   - Kamu BOLEH membuat dan memperbarui file `.gitignore`. Perbarui setiap kali muncul jenis berkas
     baru yang tidak boleh dilacak (hasil build, cache, hasil terjemahan, dan sebagainya).
     `.gitignore` harus tetap memblokir dokumen sumber dan hasil terjemahan, tetapi mengecualikan
     fixture buatan sendiri dan aset demo (mis. `!tests/fixtures/**`, `!docs/demo/**`).
   - Jika repo sudah ada, perintah baca saja yang boleh (`git status`, `git diff`, `git log`),
     dan hanya untuk melihat keadaan, bukan mengubahnya.
   - Di akhir tiap checkpoint, tulis di PROGRESS.md bagian "Saran commit": daftar file yang berubah
     dan SATU saran pesan commit berformat Conventional Commits. Aku yang menjalankan commit.
6. Invarian keselamatan harus selalu terbukti oleh tes: tidak pernah menimpa file sumber/hasil lama,
   sumber diverifikasi lewat hash SHA-256, PDF terenkripsi ditolak, tidak ada penghapusan DRM.
7. Dokumentasi utama berbahasa Indonesia. Kode, identifier, dan komentar teknis berbahasa Inggris.
8. Kualitas sebelum kecepatan: jangan menghapus atau melemahkan tes agar tugas "selesai".

## PROGRESS.md (wajib dirawat)
Baca PROGRESS.md saat memulai atau melanjutkan. Setelah tiap checkpoint tambahkan entri ringkas
(maks ~12 baris): checkpoint, bukti (perintah dan hasilnya), sisa pekerjaan, status blokir,
dan "Saran commit" (file yang berubah + satu pesan Conventional Commit).

## Kondisi PAUSE (berhenti dan tunggu aku)
- Perlu keputusan LICENSE, atau keputusan soal PyMuPDF di luar default di bawah.
- Masalah yang sama gagal 3 kali berturut-turut dengan pendekatan berbeda.
- Tindakan yang butuh izin di luar sandbox, atau yang akan melanggar aturan kerja di atas
  (termasuk aturan git).
- Butuh dokumen berhak cipta sebagai fixture.

## Fase 0 — Audit dan riset
- AUDIT.md: struktur, tes (jalankan), lint, dependensi, kekurangan, risiko, prioritas.
- docs/research.md: ringkasan TEMUAN (bukan teks mereka) dari spesifikasi Agent Skills
  (agentskills.io), konvensi AGENTS.md, dan struktur repo skills/rules populer, beserta URL sumber.
- Inventarisasi lisensi dependensi yang direncanakan. Catat bahwa PyMuPDF berlisensi AGPL-3.0 atau
  lisensi komersial Artifex.
- Usulkan 3 nama repo, deskripsi GitHub "About", dan topics (docs/repo-meta.md).
- Buat atau perbarui .gitignore sesuai aturan kerja nomor 5.

## Fase 1 — Mesin deterministik (prioritas tertinggi)
Masalah: agent menulis ulang kode ekstraksi/penulisan ulang tiap sesi → boros token, tidak konsisten.
Solusi: model HANYA menerjemahkan teks; kode yang mengurus file.
- CLI `id-translate`: `init` (folder hasil aman), `inspect`, `extract`, `apply`, `compare` (PNG
  side-by-side), `qa`, `verify`, `glossary-scan`. (`init` di sini membuat folder hasil terjemahan,
  BUKAN repo git.)
- Kontrak segmen JSONL: `id`, `type`, `text`, `style`, `loc` (halaman/bbox/sel/cue), `protect`
  (token termasking seperti ⟦P1⟧ untuk placeholder/URL/kode lalu dipulihkan), `status`.
- Batching dengan estimasi token, translation memory, resume dari checkpoint, `--dry-run`, exit code
  jelas, logging.
- Format, SATU per satu, tiap format selesai dengan tes sebelum lanjut:
  md/txt → srt/vtt → json/yaml/po/arb/android-xml → docx → pptx → xlsx → html/epub → pdf (TERAKHIR).
- PDF: ekstraksi per blok dengan bbox, redaksi yang TIDAK menghapus gambar/vektor, tulis ulang di bbox
  yang sama dengan font tertanam, auto-fit terbatas (turun maks ~10%), halaman yang tidak muat
  ditandai (jangan potong). Dokumentasikan keterbatasan PDF scan/OCR secara jujur.
- Default PyMuPDF: dependensi OPSIONAL (extra `[pdf]`), tidak di-vendor. Buat lapisan abstraksi agar
  mesin PDF bisa diganti tanpa mengubah kontrak segmen.
- Tes per format: round-trip (extract → apply identitas → hasil setara), invarian keselamatan,
  placeholder, teks lebih panjang.

## Fase 2 — Skill dan rules
- Skill valid menurut agentskills.io: `name` sama dengan nama folder (maks 64 karakter, huruf kecil/
  angka/tanda hubung, tanpa hubung di awal/akhir atau berurutan), `description` 1–1024 karakter dengan
  kata pemicu jelas, SKILL.md di bawah 500 baris, progressive disclosure (detail di references/,
  kode di scripts/).
- Satu sumber kebenaran: AGENTS.md. File runtime lain (CLAUDE.md, .cursor/rules, dll.) hanya
  penunjuk tipis ke AGENTS.md.
- Tambahkan aturan git (nomor 5 di atas) ke AGENTS.md agar berlaku untuk semua agent.
- scripts/validate_skill.py untuk memvalidasi frontmatter dan dijalankan di CI.
- Skill tambahan hanya jika perlu dan fungsinya berbeda.

## Fase 3 — Dokumentasi (orisinal, jujur, mudah dipindai)
- README.md: satu paragraf inti, masalah vs solusi, Quick Start 3 langkah, demo terminal NYATA
  (rekaman run sungguhan), tabel format + status jujur, diagram arsitektur (mermaid), FAQ,
  Keterbatasan, Roadmap. Plus README.en.md singkat.
- docs/: getting-started, architecture, formats/<format>.md, style-guide-id, glossary-howto, qa,
  troubleshooting, security-and-copyright, credits, claims.
- CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, CHANGELOG (Keep a Changelog), template issue dan PR,
  CITATION.cff.

## Fase 4 — Kualitas, CI, kepatuhan lisensi
- pyproject.toml (paket + entry point), Python 3.10–3.13, dependensi seminimal mungkin, type hints.
- Berkas workflow GitHub Actions: ruff, tes multi-versi Python, validasi skill, cek tautan Markdown,
  pemeriksaan lisensi dependensi. pre-commit (berkas konfigurasinya saja; jangan menjalankan
  `pre-commit install` karena itu mengubah .git).
- THIRD_PARTY_NOTICES.md. Tulis di README dan docs/security-and-copyright.md bahwa PyMuPDF berlisensi
  AGPL-3.0 / komersial (Artifex) dan pengguna bertanggung jawab memenuhinya. Jangan menyatakan
  "bebas masalah lisensi".
- Field `license` di SKILL.md dan pyproject.toml diisi SETELAH aku memilih LICENSE.

## Fase 5 — Evaluasi
- evals/ berisi ≥15 kasus (placeholder, tabel, teks panjang, daftar bersarang, subtitle padat, PDF
  dengan kotak berwarna, dan sebagainya) dengan pemeriksaan otomatis.
- Uji tata letak memakai TERJEMAHAN TIRUAN (pseudo-translation: teks diperpanjang ~25% dengan
  karakter pengganti), bukan terjemahan asli. Jangan mengarang klaim kualitas terjemahan.
- docs/evals.md melaporkan angka APA ADANYA dari run nyata (halaman overflow, pelanggaran glosarium,
  angka tidak cocok, waktu). Jangan mengarang angka.

## Fase 6 — Persiapan rilis
- Catatan rilis v0.1.0, checklist rilis, daftar isu yang diketahui. JANGAN membuat tag atau LICENSE.

## Definisi selesai (seluruh proyek)
Tes dan pemeriksaan lokal hijau; invarian keselamatan terbukti oleh tes; skill lolos validator;
semua klaim README terpetakan di docs/claims.md; demo direkam dari run nyata; ada daftar jujur
"belum didukung"; THIRD_PARTY_NOTICES lengkap; .gitignore terawat; PROGRESS.md mencerminkan keadaan
repo; tidak ada perintah git pengubah-status yang pernah dijalankan.