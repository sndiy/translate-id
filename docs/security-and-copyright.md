# Keamanan, Privasi, Hak Cipta, dan Lisensi Dependensi

## 1. Keamanan berkas (invarian teruji)
- Semua penulisan keluaran memakai pembuatan file eksklusif (`open(..., "xb")`): file sumber dan
  file hasil lama tidak dapat tertimpa.
- `MANIFEST.json` mencatat SHA-256 file sumber; `reports/outputs.jsonl` mencatat SHA-256 setiap hasil.
  `id-translate verify` memverifikasi keduanya.
- Input terenkripsi atau ber-DRM (PDF berpassword/terenkripsi, Office OLE terenkripsi, EPUB dengan
  `META-INF/rights.xml` atau enkripsi selain font obfuscation) ditolak dengan exit code `4`.
- Kode paket tidak memiliki fungsi dekripsi, otentikasi password, atau penghapusan DRM (dijaga oleh
  uji statis di `tests/test_safety.py`).

## 2. Privasi dan hak cipta
- `id-translate` berjalan sepenuhnya lokal dan tidak mengirim isi dokumen ke layanan pihak ketiga.
- Gunakan hanya untuk dokumen yang Anda berhak proses (keperluan pribadi, belajar, atau kerja yang sah).
- Jangan memasukkan dokumen sumber maupun hasil terjemahan karya berhak cipta ke dalam repositori
  git; `.gitignore` memblokir `hasil-terjemahan/`, `work/`, `output/`, dan ekstensi dokumen umum.

## 3. Catatan lisensi PyMuPDF (wajib dibaca)
Backend PDF bawaan menggunakan **PyMuPDF** sebagai dependensi **opsional** (`pip install 'id-translate[pdf]'`)
dan **tidak di-vendor** dalam repositori ini.

PyMuPDF berlisensi ganda: **GNU Affero General Public License v3.0 (AGPL-3.0)** atau **lisensi
komersial Artifex Software**. Apabila Anda memasang, mendistribusikan, atau menjalankan extra `[pdf]`
sebagai layanan jaringan, Anda bertanggung jawab penuh untuk menilai dan memenuhi kewajiban lisensi
PyMuPDF sendiri. Dokumen ini bukan nasihat hukum.

Lihat daftar lengkap lisensi seluruh dependensi di [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
