# Format Subtitle: SRT & WebVTT (beta)

- **Ekstensi:** `.srt`, `.vtt`
- **Dependensi:** pustaka standar Python (tanpa extra).

## Yang diterjemahkan
- Teks isi setiap cue saja.

## Yang dijaga utuh
- Nomor cue / pengenal cue, baris timestamp dan pengaturan posisi (`align:...`), header `WEBVTT`, blok `NOTE`, `STYLE`, dan `REGION`, tag inline (`<i>`, `<v Host>`, `<c.yellow>`, `<00:06.500>`), dan tag override ASS (`{\an8}`).
- Baris kosong tidak sengaja di dalam terjemahan cue otomatis dirapatkan agar struktur blok cue tidak pecah.

## Pemeriksaan QA khusus subtitle
- **ERROR** jika jumlah cue berubah atau timestamp cue berbeda dari sumber.
- **PERINGATAN** jika cue melebihi 2 baris, > 42 karakter per baris, atau kecepatan baca > 17 karakter/detik.

## Pengujian
Diuji di [tests/test_format_subtitles.py](../../tests/test_format_subtitles.py).
