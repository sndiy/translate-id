# Menjaga tata letak per format

Daftar isi: Aturan umum · PDF · DOCX · PPTX · XLSX · EPUB/HTML · Markdown/TXT · SRT/VTT ·
JSON/YAML/i18n · Teks di dalam gambar

## Aturan umum
- Terjemahkan **teks saja**; struktur, gaya, ID, dan referensi dibiarkan.
- Teks Indonesia umumnya lebih panjang dari Inggris (sering sekitar 15–25%; ukur sendiri di pilot).
  Rencanakan ruang sejak awal: spasi baris, ukuran huruf, lebar kolom.
- Pakai font yang mendukung seluruh karakter Indonesia dan mirip aslinya. Font sumber yang tidak
  tertanam jangan diasumsikan ada; sematkan font pengganti.
- Jangan ubah ukuran halaman, margin, orientasi, atau urutan elemen.
- Setelah menulis, render ulang dan bandingkan dengan sumber. Jangan percaya hanya pada ekstraksi teks.

## PDF (teks asli / text layer)
Alat umum: PyMuPDF (`pip install pymupdf`).
1. Ekstrak per halaman dengan `page.get_text("dict")` → blok, baris, span (bbox, font, ukuran, warna, flags).
   Gabungkan baris dalam satu paragraf menjadi satu segmen terjemahan; pisahkan header/footer,
   nomor halaman, keterangan gambar, dan isi tabel.
2. Untuk tiap blok: tambah anotasi redaksi pada bbox teks lama lalu `page.apply_redactions(...)`
   dengan opsi agar **gambar dan grafik vektor tidak ikut terhapus** (mis. `images=PDF_REDACT_IMAGE_NONE`
   dan, pada versi PyMuPDF yang mendukung, `graphics=PDF_REDACT_LINE_ART_NONE`). Isi warna redaksi
   sama dengan latar bagian itu (jangan asal putih pada kotak berwarna).
3. Tulis teks Indonesia di bbox yang sama: `page.insert_htmlbox(rect, html, css=..., archive=...)`
   (PyMuPDF versi baru) atau `insert_textbox`. Sematkan font yang mendukung bahasa Indonesia.
   Pertahankan tebal/miring dengan menerjemahkan per span gaya, bukan menyatukan semuanya.
4. Teks terlalu panjang: (a) spasi baris minimum ~0,95; (b) perkecil huruf bertahap, maksimum turun ~10%
   dari aslinya; (c) jika masih tidak muat, tandai halaman, jangan potong.
5. Pertahankan link (`page.get_links()`), bookmark/outline (terjemahkan judulnya), dan nomor halaman.
6. Simpan ke file BARU (`save` ke path baru, jangan `incremental` ke sumber). Cek jumlah halaman sama.
- **PDF hasil scan:** jalankan OCR dulu (mis. `ocrmypdf -l eng`) ke salinan, periksa kualitas OCR, baru
  terjemahkan. Beri tahu pengguna bahwa fidelity lebih rendah dan OCR bisa salah baca.
- **Indeks/daftar pustaka:** biarkan bahasa asli (urutan abjad tidak berlaku di bahasa target); catat
  keputusan ini di laporan. Teks yang berupa gambar: daftarkan, jangan diedit.
- **Terenkripsi/berpassword:** berhenti dan laporkan.
- **Alternatif jika fidelity penuh mustahil:** hasilkan juga versi DOCX/Markdown yang mengalir dan
  jelaskan perbedaannya; jangan menyatakannya identik.

## DOCX
Alat: `python-docx` untuk dasar; XML langsung untuk kotak teks, catatan kaki, komentar.
- Terjemahkan per **paragraf**, bukan per run. Kumpulkan run yang gayanya sama, terjemahkan, lalu
  distribusikan ulang ke run (pertahankan tebal/miring/tautan). Jangan buang run kosong penanda
  bookmark atau field.
- Tangani: tabel (termasuk sel gabungan), header/footer, catatan kaki/akhir, kotak teks, komentar,
  daftar bernomor, hyperlink (teks tampil diterjemahkan, URL tidak), field/TOC (jangan terjemahkan
  kode field; minta pengguna "Update field" untuk daftar isi, atau perbarui bila alat mendukung).
