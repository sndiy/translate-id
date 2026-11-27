# Panduan Gaya Bahasa Indonesia

Ringkasan praktis kaidah gaya yang digunakan bersama `glossary.md`. Versi ringkas untuk agent juga
tersedia di [skills/translate-id/references/style-guide-id.md](../skills/translate-id/references/style-guide-id.md).

## 1. Keputusan proyek (ditetapkan sekali di glosarium)
- **Sapaan:** pilih `Anda` (formal: dokumentasi resmi, laporan, hukum) atau `kamu` (santai: tutorial,
  buku populer, gim). Jangan dicampur dalam satu dokumen.
- **Register:** Bahasa Indonesia baku (PUEBI & KBBI) yang mengalir alami, mengikuti nada dokumen asli.
- **Istilah teknis asing:** pertahankan bila sudah lazim di bidangnya atau beri padanan Indonesia
  yang disepakati secara konsisten di glosarium.

## 2. Kaidah penulisan utama
- Bentuk baku KBBI: *desainer, analisis, aktivitas, teknologi, risiko, kualitas, ubah, praktik, nasihat*.
- Bedakan awalan `di-` (dirangkai: *dibuat, disimpan*) dan preposisi `di` (dipisah: *di sini, di folder*).
- Hindari terjemahan harfiah yang kaku ("dilakukan oleh…", "adalah merupakan…"). Terjemahkan makna,
  bukan struktur kalimat Inggris kata per kata.
- Jaga istilah yang dilarang berubah: kode, nama variabel, URL, email, placeholder (`{name}`, `%s`,
  `⟦P1⟧`), rumus, dan nama merek/karya.

## 3. Angka, tanggal, mata uang
- Pemisah ribuan titik, desimal koma: `1.250,50` (dalam prosa; jangan ubah angka di dalam kode/rumus/data mentah).
- Tanggal: `26 November 2026`.
- Mata uang: `Rp1.000.000` (tanpa spasi); mata uang asing mengikuti sumber (`US$79,99`).

## 4. False friend yang sering muncul

| Inggris | Hindari (kalkir) | Padanan sesuai konteks |
|---|---|---|
| `actually` | aktualnya | sebenarnya |
| `eventually` | eventual | akhirnya |
| `sensible` | sensibel | masuk akal, bijak |
| `interest` (desain/psikologi) | bunga | minat, ketertarikan |
| `judgment` | penghakiman | penilaian |
| `library` (pemrograman) | libreri | pustaka / *library* |
