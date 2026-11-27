"""Handler registry. Handler modules import optional dependencies lazily."""

from __future__ import annotations

import importlib
from pathlib import Path

from id_translate.errors import UnsupportedFormatError
from id_translate.formats.base import FormatHandler

# (module, class) in priority order; the first handler whose extension and sniff match wins.
_SPECS = [
    ("id_translate.formats.markdown", "MarkdownHandler"),
    ("id_translate.formats.plaintext", "PlainTextHandler"),
    ("id_translate.formats.subtitles", "SrtHandler"),
    ("id_translate.formats.subtitles", "VttHandler"),
    ("id_translate.formats.jsonfmt", "JsonHandler"),
    ("id_translate.formats.jsonfmt", "ArbHandler"),
    ("id_translate.formats.yamlfmt", "YamlHandler"),
    ("id_translate.formats.po", "PoHandler"),
    ("id_translate.formats.androidxml", "AndroidXmlHandler"),
    ("id_translate.formats.ooxml", "DocxHandler"),
    ("id_translate.formats.ooxml", "PptxHandler"),
    ("id_translate.formats.ooxml", "XlsxHandler"),
    ("id_translate.formats.html", "HtmlHandler"),
    ("id_translate.formats.epub", "EpubHandler"),
    ("id_translate.formats.pdf", "PdfHandler"),
]

_cache: list[FormatHandler] | None = None


def all_handlers() -> list[FormatHandler]:
    global _cache
    if _cache is None:
        handlers = []
        for mod, cls in _SPECS:
            try:
                module = importlib.import_module(mod)
            except ModuleNotFoundError as exc:
                if exc.name and exc.name.startswith("id_translate"):
                    continue  # handler not implemented yet
                raise
            handlers.append(getattr(module, cls)())
        _cache = handlers
    return _cache


def get_handler(name: str) -> FormatHandler:
    for h in all_handlers():
        if h.name == name:
            return h
    raise UnsupportedFormatError(f"unknown format: {name!r}")


def handler_for_path(path: Path, fmt: str | None = None) -> FormatHandler:
    if fmt:
        return get_handler(fmt)
    ext = Path(path).suffix.lower()
    candidates = [h for h in all_handlers() if ext in h.extensions]
    for h in candidates:
        if h.sniff(Path(path)):
            return h
    supported = sorted({e for h in all_handlers() for e in h.extensions})
    raise UnsupportedFormatError(
        f"unsupported file type {ext or '(none)'!r} for {Path(path).name}. Supported: {' '.join(supported)}"
    )
