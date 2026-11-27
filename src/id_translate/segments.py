"""Segment contract (JSONL) and translation files.

segments.jsonl — one JSON object per line, produced by ``extract``:
    id       stable identifier, unique within the file
    type     paragraph | heading | list_item | table_cell | cue | string | attr | block | ...
    text     masked SOURCE text sent to the model (protect tokens like ⟦P1⟧ inside)
    style    format-specific style hints (font, size, level, context, ...)
    loc      location (char offsets, page+bbox, sheet/cell, cue timing, XML part, ...)
    protect  {"⟦P1⟧": "{name}", ...} literals restored after translation
    status   pending (must be translated) | skip (no translatable text)

segments.meta.json — provenance: format, source path, source SHA-256, tool version.

translations (*.jsonl) — produced by the model/agent, one object per line:
    {"id": "<segment id>", "text": "<masked Indonesian text with the same tokens>"}
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from id_translate import __version__
from id_translate.errors import InputError, ValidationError
from id_translate.safety import write_new_text

SCHEMA = "id-translate/segments@1"
STATUSES = {"pending", "skip"}
log = logging.getLogger("id_translate")


@dataclass
class Segment:
    id: str
    type: str
    text: str
    style: dict = field(default_factory=dict)
    loc: dict = field(default_factory=dict)
    protect: dict = field(default_factory=dict)
    status: str = "pending"

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=False)

    @classmethod
    def from_dict(cls, d: dict) -> Segment:
        missing = {"id", "type", "text"} - set(d)
        if missing:
            raise ValidationError(f"segment is missing keys: {sorted(missing)}")
        status = d.get("status", "pending")
        if status not in STATUSES:
            raise ValidationError(f"segment {d['id']}: unknown status {status!r}")
        return cls(
            id=str(d["id"]),
            type=str(d["type"]),
            text=str(d["text"]),
            style=dict(d.get("style") or {}),
            loc=dict(d.get("loc") or {}),
            protect=dict(d.get("protect") or {}),
            status=status,
        )


def meta_path_for(segments_path: Path) -> Path:
    p = Path(segments_path)
    return p.with_name(p.name.removesuffix(".jsonl") + ".meta.json")


def write_segments(path: Path, segments: list[Segment], meta: dict) -> tuple[Path, Path]:
    ids = [s.id for s in segments]
    if len(ids) != len(set(ids)):
        raise ValidationError("duplicate segment ids produced by extractor")
    body = "".join(s.to_json() + "\n" for s in segments)
    full_meta = {
        "schema": SCHEMA,
        "tool_version": __version__,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "segment_count": len(segments),
        "pending_count": sum(1 for s in segments if s.status == "pending"),
        **meta,
    }
    mp = meta_path_for(path)
    if mp.exists():
        from id_translate.errors import OverwriteRefusedError

        raise OverwriteRefusedError(f"refusing to overwrite existing file: {mp}")
    write_new_text(path, body)
    write_new_text(mp, json.dumps(full_meta, indent=2, ensure_ascii=False))
    return Path(path), mp


def read_segments(path: Path) -> list[Segment]:
    path = Path(path)
    if not path.is_file():
        raise InputError(f"segments file not found: {path}")
    out: list[Segment] = []
    seen: set[str] = set()
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"{path}:{n}: invalid JSON ({exc.msg})") from exc
        seg = Segment.from_dict(d)
        if seg.id in seen:
            raise ValidationError(f"{path}:{n}: duplicate segment id {seg.id!r}")
        seen.add(seg.id)
        out.append(seg)
    return out


def read_meta(segments_path: Path) -> dict:
    mp = meta_path_for(segments_path)
    if not mp.is_file():
        raise InputError(f"segments meta file not found: {mp}")
    meta = json.loads(mp.read_text(encoding="utf-8"))
    if meta.get("schema") != SCHEMA:
        raise ValidationError(f"unsupported segments schema: {meta.get('schema')!r}")
    return meta


def _translation_files(path: Path) -> list[Path]:
    path = Path(path)
    if path.is_dir():
        return sorted(p for p in path.rglob("*.jsonl") if p.is_file())
    if path.is_file():
        return [path]
    return []


def read_translations(paths: list[Path] | Path) -> dict[str, str]:
    """Read one or more translation JSONL files/dirs. Later entries override earlier ones."""
    if isinstance(paths, (str, Path)):
        paths = [Path(paths)]
    result: dict[str, str] = {}
    for root in paths:
        files = _translation_files(Path(root))
        if not files and not Path(root).exists():
            raise InputError(f"translations path not found: {root}")
        for f in files:
            for n, line in enumerate(f.read_text(encoding="utf-8-sig").splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValidationError(f"{f}:{n}: invalid JSON ({exc.msg})") from exc
                if not isinstance(d, dict) or "id" not in d or "text" not in d:
                    raise ValidationError(f'{f}:{n}: each line needs "id" and "text"')
                sid = str(d["id"])
                if sid in result and result[sid] != d["text"]:
                    log.debug("translation for %s overridden by %s:%d", sid, f, n)
                result[sid] = str(d["text"])
    return result
