# AGENTS.md — Aturan Terjemahan ke Bahasa Indonesia (sumber tunggal)

Berlaku untuk SEMUA tugas menerjemahkan dokumen/file ke Bahasa Indonesia, apa pun formatnya
(PDF, DOCX, PPTX, XLSX, EPUB, HTML, MD/TXT, SRT/VTT, JSON/YAML/PO/ARB/Android XML, dan lainnya).
Bahasa target HANYA Indonesia. Untuk detail langkah, baca `skills/translate-id/SKILL.md`.
File instruksi khusus runtime lain (`CLAUDE.md`, `GEMINI.md`, `.cursor/rules/`, `.github/copilot-instructions.md`)
hanya penunjuk tipis ke file ini.

## A. Aturan keras (tidak boleh dilanggar)
1. **Jangan menimpa, mengganti, atau menghapus** file sumber maupun hasil sebelumnya. Semua hasil
   ditulis ke folder BARU: `hasil-terjemahan/<nama>_ID_<waktu>/` (buat dengan
   `id-translate init <file>` atau `python skills/translate-id/scripts/safe_output.py <file>`).
2. Kerjakan hanya pada salinan di folder hasil. Model HANYA menerjemahkan teks segmen; gunakan CLI
   `id-translate` untuk ekstraksi, penulisan ulang, perbandingan, dan QA. Setelah selesai, jalankan
   `id-translate verify <folder_hasil>` untuk membuktikan sumber tidak berubah (hash SHA-256).
3. **Jangan mengarang.** Setiap segmen sumber harus punya terjemahan; jangan melewatkan, meringkas,
   menambah, atau memperhalus isi. Kalau ragu arti, tandai `[?]` di laporan, jangan menebak diam-diam.
4. **Jangan mengklaim "tanpa kesalahan".** Laporkan apa yang diperiksa, apa yang lolos, dan apa yang
   masih meragukan (`reports/QA_report.md`).
5. **Hak dan privasi.** Terjemahkan hanya file yang pengguna berhak pakai, untuk keperluan pribadi/
   belajar/kerja yang sah. Jangan menghapus DRM atau password, jangan mengunggah/mendistribusikan hasil,
   jangan mengirim isi file ke layanan pihak ketiga tanpa izin pengguna. Jika file terenkripsi atau
   ber-DRM, BERHENTI dan laporkan.
6. **Jangan terjemahkan**: kode, nama variabel/kunci/ID, URL, email, path, tag/markup, placeholder
   (`{x}`, `{{x}}`, `%s`, `%1$s`, token `⟦P1⟧`), nama orang/merek/produk/judul karya, rumus, dan angka.
7. **Tata letak harus terjaga.** Jumlah halaman/slide/sheet sama; tidak ada teks terpotong, menimpa
   gambar, atau keluar halaman. Jika teks Indonesia tidak muat, perkecil secara terbatas (maks. ~10%)
   lalu TANDAI halaman itu. Jangan pernah memotong teks agar muat.

## B. Alur wajib (berhenti di titik persetujuan)
0. **Inisialisasi & inventaris** (`id-translate init`, `id-translate inspect`, `id-translate extract`) →
1. **Glosarium + gaya** (`id-translate glossary-scan` + `glossary.md`) → *STOP, minta persetujuan* →
2. **Pilot** (±10 halaman/segmen representatif + `id-translate compare`) → *STOP, minta persetujuan* →
3. **Terjemahan penuh** (`id-translate batch`, terjemahkan per batch dengan checkpoint & TM, `id-translate apply`) →
4. **QA** (`id-translate qa` + tinjauan visual + sampel terjemah-balik) →
5. **Laporan akhir & verifikasi** (`id-translate verify`).

## C. Kualitas bahasa
- Bahasa Indonesia baku yang wajar dibaca (PUEBI + KBBI), bukan terjemahan kata per kata.
- Konsisten: satu istilah = satu padanan di seluruh dokumen; ikuti `glossary.md` yang disetujui.
- Waspadai false friend dan salah makna konteks (mis. *interest* = minat, bukan bunga, dalam konteks
  psikologi/desain). Pilih makna sesuai domain dokumen.
- Sapaan (`Anda` atau `kamu`) ditetapkan SEKALI di tahap glosarium, lalu dipakai konsisten.
- Format angka/tanggal gaya Indonesia: `1.250,50`, `25 November 2026`, `Rp1.000.000`.

## D. Pelaporan
Selesai berarti ada: file hasil di `output/`, `glossary.md`, `reports/QA_report.md`, daftar halaman/
segmen yang perlu tinjau manual, dan daftar elemen yang tidak diterjemahkan (mis. teks di dalam
gambar). Laporkan jujur jika ada bagian yang gagal.

## E. Gaya komunikasi dengan pengguna
Singkat, langsung, jujur. Jangan menanyakan hal yang bisa disimpulkan dari file atau percakapan.
Tanyakan hanya keputusan yang memang memengaruhi hasil (sapaan, istilah ambigu, format keluaran).

## F. Aturan Git (berlaku untuk semua agent)
1. **Jangan menjalankan perintah git yang mengubah status repositori**: `init`, `add`, `commit`,
   `branch`, `checkout`, `switch`, `merge`, `rebase`, `reset`, `stash`, `tag`, `push`, `pull`,
   `remote`, `clean`, `pre-commit install`, dan sejenisnya. Pemilik repo yang melakukan commit.
2. **Jangan membuat repositori git sendiri.** Jika folder `.git` belum ada, biarkan.
3. **`.gitignore` boleh dibuat atau diperbarui** setiap kali muncul berkas sementara/build/cache baru,
   tetap memblokir dokumen sumber dan hasil terjemahan, sambil mengecualikan fixture buatan sendiri
   dan aset demo (`!tests/fixtures/**`, `!docs/demo/**`).
4. **Hanya perintah baca** (`git status`, `git diff`, `git log`, `git check-ignore`) yang boleh
   dijalankan jika repo sudah ada, semata untuk inspeksi.
5. Di akhir tiap checkpoint pengembangan, catat bagian **"Saran commit"** di `PROGRESS.md` (daftar
   file berubah + satu saran pesan Conventional Commits).
