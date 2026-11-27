# Daftar periksa QA (centang semua sebelum menyatakan selesai)

## Otomatis (`scripts/qa_check.py`)
- [ ] Jumlah halaman/slide/sheet sama dengan sumber
- [ ] Angka cocok (atau perbedaannya dijelaskan)
- [ ] Placeholder, tag, dan URL utuh
- [ ] Nol "terjemahan terlarang" dari glosarium
- [ ] Istilah glosarium muncul dengan padanan yang disetujui
- [ ] Tidak ada baris yang masih tampak Inggris (kecuali yang memang dikecualikan)
- [ ] Rasio panjang wajar; ejaan diperiksa jika kamus tersedia

## Visual (render ke gambar, bandingkan dengan sumber)
- [ ] Tidak ada teks terpotong, menimpa gambar/garis, atau keluar dari halaman/slide/sel
- [ ] Warna latar kotak/bagian tetap benar setelah teks lama dihapus
- [ ] Header, footer, nomor halaman, tautan, daftar isi masih benar
- [ ] Sampel 10% acak per bagian + SEMUA halaman yang ditandai sudah dilihat mata

## Makna dan bahasa (manual)
- [ ] Terjemah-balik sampel 10% per bagian; tidak ada pergeseran makna
- [ ] Judul dan rujukan silang sinkron (Bab/Tabel/Gambar)
- [ ] Nada dan sapaan konsisten; tidak ada campuran Anda/kamu
- [ ] Istilah yang diragukan sudah ditandai `[?]` di `reports/review_list.md`

## Keamanan berkas
- [ ] `safe_output.py --verify <folder_hasil>` menyatakan sumber tidak berubah
- [ ] Tidak ada file sumber atau hasil lama yang ditimpa/dihapus
- [ ] Laporan akhir menyebut keterbatasan: teks di gambar, indeks/pustaka, halaman perlu tinjau
