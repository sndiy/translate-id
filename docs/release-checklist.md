# Checklist Rilis v0.1.0 (untuk Pemilik Repositori)

## 1. Keputusan lisensi (wajib sebelum rilis publik)
- [ ] Putuskan lisensi repositori di [docs/license-decision.md](license-decision.md) (rekomendasi awal: MIT) dan buat berkas `LICENSE` di akar repo.
- [ ] Isi field `license` di [pyproject.toml](../pyproject.toml) dan [skills/translate-id/SKILL.md](../skills/translate-id/SKILL.md).
- [ ] Perbarui bagian lisensi di [README.md](../README.md) dan [README.en.md](../README.en.md).

## 2. Versi dan changelog
- [ ] Ubah versi `0.1.0.dev0` → `0.1.0` di [pyproject.toml](../pyproject.toml), [src/id_translate/__init__.py](../src/id_translate/__init__.py), dan [CITATION.cff](../CITATION.cff).
- [ ] Pindahkan isi `[Unreleased]` di [CHANGELOG.md](../CHANGELOG.md) menjadi `[0.1.0] - YYYY-MM-DD`.
- [ ] Tinjau [docs/releases/v0.1.0.md](releases/v0.1.0.md) dan [docs/known-issues.md](known-issues.md).

## 3. Verifikasi lokal sebelum tag
- [ ] `ruff check src tests scripts evals` keluar `0`.
- [ ] `python -m pytest -q` keluar `0`.
- [ ] `python evals/run_evals.py` keluar `0`.
- [ ] `python scripts/validate_skill.py` keluar `0`.
- [ ] `python scripts/check_markdown_links.py` keluar `0`.
- [ ] `python scripts/check_licenses.py` keluar `0`.
- [ ] `git status` bersih dari dokumen berhak cipta, `hasil-terjemahan/`, dan berkas sementara.

## 4. Commit, CI, dan tag (dijalankan oleh pemilik repo)
- [ ] Commit perubahan (dapat mengikuti saran commit di [PROGRESS.md](../PROGRESS.md)).
- [ ] Push ke remote dan pastikan workflow `.github/workflows/ci.yml` hijau pada Python 3.10–3.13 + `[pdf]`.
- [ ] Buat tag `v0.1.0` dan publikasikan GitHub Release dengan isi [docs/releases/v0.1.0.md](releases/v0.1.0.md).
- [ ] Atur deskripsi "About" dan topics repositori (lihat usulan di [docs/repo-meta.md](repo-meta.md)).
