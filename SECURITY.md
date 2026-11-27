# Kebijakan Keamanan

## Cakupan keamanan proyek ini
- Invarian keselamatan berkas (tidak menimpa file sumber/hasil, validasi path, verifikasi SHA-256).
- Penolakan berkas terenkripsi/ber-DRM (PDF, Office OLE, EPUB).
- Keamanan parsing XML/YAML/ZIP (mis. proteksi terhadap input tak tepercaya).

## Cara melaporkan kerentanan
**Jangan membuka issue publik untuk kerentanan keamanan.**

Laporkan secara privat melalui fitur *GitHub Security Advisories* (*Report a vulnerability* di tab
**Security** repositori) atau hubungi pengelola repositori secara langsung. Sertakan langkah
reproduksi minimal (pakai fixture buatan sendiri, bukan dokumen berhak cipta), dampak yang
diperkirakan, dan versi Python / `id-translate`.

Kami berusaha merespons laporan dalam 7 hari kerja.
