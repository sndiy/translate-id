"""JSON and Flutter ARB handlers, edited in place by string-literal offsets.

Translated: string values only (never keys, numbers, booleans, or nulls).
ARB: skips metadata keys starting with ``@`` (e.g. ``@@locale``, ``@greeting``), attaches
``@key.description`` as segment context, and updates ``@@locale`` to ``id`` when ``set_lang`` is on.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from id_translate.errors import InputError
from id_translate.formats.base import ApplyOptions
from id_translate.formats.textdoc import InPlaceTextHandler, TextDoc, read_text_doc
from id_translate.protect import DEFAULT_OPTIONS, has_translatable_text, mask
from id_translate.segments import Segment

TOKEN_RE = re.compile(
    r'\s*(?:(?P<str>"(?:\\.|[^"\\])*")|(?P<punct>[{}\[\]:,])|(?P<atom>true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?))'
)


def _scan_json_strings(text: str) -> list[tuple[int, int, tuple[str | int, ...], str]]:
    """Return (start, end, path_tuple, decoded_str) for every string VALUE in valid JSON."""
    # Validate syntax first so malformed JSON fails cleanly.
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid JSON: {exc}") from exc

    results: list[tuple[int, int, tuple[str | int, ...], str]] = []
    # Stack entries: ["obj", state, current_key] or ["arr", next_index]
    stack: list[list] = []
    pos = 0
    n = len(text)
    while pos < n:
        m = TOKEN_RE.match(text, pos)
        if not m:
            break
        pos = m.end()
        punct = m.group("punct")
        if punct == "{":
            if stack and stack[-1][0] == "arr":
                idx = stack[-1][1]
                stack[-1][1] += 1
                stack.append(["obj", "key", None, idx])
            else:
                stack.append(["obj", "key", None, None])
        elif punct == "[":
            if stack and stack[-1][0] == "arr":
                idx = stack[-1][1]
                stack[-1][1] += 1
                stack.append(["arr", 0, idx])
            else:
                stack.append(["arr", 0, None])
        elif punct in ("}", "]"):
            if stack:
                stack.pop()
            if stack and stack[-1][0] == "obj":
                stack[-1][1] = "after_val"
        elif punct == ":":
            if stack and stack[-1][0] == "obj":
                stack[-1][1] = "val"
        elif punct == ",":
            if stack and stack[-1][0] == "obj":
                stack[-1][1] = "key"
                stack[-1][2] = None
        elif m.group("str") is not None:
            s, e = m.start("str"), m.end("str")
            val = json.loads(m.group("str"))
            if not stack:
                results.append((s, e, (), val))
            elif stack[-1][0] == "obj":
                if stack[-1][1] == "key":
                    stack[-1][2] = val
                elif stack[-1][1] == "val":
                    path = _build_path(stack)
                    results.append((s, e, path, val))
                    stack[-1][1] = "after_val"
            elif stack[-1][0] == "arr":
                idx = stack[-1][1]
                stack[-1][1] += 1
                path = (*_build_path(stack), idx)
                results.append((s, e, path, val))
        elif m.group("atom") is not None:
            if stack and stack[-1][0] == "obj":
                stack[-1][1] = "after_val"
            elif stack and stack[-1][0] == "arr":
                stack[-1][1] += 1
    return results


def _build_path(stack: list[list]) -> tuple[str | int, ...]:
    parts: list[str | int] = []
    for frame in stack:
        if frame[0] == "obj":
            if frame[3] is not None:
                parts.append(frame[3])
            if frame[2] is not None:
                parts.append(frame[2])
        elif frame[0] == "arr":
            if frame[2] is not None:
                parts.append(frame[2])
    return tuple(parts)


def _format_key_path(path: tuple[str | int, ...]) -> str:
    return ".".join(str(p) for p in path) if path else "$"


def _key_skeleton(obj):
    if isinstance(obj, dict):
        return {k: _key_skeleton(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_key_skeleton(v) for v in obj]
    return type(obj).__name__


class JsonHandler(InPlaceTextHandler):
    name = "json"
    extensions = (".json",)
    id_prefix = "js"

    def _skip_path(self, path: tuple[str | int, ...]) -> bool:
        return False

    def _context_for(self, data, path: tuple[str | int, ...]) -> str | None:
        return None

    def parse(self, doc: TextDoc, path: Path) -> list[Segment]:
        data = json.loads(doc.text)
        segs: list[Segment] = []
        for s, e, key_path, val in _scan_json_strings(doc.text):
            if self._skip_path(key_path):
                continue
            masked, protect = mask(val, DEFAULT_OPTIONS)
            style: dict = {"key": _format_key_path(key_path)}
            ctx = self._context_for(data, key_path)
            if ctx:
                style["context"] = ctx
            segs.append(
                Segment(
                    id=f"{self.id_prefix}{len(segs) + 1:04d}",
                    type="string",
                    text=masked,
                    style=style,
                    loc={"start": s, "end": e, "key": _format_key_path(key_path)},
                    protect=protect,
                    status="pending" if has_translatable_text(masked) else "skip",
                )
            )
        return segs

    def encode(self, seg: Segment, final_text: str, doc: TextDoc) -> str:
        return json.dumps(final_text, ensure_ascii=False)

    def extra_qa(self, source: Path, target: Path) -> tuple[list[str], list[str], list[str]]:
        try:
            s_obj = json.loads(read_text_doc(source).text)
            t_obj = json.loads(read_text_doc(target).text)
        except json.JSONDecodeError as exc:
            return [f"JSON hasil tidak valid: {exc}"], [], []
        if _key_skeleton(s_obj) != _key_skeleton(t_obj):
            return ["Struktur kunci/tipe JSON berubah antara sumber dan hasil."], [], []
        return [], [], ["Struktur kunci JSON identik dengan sumber."]


class ArbHandler(JsonHandler):
    name = "arb"
    extensions = (".arb",)
    id_prefix = "arb"

    def _skip_path(self, path: tuple[str | int, ...]) -> bool:
        return bool(path) and isinstance(path[0], str) and path[0].startswith("@")

    def _context_for(self, data, path: tuple[str | int, ...]) -> str | None:
        if isinstance(data, dict) and len(path) == 1 and isinstance(path[0], str):
            meta = data.get(f"@{path[0]}")
            if isinstance(meta, dict) and isinstance(meta.get("description"), str):
                return meta["description"]
        return None

    def lang_edits(self, doc: TextDoc, options: ApplyOptions) -> list[tuple[int, int, str]]:
        for s, e, key_path, _ in _scan_json_strings(doc.text):
            if key_path == ("@@locale",):
                return [(s, e, json.dumps(options.lang, ensure_ascii=False))]
        return []
