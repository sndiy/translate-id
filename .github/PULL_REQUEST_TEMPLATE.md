## Ringkasan perubahan
Jelaskan apa yang diubah dan alasannya.

## Daftar periksa sebelum merge
- [ ] Semua konten orisinal; tidak ada dokumen sumber/hasil berhak cipta yang ikut masuk
- [ ] `ruff check src tests scripts` lolos
- [ ] `python -m pytest -q` lolos (termasuk invarian keselamatan)
- [ ] `python scripts/validate_skill.py` lolos
- [ ] `python scripts/check_markdown_links.py` lolos
- [ ] Jika klaim di `README.md` berubah, `docs/claims.md` sudah diperbarui
- [ ] Jika dependensi berubah, `THIRD_PARTY_NOTICES.md` sudah diperbarui
