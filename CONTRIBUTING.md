# Panduan Kontribusi

Terima kasih berminat berkontribusi ke `terjemahan-id`!

## Prinsip utama
1. **Konten orisinal:** jangan menyalin teks atau kode dari repositori lain. Catat ide yang dipinjam di [docs/credits.md](docs/credits.md).
2. **Tanpa file berhak cipta:** semua fixture di `tests/fixtures/` harus buatan sendiri atau berlisensi bebas yang jelas. Jangan pernah meng-commit dokumen sumber atau hasil terjemahan karya berhak cipta.
3. **Invarian keselamatan tidak boleh dilemahkan:** tidak pernah menimpa file, verifikasi SHA-256, tolak input terenkripsi/DRM, dan tidak ada kode penghapusan DRM.
4. **Bahasa:** dokumentasi utama berbahasa Indonesia; kode, identifier, dan komentar teknis berbahasa Inggris.

## Menyiapkan lingkungan lokal

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
# Opsional untuk pengujian PDF: pip install -e ".[pdf]"
```

## Pemeriksaan sebelum membuka PR

```bash
ruff check src tests scripts
python -m pytest -q
python scripts/validate_skill.py
python scripts/check_markdown_links.py
python scripts/check_licenses.py
```

Jika menambah klaim baru di `README.md`, petakan buktinya di [docs/claims.md](docs/claims.md).
Jika menambah dependensi baru, perbarui [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
Gunakan format [Conventional Commits](https://www.conventionalcommits.org/) untuk pesan commit.
