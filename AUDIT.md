# AUDIT.md — Kondisi awal repo (Fase 0)

Tanggal audit: 26 November 2026. Lingkungan: Windows, Python 3.15.2 (satu-satunya interpreter
terpasang, `py -0p`), virtualenv lokal `.venv/` (diabaikan git).

## 1. Struktur saat audit

```
terjemahan-id/
├── .git/                 (repo sudah ada: branch main, belum ada commit; tidak disentuh)
├── .gitignore
├── AGENTS.md             aturan terjemahan untuk agent (bahasa Indonesia)
├── PLAN.md               rencana produksi (Fase 0–6)
├── README.md
├── requirements.txt      pymupdf>=1.24, python-docx, python-pptx, openpyxl, beautifulsoup4, lxml (tanpa pin)
├── skills/translate-id/
│   ├── SKILL.md          81 baris, frontmatter name+description
│   ├── assets/glossary-template.md
│   ├── references/{layout-by-format,qa-checklist,style-guide-id}.md
│   └── scripts/{safe_output,inventory,qa_check}.py
└── tests/test_scripts.py (unittest, 5 tes)
```

Tidak ada: paket Python/`pyproject.toml`, CLI, kode ekstraksi/penulisan ulang format apa pun,
fixture, CI, LICENSE (sengaja, menunggu keputusan pemilik), PROGRESS.md.

## 2. Tes (dijalankan)

```
> .\.venv\Scripts\python -m pytest -q
.....                                                                    [100%]
5 passed in 1.38s
```

Cakupan tes lama: `safe_output.py` (folder unik, `--verify`, `--check`, `--unique`), `qa_check.py`
(terjemahan baik lolos; istilah terlarang + URL hilang gagal; batas kata glosarium), `inventory.py`
(hanya file `.srt`). Tidak ada tes untuk PDF, DOCX, PPTX, XLSX, EPUB, PDF terenkripsi, atau
invarian "tidak menimpa" pada tingkat penulisan file.

## 3. Lint (dijalankan)

`ruff 0.17.6` tanpa konfigurasi proyek (aturan aktif berasal dari konfigurasi ruff di mesin ini):

```
> .\.venv\Scripts\python -m ruff check skills tests --output-format concise
qa_check.py:32:15 SIM905, :36:15 SIM905, :130:13 PLW1510, :181:67 UP034, :181:96 UP034, :245:15 ISC004
tests\test_scripts.py:12:12 PLW1510
Found 7 errors.
```

Semua temuan bersifat gaya, bukan bug. Proyek belum punya konfigurasi lint sendiri.

## 4. Dependensi

| Paket | Dipakai skrip lama? | Lisensi (pip-licenses, versi terpasang) | Catatan |
|---|---|---|---|
| pymupdf 2.2 | ya (inventory/qa untuk PDF) | **AGPL-3.0 atau lisensi komersial Artifex** | ditulis sebagai dependensi "inti" di requirements.txt |
| python-docx 1.2.0 | tidak | MIT | skrip memakai zipfile+regex |
| python-pptx 1.0.2 | tidak | MIT | idem |
| openpyxl 3.1.5 | tidak | MIT | idem |
| beautifulsoup4 | tidak | MIT | tidak terpasang, tidak dipakai |
| lxml 6.1.3 | tidak | BSD-3-Clause | |

Temuan penting PyMuPDF 2.2: metadata wheel-nya mewajibkan `onnxruntime`, `pymupdf-layout`,
`pymupdf4llm`, `numpy`, `networkx`, dll. `onnxruntime` tidak tersedia untuk Python 3.15 sehingga
`pip install pymupdf` gagal. Modul inti `pymupdf` berjalan normal bila dipasang dengan `--no-deps`
(diuji: import, konstanta redaksi tersedia, MuPDF 1.28.6). Ini harus didokumentasikan di panduan
instalasi extra `[pdf]`.

Inventaris lisensi dependensi yang direncanakan ada di bagian 8.

## 5. Kekurangan

1. **Masalah inti PLAN belum tersentuh:** tidak ada kode extract/apply. Agent harus menulis ulang
   kode ekstraksi dan penulisan ulang per sesi → boros token, hasil tidak konsisten.
