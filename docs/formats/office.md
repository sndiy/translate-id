# Format Office OOXML: DOCX, PPTX, XLSX (beta)

- **Ekstensi:** `.docx`, `.pptx`, `.xlsx`
- **Dependensi:** extra `[office]` (`lxml`). Tidak mengekspor lewat PDF.

## Perilaku per format
- **DOCX:** menerjemahkan paragraf pada badan dokumen, tabel, header/footer, catatan kaki/akhir, dan komentar; mengelompokkan run bergaya sama dengan token `⟦S1⟧…⟦/S1⟧`; melewatkan penghapusan terlacak (`<w:del>`) dan kode field; menyetel `w:lang="id-ID"`.
- **PPTX:** menerjemahkan paragraf pada slide dan `notesSlides` (terurut numerik); mempertahankan gaya run, transisi, animasi, media, dan jumlah slide; menyetel `lang="id-ID"`.
- **XLSX:** menerjemahkan `sharedStrings` dan `inlineStr` saja; **tidak pernah** menyentuh sel rumus (`<f>`), angka, tanggal, atau nama sheet.

## Keamanan & keterbatasan
- Berkas Office terenkripsi/berpassword (kontainer OLE) ditolak sejak awal dengan exit code `4`.
- Judul chart, teks SmartArt, dan teks di dalam gambar tidak diedit otomatis.

## Pengujian
Diuji pada fixture buatan sendiri + penolakan OLE terenkripsi di [tests/test_format_ooxml.py](../../tests/test_format_ooxml.py).
