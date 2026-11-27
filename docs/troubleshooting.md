# Pemecahan Masalah (Troubleshooting)

## Exit code `4` — Penolakan keselamatan
- **`refusing to overwrite existing file`**: target keluaran sudah ada. Pilih path baru atau jalankan
  `id-translate apply --result <folder>` agar nama unik (`-2`, `-3`, …) dipakai otomatis.
- **`source file differs ... (SHA-256 mismatch)`**: file sumber berubah setelah `extract`. Jalankan
  ulang `init` dan `extract` di folder hasil baru.
- **`encrypted` / `OLE container` / `DRM`**: file terkunci password atau ber-DRM. `id-translate`
  tidak pernah menghapus password atau DRM; gunakan salinan tidak terenkripsi yang Anda miliki haknya.

## Exit code `5` — Dependensi opsional belum terpasang
Pasang extra yang diminta pesan error:
- DOCX/PPTX/XLSX → `pip install -e ".[office]"`
- YAML → `pip install -e ".[yaml]"`
- `compare` → `pip install -e ".[compare]"`
- PDF → `pip install -e ".[pdf]"`

### PyMuPDF gagal dipasang di Python 3.15 karena `onnxruntime`
Wheel PyMuPDF 2.2 mencantumkan `onnxruntime` sebagai dependensi, yang belum tersedia untuk Python 3.15.
Modul inti PyMuPDF yang dipakai `id-translate` berjalan tanpa `onnxruntime`:
```bash
pip install --no-deps pymupdf
```

## Exit code `6` — Validasi segmen / token gagal
- **`segment(s) have no translation`**: ada segmen `pending` yang belum punya terjemahan. Lengkapi
  batch atau pakai `--allow-partial` (khusus pilot; segmen kosong dibiarkan dalam bahasa sumber).
- **`missing tokens` / `unexpected/duplicated tokens`**: model menghapus, mengubah, atau menggandakan
  token pelindung seperti `⟦P1⟧` atau `⟦S1⟧`. Perbaiki baris segmen tersebut di `work/translations/*.jsonl`.

## Teks PDF tidak muat (`overflow_after_10pct_shrink`)
Teks tidak pernah dipotong; kotak diperluas ke bawah dan halaman dicatat di `review_flags`. Render
halaman tersebut dengan `id-translate compare --pages <N>` lalu padatkan terjemahan bila perlu.
