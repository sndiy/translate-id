# Format PDF (prototipe / beta)

## Cara kerja
1. **Ekstraksi** per blok teks dengan koordinat (`bbox`), ukuran huruf, warna, dan gaya dasar.
2. **Redaksi aman**: teks lama dihapus dengan `fill=None`, `images=PDF_REDACT_IMAGE_NONE`, dan
   `graphics=PDF_REDACT_LINE_ART_NONE` sehingga gambar raster dan kotak/garis vektor tidak ikut
   terhapus atau tertimpa warna putih.
3. **Penulisan ulang**: teks Indonesia ditulis di `bbox` yang sama menggunakan font tertanam
   (`insert_htmlbox`) dengan auto-fit terbatas (maksimum turun **10%** dari ukuran huruf asli).
4. **Overflow**: bila teks tetap tidak muat setelah diperkecil 10%, teks **tidak pernah dipotong**;
   kotak diperluas ke bawah agar seluruh teks tetap tertulis, dan segmen/halaman dicatat di
   `review_flags` (`overflow_after_10pct_shrink`) untuk tinjauan visual manual.
5. **Perbandingan visual**: `id-translate compare sumber.pdf hasil.pdf --out compare.png --pages 1`
   merender gambar side-by-side.

## Dependensi dan lisensi
- Mesin PDF berada di balik antarmuka `id_translate.pdf.PdfEngine` sehingga dapat diganti tanpa
  mengubah kontrak segmen JSONL.
- Mesin bawaan adalah **PyMuPDF** sebagai extra opsional (`pip install 'id-translate[pdf]'`),
  **tidak di-vendor**.
- **Perhatian lisensi**: PyMuPDF berlisensi ganda **GNU AGPL-3.0** atau **lisensi komersial
  Artifex**. Pengguna bertanggung jawab mematuhi lisensi PyMuPDF sesuai cara pemakaiannya.

## Keterbatasan jujur (khususnya PDF hasil scan / OCR)
- **PDF terenkripsi / berpassword**: selalu ditolak (exit code 4). `id-translate` tidak menghapus
  password atau DRM.
- **PDF hasil scan (tanpa text layer)**: terdeteksi oleh `id-translate inspect` (`is_likely_scan: true`).
  Harus melewati OCR lebih dulu (mis. `ocrmypdf -l eng`) pada salinan file. Fidelity tata letak
  hasil scan jauh lebih rendah dan OCR dapat salah mengenali kata/angka; wajib tinjau manual.
- **Teks di dalam gambar**: tidak diubah otomatis; daftarkan di laporan terpisah.
- **Tata letak kompleks** (multi-kolom rapat, tabel bergaris rapat, rumus matematika): teks
  Indonesia umumnya lebih panjang ~15–25%, sehingga beberapa blok bisa tumpang tindih atau memicu
  flag overflow. Selalu periksa hasil dengan `id-translate compare`.
