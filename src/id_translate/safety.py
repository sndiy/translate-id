"""Safety invariants: never overwrite, hash sources, record and verify outputs.

Every file this package produces is created with exclusive mode (``open(path, "xb")``),
so an existing file can never be replaced, even under a race.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import time
import zipfile
from pathlib import Path

from id_translate import __version__
from id_translate.errors import EncryptedInputError, InputError, OverwriteRefusedError, SafetyError

MANIFEST = "MANIFEST.json"
OUTPUTS_LOG = "reports/outputs.jsonl"
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
# EPUB font obfuscation algorithms are not DRM; anything else in encryption.xml is treated as DRM.
EPUB_FONT_OBFUSCATION = {
    "http://www.idpf.org/2008/embedding",
    "http://ns.adobe.com/pdf/enc#RC",
}


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_new_bytes(path: Path, data: bytes) -> Path:
    """Create ``path`` with ``data``. Raises OverwriteRefusedError if it already exists."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "xb") as fh:
            fh.write(data)
    except FileExistsError as exc:
        raise OverwriteRefusedError(f"refusing to overwrite existing file: {path}") from exc
    return path


def write_new_text(path: Path, text: str, encoding: str = "utf-8") -> Path:
    return write_new_bytes(path, text.encode(encoding))


def append_jsonl(path: Path, record: dict) -> None:
    """Append-only log write (never truncates existing content)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def unique_path(target: Path) -> Path:
    """Return ``target`` or ``<stem>-N<suffix>`` that does not exist yet."""
    target = Path(target)
    if not target.exists():
        return target
    i = 2
    while True:
        cand = target.with_name(f"{target.stem}-{i}{target.suffix}")
        if not cand.exists():
            return cand
        i += 1


def ensure_distinct_output(source: Path, out: Path) -> None:
    src, dst = Path(source).resolve(), Path(out).resolve()
    if src == dst:
        raise SafetyError(f"output path is the source file itself: {dst}")
    if dst.exists():
        raise OverwriteRefusedError(f"output already exists, refusing to overwrite: {dst}")


def make_result_dir(source: Path, out_root: Path | None = None, dry_run: bool = False) -> Path:
    """Create ``<out_root>/<stem>_ID_<timestamp>[-N]/{output,work,reports}`` plus MANIFEST.json."""
    source = Path(source).resolve()
    if not source.is_file():
        raise InputError(f"source is not a file: {source}")
    root = Path(out_root).resolve() if out_root else source.parent / "hasil-terjemahan"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = f"{source.stem}_ID_{stamp}"
    if dry_run:
        return unique_path(root / base)
    root.mkdir(parents=True, exist_ok=True)
    result = None
    for i in range(1, 1000):
        cand = root / (base if i == 1 else f"{base}-{i}")
        try:
            cand.mkdir(exist_ok=False)
        except FileExistsError:
            continue
        result = cand
        break
    if result is None:
        raise SafetyError("could not create a unique result folder")
    for sub in ("output", "work", "reports"):
        (result / sub).mkdir()
    manifest = {
        "tool": "id-translate",
        "tool_version": __version__,
        "source_path": str(source),
        "source_size_bytes": source.stat().st_size,
        "source_sha256": sha256_file(source),
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "python": platform.python_version(),
        "target_language": "id",
    }
    write_new_text(result / MANIFEST, json.dumps(manifest, indent=2, ensure_ascii=False))
    return result


def read_manifest(result_dir: Path) -> dict:
    mpath = Path(result_dir) / MANIFEST
    if not mpath.is_file():
        raise InputError(f"{MANIFEST} not found in {result_dir}")
    return json.loads(mpath.read_text(encoding="utf-8"))


def record_output(result_dir: Path, output: Path, extra: dict | None = None) -> None:
    rec = {
        "path": str(Path(output).resolve()),
        "sha256": sha256_file(output),
        "recorded": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if extra:
        rec.update(extra)
    append_jsonl(Path(result_dir) / OUTPUTS_LOG, rec)


def verify_result_dir(result_dir: Path) -> tuple[bool, list[str]]:
    """Check the source hash from MANIFEST and every recorded output hash."""
    result_dir = Path(result_dir)
    messages: list[str] = []
    ok = True
    m = read_manifest(result_dir)
    src = Path(m["source_path"])
    if not src.is_file():
        ok = False
        messages.append(f"FAIL source missing: {src}")
    elif sha256_file(src) != m["source_sha256"]:
        ok = False
        messages.append(f"FAIL source changed since the result folder was created: {src}")
    else:
        messages.append(f"OK source unchanged (sha256 {m['source_sha256'][:16]}...): {src}")
    log = result_dir / OUTPUTS_LOG
    if log.is_file():
        for line in log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            p = Path(rec["path"])
            if not p.is_file():
                ok = False
                messages.append(f"FAIL recorded output missing: {p}")
            elif sha256_file(p) != rec["sha256"]:
                ok = False
                messages.append(f"FAIL recorded output was modified: {p}")
            else:
                messages.append(f"OK output unchanged: {p}")
    return ok, messages


def check_ole_encrypted(path: Path) -> None:
    """Encrypted OOXML files are OLE compound documents, not ZIP archives."""
    with open(path, "rb") as fh:
        head = fh.read(8)
    if head == OLE_MAGIC:
        raise EncryptedInputError(
            f"{path.name} is an OLE container (password-protected/encrypted Office file or legacy "
            "binary format). Refusing to process; id-translate never removes protection."
        )


def check_epub_drm(path: Path) -> None:
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise InputError(f"not a valid EPUB/ZIP file: {path}") from exc
    with zf:
        names = set(zf.namelist())
        if "META-INF/rights.xml" in names:
            raise EncryptedInputError(f"{path.name} contains META-INF/rights.xml (DRM). Refusing.")
        if "META-INF/encryption.xml" in names:
            xml = zf.read("META-INF/encryption.xml").decode("utf-8", "replace")
            algos = set(re.findall(r"Algorithm\s*=\s*[\"']([^\"']+)[\"']", xml))
            if not algos or algos - EPUB_FONT_OBFUSCATION:
                raise EncryptedInputError(
                    f"{path.name} has encrypted resources (META-INF/encryption.xml). Refusing; "
                    "id-translate never removes DRM."
                )


def same_file(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False
