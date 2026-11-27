# THIRD_PARTY_NOTICES.md — Pemberitahuan Dependensi Pihak Ketiga

Paket inti `id-translate` **tidak memiliki dependensi pihak ketiga wajib** (hanya pustaka standar
Python 3.10+). Tidak ada pustaka pihak ketiga yang di-vendor di dalam repositori ini.

Tabel berikut mencatat seluruh dependensi opsional (*extras*) dan dependensi pengembangan (`[dev]`)
yang dideklarasikan di [pyproject.toml](pyproject.toml) beserta lisensinya.

## Dependensi opsional (runtime extras)

| Paket | Extra | Fungsi | Lisensi | Sumber |
|---|---|---|---|---|
| `lxml` | `[office]` | Manipulasi XML langsung untuk DOCX, PPTX, XLSX | BSD-3-Clause | https://lxml.de/ |
| `PyYAML` | `[yaml]` | Parsing node YAML untuk edit in-place | MIT | https://pyyaml.org/ |
| `Pillow` | `[compare]` | Pembuatan gambar perbandingan PNG side-by-side | MIT-CMU (HPND) | https://python-pillow.org/ |
| `pymupdf` | `[pdf]` | Backend PDF opsional (ekstraksi, redaksi, tulis ulang, render) | **GNU AGPL-3.0 atau lisensi komersial Artifex** | https://pymupdf.readthedocs.io/ |

### Pemberitahuan khusus PyMuPDF (`[pdf]`)
**PyMuPDF** (MuPDF) berlisensi ganda di bawah **GNU Affero General Public License v3.0 (AGPL-3.0)**
atau **lisensi komersial Artifex Software** (https://artifex.com/licensing). PyMuPDF bersifat
**opsional**, **tidak di-vendor**, dan hanya digunakan apabila pengguna memasang extra `[pdf]`.
Pengguna yang memasang, mendistribusikan, atau menjalankan `id-translate[pdf]` (termasuk sebagai
layanan jaringan) bertanggung jawab penuh mematuhi ketentuan AGPL-3.0 atau memperoleh lisensi
komersial Artifex. Dokumen ini bukan nasihat hukum.

## Dependensi pengembangan & pengujian (`[dev]`)

| Paket | Fungsi | Lisensi |
|---|---|---|
| `pytest` | Menjalankan rangkaian tes | MIT |
| `ruff` | Pemeriksaan lint kode Python | MIT |
| `python-docx` | Membuat dan memverifikasi fixture DOCX di tes | MIT |
| `python-pptx` | Membuat dan memverifikasi fixture PPTX di tes | MIT |
| `openpyxl` | Membuat dan memverifikasi fixture XLSX di tes | MIT |
| `XlsxWriter` *(transitif python-pptx)* | Dependensi transitif pengujian | BSD-2-Clause |
| `et-xmlfile` *(transitif openpyxl)* | Dependensi transitif pengujian | MIT |
