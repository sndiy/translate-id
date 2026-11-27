# Suite Evaluasi (`evals/`)

Suite evaluasi deterministik berisi **18 kasus** lintas seluruh format yang didukung plus uji penjaga
glosarium. Pengujian memakai **terjemahan tiruan (*pseudo-translation*)** yang memperpanjang teks
sekitar **~25%** tanpa mengubah token pelindung (`⟦P1⟧`, `⟦S1⟧`) untuk menguji tata letak,
keutuhan struktur, dan pemeriksaan QA — **bukan** menilai kefasihan atau ketepatan makna terjemahan
model LLM.

## Cara menjalankan ulang

```bash
python evals/run_evals.py
# Opsional: simpan laporan JSON
python evals/run_evals.py --json eval-results.json
```

Memerlukan extra `[dev,pdf]` agar kasus DOCX/PPTX/XLSX/PDF berjalan. Laporan hasil eksekusi nyata
tercatat di [docs/evals.md](../docs/evals.md).
