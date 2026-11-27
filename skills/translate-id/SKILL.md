---
name: translate-id
description: >-
  Menerjemahkan dokumen/file apa pun ke Bahasa Indonesia secara akurat, konsisten, dan tanpa merusak
  tata letak, lalu menyimpan hasil di folder baru tanpa menimpa file asli. Gunakan skill ini setiap kali
  pengguna meminta terjemahan, lokalisasi, "translate", "terjemahkan", "alihbahasa", atau membuat
  versi Bahasa Indonesia dari file PDF, DOCX, PPTX, XLSX, EPUB, HTML, Markdown, TXT, subtitle SRT/VTT,
  JSON/YAML/PO/ARB/Android XML, buku, makalah, slide, manual, atau UI/aplikasi, walaupun pengguna tidak
  menyebut kata "skill". Wajib dipakai juga saat pengguna menekankan "jangan ngawur", "tata letak
  jangan berantakan", atau "jangan menimpa file asli". Hanya untuk target Bahasa Indonesia.
compatibility: >-
  Memerlukan Python >= 3.10 dan CLI id-translate (pip install -e .). Extra opsional: [office] untuk
  DOCX/PPTX/XLSX, [yaml] untuk YAML, [pdf] (PyMuPDF, AGPL-3.0/Artifex) untuk PDF, [compare] untuk PNG.
---

# translate-id — Terjemahan ke Bahasa Indonesia yang aman dan rapi

Prinsip: **akurat > konsisten > rapi > cepat.** Model HANYA menerjemahkan teks; CLI `id-translate`
mengurus ekstraksi, perlindungan placeholder (`⟦P1⟧`), penulisan ulang file, perbandingan visual,
dan QA. Baca juga aturan keras di `AGENTS.md`.

## Alur kerja (ikuti berurutan)

### 0. Siapkan folder hasil dan inventaris
```bash
id-translate init "<file_sumber>"                         # cetak path folder hasil baru; catat
id-translate inspect "<file_sumber>" --json "<folder_hasil>/reports/inventory.json"
id-translate extract "<file_sumber>" --result "<folder_hasil>"
```
- Semua keluaran berikutnya hanya di `<folder_hasil>/{output,work,reports}`.
- Jika file terenkripsi/ber-DRM (exit code 4) → **BERHENTI** dan laporkan.
- Jika PDF hasil scan (`is_likely_scan: true`) → baca `references/layout-by-format.md` bagian OCR
  dan beri tahu pengguna bahwa fidelity tata letak lebih rendah.

### 1. Glosarium dan gaya (WAJIB, lalu minta persetujuan)
```bash
id-translate glossary-scan "<folder_hasil>/work/segments.jsonl" \
  --out "<folder_hasil>/reports/glossary-candidates.md"
```
- Salin `assets/glossary-template.md` ke `<folder_hasil>/glossary.md` dan isi: domain, sapaan
  (`Anda` atau `kamu`), istilah kunci, nama yang tidak diterjemahkan, dan **Terjemahan terlarang**.
- Baca `references/style-guide-id.md` untuk keputusan gaya. Tampilkan glosarium ke pengguna dan
  **tunggu persetujuan**. Jangan lanjut tanpa persetujuan untuk dokumen > 5 halaman.

### 2. Pilot
- Ambil ±10 halaman/segmen yang mewakili (judul, daftar isi, paragraf, tabel/kotak, catatan kaki).
- Terjemahkan ke `<folder_hasil>/work/translations/pilot.jsonl` (`{"id": "...", "text": "..."}`),
  pertahankan setiap token seperti `⟦P1⟧` atau `⟦S1⟧...⟦/S1⟧` persis sama.
- Terapkan dengan `--allow-partial` lalu bandingkan secara visual:
```bash
id-translate apply --result "<folder_hasil>" --allow-partial
id-translate compare "<file_sumber>" "<file_hasil>" --out "<folder_hasil>/reports/pilot.png" --pages 1
```
- Laporkan masalah tata letak, estimasi ukuran pekerjaan, dan perkiraan token. **Tunggu persetujuan.**

### 3. Terjemahan penuh (dapat dilanjutkan dari checkpoint)
```bash
id-translate batch "<folder_hasil>/work/segments.jsonl" --max-tokens 1500
```
- Terjemahkan tiap `batch-NNNN.jsonl` ke file target `work/translations/batch-NNNN.jsonl` dengan
  mengikuti `glossary.md`. Menjalankan ulang `batch` otomatis melewati segmen yang sudah selesai
  dan memanfaatkan translation memory (`work/tm.jsonl`).
- Setelah semua batch selesai, tulis file hasil baru:
```bash
id-translate apply --result "<folder_hasil>"
```
- Jangan pernah mengekspor ulang lewat format lain (mis. DOCX→PDF→DOCX).

### 4. QA (semua wajib)
```bash
id-translate qa "<file_sumber>" "<file_hasil>" \
  --glossary "<folder_hasil>/glossary.md" --report "<folder_hasil>/reports/QA_report.md"
```
- Lakukan juga pemeriksaan manual: bandingkan sampel 10% acak + semua segmen/halaman yang muncul di
  `review_flags` memakai `id-translate compare`; lakukan terjemah-balik sampel 10% per bagian; cek
  `references/qa-checklist.md`. Ulangi hingga ERROR = 0; jelaskan semua peringatan.

### 5. Laporan akhir dan verifikasi
```bash
id-translate verify "<folder_hasil>"   # pastikan SHA-256 sumber dan hasil tercatat tidak berubah
```
Laporkan: lokasi hasil, jumlah segmen, ringkasan QA, daftar halaman/segmen yang perlu tinjau manual,
elemen yang tidak diterjemahkan (teks dalam gambar, indeks, pustaka), dan keterbatasan jujur.

## Aturan penanganan masalah
- **Teks tidak muat:** auto-fit terbatas (maks. turun ~10%), lalu tandai halaman; jangan potong.
- **Ragu makna:** tandai `[?]` di `reports/review_list.md` beserta kemungkinan artinya.
- **Teks di dalam gambar:** jangan diedit otomatis; daftarkan di `reports/figures_with_text.md`.
- **Gagal di tengah jalan:** simpan terjemahan batch yang sudah jadi lalu lanjutkan via `id-translate batch`.

## Referensi (baca sesuai kebutuhan)
- [references/layout-by-format.md](references/layout-by-format.md) — teknik menjaga tata letak per format
- [references/style-guide-id.md](references/style-guide-id.md) — kaidah gaya, ejaan, angka, false friend
- [references/qa-checklist.md](references/qa-checklist.md) — daftar periksa sebelum menyatakan selesai
- [assets/glossary-template.md](assets/glossary-template.md) — templat glosarium (dibaca otomatis oleh QA)
