# Laporan Evaluasi (`docs/evals.md`)

Seluruh angka di bawah berasal dari **eksekusi nyata** skrip [evals/run_evals.py](../evals/run_evals.py)
pada **26 November 2026** (Windows, Python 3.15.2, `.venv` dengan `id-translate 0.1.0.dev0`,
`lxml 6.1.3`, `PyYAML 6.0.4`, `Pillow 13.0.0`, `PyMuPDF 2.2`).

## Metodologi
- Terdiri dari **18 kasus** buatan sendiri (tanpa dokumen berhak cipta) lintas seluruh format yang
  didukung ditambah 1 kasus uji negatif glosarium.
- Kasus 01–17 memakai **terjemahan tiruan (*pseudo-translation*)** yang memperpanjang teks sekitar
  **~25%** dengan karakter non-ASCII tanpa mengubah token pelindung (`⟦P1⟧`, `⟦S1⟧`), untuk
  mensimulasikan pemekaran teks Bahasa Indonesia.
- Kasus 18 secara sengaja memasukkan istilah terlarang dari glosarium untuk memastikan `id-translate qa`
  menangkap pelanggaran tersebut sebagai `ERROR`.

Perintah untuk mengulang evaluasi:

```bash
python evals/run_evals.py
```

## Hasil run nyata

Ringkasan: **18/18 kasus lulus**, total waktu **859,8 ms**, **100% file sumber tidak berubah**
(diverifikasi SHA-256 sebelum dan sesudah).

| Kasus | Format | Segmen | Overflow flag | Pelanggaran glosarium | Angka tidak cocok | QA error | Waktu (ms) | Status |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `01_md_placeholders_urls` | markdown | 2 | 0 | 0 | 0 | 0 | 75,2 | PASS |
| `02_md_tables_nested_lists` | markdown | 9 | 0 | 0 | 0 | 0 | 39,5 | PASS |
| `03_md_long_prose` | markdown | 8 | 0 | 0 | 0 | 0 | 40,5 | PASS |
| `04_txt_bom_crlf_numbers` | text | 2 | 0 | 0 | 0 | 0 | 44,1 | PASS |
| `05_srt_dense_subtitles` | srt | 2 | 0 | 0 | 0 | 0 | 38,0 | PASS |
| `06_vtt_voice_tags_styles` | vtt | 1 | 0 | 0 | 0 | 0 | 36,7 | PASS |
| `07_json_nested_placeholders` | json | 2 | 0 | 0 | 0 | 0 | 40,2 | PASS |
| `08_arb_icu_plurals` | arb | 1 | 0 | 0 | 0 | 0 | 36,8 | PASS |
| `09_yaml_comments_colons` | yaml | 2 | 0 | 0 | 0 | 0 | 67,7 | PASS |
| `10_po_plurals_context` | po | 3 | 0 | 0 | 0 | 0 | 36,6 | PASS |
| `11_android_xml_escapes` | android-xml | 2 | 0 | 0 | 0 | 0 | 38,3 | PASS |
| `12_docx_tables_headers_bold` | docx | 7 | 0 | 0 | 0 | 0 | 58,4 | PASS |
| `13_pptx_slides_notes` | pptx | 4 | 0 | 0 | 0 | 0 | 52,6 | PASS |
| `14_xlsx_formulas_numbers` | xlsx | 6 | 0 | 0 | 0 | 0 | 47,1 | PASS |
| `15_html_code_and_attrs` | html | 5 | 0 | 0 | 0 | 0 | 43,1 | PASS |
| `16_epub_mimetype_lang` | epub | 3 | 0 | 0 | 0 | 0 | 48,1 | PASS |
| `17_pdf_colored_box_image` | pdf | 4 | 4 | 0 | 0 | 0 | 79,8 | PASS |
| `18_glossary_forbidden_guard` | markdown | 1 | 0 | 1 | 0 | 1 *(sesuai ekspektasi)* | 37,0 | PASS |

### Catatan temuan nyata
- **`17_pdf_colored_box_image`:** keempat blok teks memicu flag `overflow_after_10pct_shrink` saat
  diperpanjang ~25% karena batas penyusutan huruf dibatasi maksimum −10%. Tidak ada teks yang
  terpotong, 1 gambar raster dan ≥2 kotak vektor berwarna tetap utuh, dan jumlah halaman tetap 1.
- **`05_srt_dense_subtitles`:** QA mendeteksi peringatan kepadatan subtitle (melebihi 42 karakter/baris
  atau kecepatan baca > 17 kar/detik) sementara timestamp tetap utuh.
- **`18_glossary_forbidden_guard`:** pelanggaran istilah terlarang `"Kurva Bunga"` tertangkap sebagai
  1 QA error.

## Keterbatasan evaluasi ini (jujur)
1. **Bukan ukuran kualitas bahasa atau akurasi makna:** karena memakai *pseudo-translation* (~+25%),
   evaluasi ini tidak mengukur keluwesan Bahasa Indonesia, ketepatan terjemahan idiom, atau kualitas
   keluaran model LLM tertentu.
2. **Fixture sintetis berukuran kecil:** kasus uji dirancang sebagai fixture ringkas buatan sendiri,
   bukan buku ratusan halaman atau PDF multi-kolom rapat dunia nyata.
3. **Tanpa render visual Office/EPUB:** tata letak DOCX, PPTX, XLSX, dan EPUB diverifikasi pada level
   struktur XML/ZIP dan ekstraksi ulang, bukan melalui render LibreOffice/Word.
4. **Waktu eksekusi bergantung mesin:** angka milidetik di atas adalah hasil satu kali jalan di mesin
   pengembangan lokal, bukan benchmark resmi.
