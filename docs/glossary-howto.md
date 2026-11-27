# Cara Menyusun dan Memakai Glosarium

Glosarium (`glossary.md`) memastikan satu istilah Inggris selalu diterjemahkan dengan satu padanan
Indonesia yang konsisten di seluruh dokumen dan dibaca otomatis oleh `id-translate qa` serta
`id-translate glossary-scan`.

## 1. Memindai kandidat istilah

```bash
id-translate glossary-scan hasil-terjemahan/<proyek>/work/segments.jsonl \
  --out hasil-terjemahan/<proyek>/reports/glossary-candidates.md
```

Perintah ini mengumpulkan frasa kapital, akronim, dan bigram yang sering muncul.

## 2. Mengisi `glossary.md`

Salin templat dari [skills/translate-id/assets/glossary-template.md](../skills/translate-id/assets/glossary-template.md)
ke `<folder_hasil>/glossary.md`. Struktur yang dibaca otomatis oleh QA:

```markdown
## Glosarium
| EN | ID | Catatan |
|---|---|---|
| Interest Curve | Kurva Minat | "interest" = minat, bukan bunga |
| Mechanics | Mekanika | jangan campur dengan "Mekanik" |

## Terjemahan terlarang
- Kurva Bunga → Kurva Minat

## Dikecualikan dari deteksi sisa bahasa Inggris
- PyMuPDF
```

- Gunakan `/` pada kolom `ID` bila beberapa padanan diperbolehkan (mis. `pustaka / library`).
- Setiap kemunculan istilah di bagian **Terjemahan terlarang** ditandai sebagai **ERROR** oleh QA.

## 3. Memeriksa kepatuhan glosarium

```bash
id-translate glossary-scan work/segments.jsonl \
  --glossary glossary.md \
  --translations work/translations
```

Keluar dengan kode `1` jika ada terjemahan terlarang yang ditemukan.
