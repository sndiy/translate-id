# Format Markdown & Teks Polos (beta)

- **Ekstensi:** `.md`, `.markdown`, `.mdown`, `.mkd`, `.txt`, `.text`
- **Dependensi:** pustaka standar Python (tanpa extra).

## Yang diterjemahkan
- Markdown: heading (ATX & Setext), paragraf, item daftar, teks kutipan (`>`), sel tabel, teks tautan dan alt gambar.
- Teks polos: setiap paragraf (blok yang dipisahkan baris kosong).

## Yang dijaga utuh
- Front matter YAML (`--- ... ---`), blok kode berpagar (```` ``` ```` / `~~~`), blok kode berindentasi, komentar HTML, definisi rujukan tautan (`[ref]: ...`), kode inline, tujuan URL tautan, autolink, entitas HTML, ID heading `{#id}`, indentasi lanjutan, BOM, encoding (`UTF-8`, `UTF-16`), dan gaya baris baru (`LF`/`CRLF`).
- Karakter `|` di dalam terjemahan sel tabel Markdown otomatis di-escape menjadi `\|`.

## Pengujian
Diuji round-trip identitas (identik per byte), teks lebih panjang, BOM/CRLF/UTF-16, dan placeholder di [tests/test_format_text.py](../../tests/test_format_text.py).
