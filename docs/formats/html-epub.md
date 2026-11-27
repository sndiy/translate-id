# Format Web & E-book: HTML & EPUB (beta)

- **Ekstensi:** `.html`, `.htm`, `.xhtml`, `.epub`
- **Dependensi:** pustaka standar Python (tanpa extra).

## Perilaku per format
- **HTML / XHTML:** menerjemahkan text node di luar `<script>`, `<style>`, `<code>`, `<pre>`, `<kbd>`, `<samp>`, `<var>`, `<textarea>`, `<svg>`, `<math>`, serta atribut tampilan (`alt`, `title`, `placeholder`, `aria-label`, dan `<meta name="description" content>`). Menyetel `lang="id"` pada `<html>`.
- **EPUB:** memproses seluruh dokumen `.xhtml`/`.html` di dalam kontainer, mempertahankan entri `mimetype` di urutan pertama tanpa kompresi (`ZIP_STORED`), serta memperbarui `lang="id"` dan `<dc:language>id</dc:language>` di berkas `.opf`.

## Keamanan
- EPUB dengan `META-INF/rights.xml` atau enkripsi selain font obfuscation di `META-INF/encryption.xml` ditolak dengan exit code `4`.

## Pengujian
Diuji di [tests/test_format_html_epub.py](../../tests/test_format_html_epub.py).
