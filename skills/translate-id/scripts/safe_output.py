#!/usr/bin/env python3
"""
safe_output.py - Folder hasil terjemahan yang TIDAK PERNAH menimpa apa pun.

Perintah:
  python safe_output.py <file_sumber> [--out-root DIR]
      Buat folder baru <out-root>/<nama>_ID_<waktu>/ berisi output/ work/ reports/
      dan MANIFEST.json (SHA-256 sumber). Cetak path folder di baris terakhir.
      Default out-root: folder "hasil-terjemahan" di sebelah file sumber.

  python safe_output.py --unique <path_target>
      Cetak path yang belum dipakai (menambah -2, -3, ... jika sudah ada).

  python safe_output.py --check <path_target>
      Exit 1 jika path sudah ada (jangan tulis ke sana).

  python safe_output.py --verify <folder_hasil>
      Hitung ulang SHA-256 sumber dan bandingkan dengan MANIFEST.json.
      Exit 1 jika file sumber berubah.
"""
import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def unique_path(target: Path) -> Path:
    """Kembalikan path yang belum ada; tidak pernah menimpa."""
    target = Path(target)
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    i = 2
    while True:
        cand = target.with_name(f"{stem}-{i}{suffix}")
        if not cand.exists():
            return cand
        i += 1


def make_result_dir(source: Path, out_root: Path | None = None) -> Path:
    source = source.resolve()
    if not source.is_file():
        raise SystemExit(f"Sumber bukan file atau tidak ada: {source}")
    root = (out_root or source.parent / "hasil-terjemahan").resolve()
    root.mkdir(parents=True, exist_ok=True)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = f"{source.stem}_ID_{stamp}"
    result = None
    for i in range(1, 1000):
        name = base if i == 1 else f"{base}-{i}"
        cand = root / name
        try:
            cand.mkdir(exist_ok=False)  # gagal jika sudah ada: tidak menimpa
            result = cand
            break
        except FileExistsError:
            continue
    if result is None:
        raise SystemExit("Gagal membuat folder hasil yang unik.")

    for sub in ("output", "work", "reports"):
        (result / sub).mkdir()

    manifest = {
        "source_path": str(source),
        "source_size_bytes": source.stat().st_size,
        "source_sha256": sha256(source),
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "python": platform.python_version(),
        "target_language": "id",
        "note": "Sumber tidak boleh diubah. Verifikasi: safe_output.py --verify <folder>",
    }
    (result / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return result


def verify(result_dir: Path) -> bool:
    mpath = result_dir / "MANIFEST.json"
    if not mpath.is_file():
        print(f"MANIFEST.json tidak ditemukan di {result_dir}", file=sys.stderr)
        return False
    m = json.loads(mpath.read_text(encoding="utf-8"))
    src = Path(m["source_path"])
    if not src.is_file():
        print(f"Sumber hilang: {src}", file=sys.stderr)
        return False
    now = sha256(src)
    ok = now == m["source_sha256"]
    print("OK: sumber tidak berubah." if ok else "PERINGATAN: sumber BERUBAH sejak folder dibuat!")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?")
    ap.add_argument("--out-root")
    ap.add_argument("--unique", metavar="PATH")
    ap.add_argument("--check", metavar="PATH")
    ap.add_argument("--verify", metavar="DIR")
    a = ap.parse_args()

    if a.unique:
        print(unique_path(Path(a.unique)))
        return
    if a.check:
        exists = Path(a.check).exists()
        print("ADA (jangan ditimpa)" if exists else "BELUM ADA (aman)")
        sys.exit(1 if exists else 0)
    if a.verify:
        sys.exit(0 if verify(Path(a.verify)) else 1)
    if not a.path:
        ap.print_help()
        sys.exit(2)
    d = make_result_dir(Path(a.path), Path(a.out_root) if a.out_root else None)
    print(d)


if __name__ == "__main__":
    main()