- Perubahan terlacak (tracked changes): jangan diterima/ditolak otomatis; laporkan jika ada.
- Setel bahasa dokumen ke `id-ID` (atribut `w:lang` pada gaya/run) agar pemeriksa ejaan Word benar.
- Hasilkan file `.docx` baru; jangan menyimpan ke file sumber.

## PPTX
Alat: `python-pptx`.
- Terjemahkan per paragraf pada tiap shape (termasuk placeholder, grup, tabel, catatan pembicara).
- Teks panjang: gunakan autofit "kecilkan teks saat meluap" atau turunkan ukuran huruf terbatas; jangan
  mengubah ukuran shape. Cek visual tiap slide.
- Judul chart/SmartArt/gambar berisi teks sering tidak bisa diakses lewat API: daftarkan di laporan.
- Setel `lang="id-ID"` pada run. Pertahankan transisi, animasi, urutan slide, dan notes.

## XLSX
Alat: `openpyxl` (hati-hati: bisa menghilangkan fitur tertentu; uji dulu pada salinan).
- Terjemahkan hanya sel **teks**. Lewati rumus (diawali `=`), angka, tanggal, kunci/ID, kode.
- Nama sheet: terjemahkan hanya bila diminta; jika diubah, perbarui semua rumus yang merujuknya
  (batas 31 karakter, tanpa `[]:*?/\`).
- Pertahankan lebar kolom, format sel, validasi data, komentar sel, dan string pembanding yang
  dipakai rumus `IF`/`VLOOKUP` (jangan ubah tanpa memperbarui rumusnya).

## EPUB / HTML
Alat: BeautifulSoup/lxml.
- Terjemahkan **text node** saja. Lewati `<script>`, `<style>`, `<code>`, `<pre>`, `<kbd>`.
- Terjemahkan atribut tampilan: `alt`, `title`, `placeholder`, `aria-label`, `<title>`, meta description.
- Pertahankan `id`, `class`, `href`, `src`. Setel `lang="id"` pada `<html>` dan, untuk EPUB,
  `dc:language` = `id`, termasuk dokumen navigasi/TOC.
- Entitas HTML dan tag inline (`<em>`, `<a>`) dijaga; jangan memecah tag di tengah kalimat tanpa perlu.

## Markdown / TXT
- Jangan ubah: blok kode, kode inline, URL tautan, front matter (hanya nilai yang memang teks
  tampilan), tabel (jaga jumlah kolom), penanda daftar, indentasi, jenis baris baru, dan encoding/BOM.

## SRT / VTT (subtitle)
- Nomor cue dan timestamp tidak berubah. Maksimal 2 baris per cue, sekitar 42 karakter per baris,
  kecepatan baca ≤ ~17 karakter/detik. Padatkan dengan menyingkat kalimat, bukan membuang makna;
  catat cue yang terpaksa dipadatkan.

## JSON / YAML / PO / ARB / strings / Android XML
- Terjemahkan **nilai**, bukan kunci. Pertahankan placeholder (`{name}`, `%s`, `%1$s`, `{{x}}`,
  ICU `{count, plural, ...}`) dan tag. Urutan placeholder boleh berubah hanya bila format mendukung
  penomoran posisi (`%1$s`).
- Bahasa Indonesia tidak membedakan bentuk jamak; di CLDR hanya kategori `other`. Isi `other`
  (dan salin ke kategori lain bila format menuntut).
- Android XML: escape apostrof (`\'`) dan karakter khusus; jangan ubah atribut `name`/`translatable`.
- Simpan sebagai file bahasa baru (mis. `id.json`, `values-in/strings.xml`), bukan menimpa file Inggris.

## Teks di dalam gambar
Jangan diedit otomatis. Daftarkan (halaman, deskripsi, teks Inggris, terjemahan) di
`reports/figures_with_text.md`. Hanya edit gambar jika pengguna memintanya dan alatnya memungkinkan.
