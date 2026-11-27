"""Pluggable PDF engine abstraction.

The segment contract and ``PdfHandler`` depend only on this interface so the underlying PDF
engine (default: optional PyMuPDF extra ``[pdf]``, AGPL-3.0 / Artifex commercial) can be
swapped without changing segment files or CLI behavior.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from id_translate.errors import DependencyMissingError


@dataclass
class PdfBlock:
    page: int  # 1-based
    block_no: int
    bbox: tuple[float, float, float, float]
    text: str
    font_size: float
    color_rgb: tuple[float, float, float]
    bold: bool = False
    italic: bool = False
    serif: bool = False


@dataclass
class PdfEdit:
    page: int  # 1-based
    segment_id: str
    bbox: tuple[float, float, float, float]
    text: str
    font_size: float
    color_rgb: tuple[float, float, float]
    bold: bool = False
    italic: bool = False
    serif: bool = False


@dataclass
class PdfRenderResult:
    data: bytes
    flags: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class PdfEngine(ABC):
    name: str = ""

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def check_access(self, path: Path) -> None:
        """Raise EncryptedInputError if the PDF is encrypted or requires a password."""
        raise NotImplementedError

    @abstractmethod
    def inspect(self, path: Path) -> dict:
        raise NotImplementedError

    @abstractmethod
    def page_count(self, path: Path) -> int:
        raise NotImplementedError

    @abstractmethod
    def extract_blocks(self, path: Path) -> list[PdfBlock]:
        raise NotImplementedError

    @abstractmethod
    def extract_plain_text(self, path: Path) -> str:
        raise NotImplementedError

    @abstractmethod
    def apply_edits(self, path: Path, edits: list[PdfEdit]) -> PdfRenderResult:
        raise NotImplementedError

    @abstractmethod
    def side_by_side_png(self, source: Path, translated: Path, page_index: int, zoom: float = 1.5) -> bytes:
        raise NotImplementedError


_ENGINES: dict[str, Callable[[], PdfEngine]] = {}


def register_engine(name: str, factory: Callable[[], PdfEngine]) -> None:
    _ENGINES[name] = factory


def get_engine(name: str | None = None) -> PdfEngine:
    chosen = name or os.environ.get("ID_TRANSLATE_PDF_ENGINE") or "pymupdf"
    if chosen not in _ENGINES:
        if chosen == "pymupdf":
            from id_translate.pdf.pymupdf_engine import PyMuPdfEngine

            register_engine("pymupdf", PyMuPdfEngine)
        else:
            raise DependencyMissingError(f"unknown PDF engine: {chosen!r}")
    engine = _ENGINES[chosen]()
    if not engine.is_available():
        raise DependencyMissingError(
            f"PDF engine {chosen!r} is not installed. Install optional extra: pip install 'id-translate[pdf]' "
            "(note: PyMuPDF is dual-licensed AGPL-3.0 or Artifex commercial)."
        )
    return engine