2. `qa_check.py` mengekstrak DOCX/PPTX/XLSX dengan regex; pola `<w:t[^>]*>` juga cocok dengan
   `<w:tbl>`, `<w:tc>`, dsb. (aman secara kebetulan karena butuh `</w:t>` langsung). Urutan slide
   diurutkan leksikografis (`slide10` sebelum `slide2`).
3. Penulisan laporan memakai pola "cek-ada-lalu-tulis" (TOCTOU), bukan pembuatan file eksklusif.
4. Tidak ada deteksi OOXML terenkripsi (berkas OLE `D0 CF 11 E0`) atau EPUB ber-DRM
   (`META-INF/encryption.xml`/`rights.xml`).
5. `inventory.py` membaca tiap sheet XLSX dua kali; memperlakukan `pymupdf` sebagai wajib untuk PDF.
6. Komentar dan pesan kode berbahasa Indonesia; PLAN aturan 7 meminta komentar teknis berbahasa
   Inggris (kode baru Fase 1 mengikuti aturan; skrip lama dimigrasikan di Fase 2).
7. `.gitignore` belum punya pengecualian fixture/demo, cache build, dan format sumber lain.
8. README mengklaim beberapa perilaku agent ("dibaca otomatis oleh Codex") tanpa peta bukti.
9. Tidak ada konfigurasi lint/format, CI, atau versi Python yang dikunci.

## 6. Risiko

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Lisensi AGPL-3.0 PyMuPDF | pengguna/distributor wajib patuh AGPL atau beli lisensi komersial | jadikan extra opsional `[pdf]`, tidak di-vendor; lapisan abstraksi mesin PDF; tulis di docs |
| Fidelity tata letak PDF | teks Indonesia ~15–25% lebih panjang | auto-fit terbatas (maks turun ~10%), tandai halaman, jangan potong |
| Menimpa file sumber/hasil | kehilangan data | semua tulisan lewat pembuatan eksklusif (`open(..., "xb")`), hash SHA-256 sumber, tes invarian |
| File berhak cipta masuk repo | pelanggaran hak cipta | `.gitignore` memblokir dokumen; fixture dibuat sendiri oleh kode tes |
| Dependensi berat PyMuPDF 2.x | instalasi gagal di Python baru | dokumentasikan `--no-deps` atau pin versi |
| Penghapusan DRM | pelanggaran hukum | tolak PDF terenkripsi/OOXML terenkripsi/EPUB DRM; tidak ada kode dekripsi |

## 7. Prioritas

1. **P0** – Fase 1: paket `id_translate`, CLI, kontrak segmen JSONL, invarian keselamatan + tes.
2. **P0** – Handler format satu per satu dengan tes round-trip; PDF terakhir.
3. **P1** – Fase 2: skill memakai CLI; AGENTS.md sebagai sumber tunggal; validator skill.
4. **P2** – Fase 3: dokumentasi orisinal + peta klaim.
5. **P3** – Fase 4–6: CI, kepatuhan lisensi, evals, rilis.

## 8. Inventaris lisensi dependensi yang direncanakan

| Paket | Peran | Lisensi | Status |
|---|---|---|---|
| (stdlib Python) | md/txt, srt/vtt, json/arb, po, android-xml, html/epub | PSF | inti, tanpa dependensi |
| lxml | DOCX/PPTX/XLSX (manipulasi XML langsung) | BSD-3-Clause | extra `[office]` |
| PyYAML | YAML (posisi node untuk penggantian presisi) | MIT | extra `[yaml]` |
| PyMuPDF | PDF (ekstraksi, redaksi, tulis ulang, render) | **AGPL-3.0 atau komersial Artifex** | extra `[pdf]`, opsional, tidak di-vendor |
| Pillow | `compare` untuk format non-PDF (panel teks) | MIT-CMU (HPND) | extra `[compare]` |
| pytest | tes | MIT | dev |
| ruff | lint | MIT | dev |
| python-docx / python-pptx / openpyxl | hanya untuk membuat fixture dan memverifikasi hasil di tes | MIT | dev |
| XlsxWriter, et-xmlfile | dependensi transitif python-pptx/openpyxl | BSD-2-Clause / MIT | dev |

Keputusan lisensi repo sendiri belum dibuat (lihat `docs/license-decision.md`).
