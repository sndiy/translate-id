# Keputusan LICENSE — MENUNGGU PEMILIK REPO

Status: **belum diputuskan.** Berkas `LICENSE` sengaja belum dibuat (PLAN aturan 4).

## Rekomendasi awal: MIT

Alasan:
- Sederhana dan permisif; mudah dipakai ulang oleh pengguna agent mana pun.
- Semua dependensi inti/opsional selain PyMuPDF berlisensi permisif (BSD/MIT/HPND).
- PyMuPDF (AGPL-3.0 atau komersial Artifex) **tidak di-vendor** dan hanya extra opsional `[pdf]`,
  sehingga kode repo tidak harus AGPL. Pengguna yang memasang extra `[pdf]` tetap wajib mematuhi
  lisensi PyMuPDF sendiri.

Alternatif yang perlu dipertimbangkan:
- **Apache-2.0**: permisif + klausul paten eksplisit.
- **AGPL-3.0**: bila ingin selaras penuh dengan PyMuPDF dan mewajibkan keterbukaan turunan.

Ini bukan nasihat hukum. Setelah pemilik memilih, isi field `license` di `SKILL.md` dan
`pyproject.toml` (PLAN Fase 4).
