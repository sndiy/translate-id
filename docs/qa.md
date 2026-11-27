# Pemeriksaan Kualitas (QA)

QA di `id-translate` menggabungkan pemeriksaan otomatis (heuristik) dan pemeriksaan manual.
**Lulus QA otomatis bukan bukti terjemahan tanpa salah.**

## 1. QA otomatis (`id-translate qa`)

```bash
id-translate qa sumber.docx hasil_ID.docx \
  --glossary hasil-terjemahan/<proyek>/glossary.md \
  --report hasil-terjemahan/<proyek>/reports/QA_report.md
```

Pemeriksaan yang dijalankan:
1. **Jumlah unit struktural**: halaman (PDF), slide (PPTX), sheet (XLSX), cue (SRT/VTT), pesan (PO), dokumen XHTML (EPUB).
2. **Angka**: membandingkan himpunan token angka (mengabaikan perbedaan pemisah ribuan/desimal).
3. **Placeholder & tag**: `{x}`, `{{x}}`, `%s`, `%1$s`, tag HTML/XML.
4. **URL**: memastikan tidak ada URL sumber yang hilang atau berubah.
5. **Glosarium**: terjemahan terlarang → ERROR; istilah sumber tanpa padanan ID → PERINGATAN.
6. **Sisa bahasa Inggris**: deteksi heuristik baris yang masih didominasi stopword Inggris.
7. **Rasio panjang**: memperingatkan bila rasio hasil/sumber di luar `0,75–1,60` (untuk dokumen > 200 karakter).
8. **QA khusus format**: validitas struktur JSON/YAML/Android XML, keutuhan timestamp & kecepatan baca subtitle (maks. 2 baris, 42 kar/baris, ≤ 17 kar/detik).
9. **Ejaan (opsional)**: dijalankan bila `hunspell` dan kamus `id_ID` terpasang di sistem.

Tambahkan `--strict` agar peringatan juga menghasilkan exit code `1`.

## 2. Pemeriksaan visual (`id-translate compare`)

```bash
id-translate compare sumber.pdf hasil_ID.pdf --out reports/hal1.png --pages 1
```

- Untuk PDF, menghasilkan render side-by-side halaman asli vs hasil.
- Untuk format non-PDF, menghasilkan panel teks hasil ekstraksi (diberi label jelas bahwa itu bukan render tata letak).

## 3. Daftar periksa manual

Lihat [skills/translate-id/references/qa-checklist.md](../skills/translate-id/references/qa-checklist.md):
periksa visual sampel 10% acak + semua item di `review_flags`, lakukan terjemah-balik sampel 10%
per bagian, dan jalankan `id-translate verify <folder_hasil>`.
