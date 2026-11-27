# Daftar Isu yang Diketahui (Known Issues — v0.1.0)

1. **PDF hasil scan / tanpa text layer:** `id-translate inspect` mendeteksi kemungkinan scan
   (`is_likely_scan: true`), tetapi OCR tidak dijalankan otomatis. Pengguna harus menjalankan OCR
   (mis. `ocrmypdf -l eng`) pada salinan file terlebih dahulu; fidelity tata letak tetap rendah.
2. **Overflow pada PDF dengan kotak teks sempit atau tata letak multi-kolom rapat:** teks Bahasa
   Indonesia umumnya 15–25% lebih panjang. Auto-fit dibatasi maksimum −10%; blok yang tetap tidak
   muat diperluas ke bawah agar teks tidak terpotong dan ditandai di `review_flags`
   (`overflow_after_10pct_shrink`), sehingga dapat tumpang tindih dengan elemen di bawahnya dan
   memerlukan tinjauan visual via `id-translate compare`.
3. **Instalasi PyMuPDF 2.2 di Python 3.15:** metadata wheel PyMuPDF 2.2 meminta `onnxruntime` yang
   belum tersedia untuk Python 3.15. Workaround: `pip install --no-deps pymupdf` (lihat
   [docs/troubleshooting.md](troubleshooting.md)).
4. **Teks di dalam gambar, judul chart, dan SmartArt (PDF/DOCX/PPTX/XLSX):** tidak diekstrak atau
   diedit otomatis; harus didaftarkan secara manual bila perlu diterjemahkan.
5. **`id-translate compare` untuk format non-PDF:** menghasilkan panel teks hasil ekstraksi (Pillow),
   bukan render tata letak visual dokumen (tidak membundel LibreOffice/renderer Office).
6. **Cek ejaan Bahasa Indonesia di `id-translate qa`:** bersifat opsional dan otomatis dilewati bila
   `hunspell` serta kamus `id_ID` tidak terpasang di sistem.
7. **Format yang belum didukung (`planned`):** Office biner lama (`.doc`, `.ppt`, `.xls`),
   OpenDocument (`.odt`, `.odp`, `.ods`), InDesign (`.idml`), subtitle `.ass`/`.ssa`, dan Apple `.strings`.
8. **Skrip lama di `skills/translate-id/scripts/`:** dipertahankan sementara untuk kompatibilitas
   mundur (diuji oleh `tests/test_scripts.py`); alur utama menggunakan CLI `id-translate`.
