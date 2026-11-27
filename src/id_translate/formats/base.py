"""Format handler interface.

A handler turns a source file into segments (``extract``) and renders a NEW byte string
with translations applied (``render``). Handlers never write files; the pipeline writes
outputs with exclusive-create so the no-overwrite invariant lives in one place.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path

from id_translate.errors import DependencyMissingError
from id_translate.protect import restore, strip_tokens
from id_translate.segments import Segment


@dataclass
class ApplyOptions:
    set_lang: bool = True  # mark output language as Indonesian where the format supports it
    lang: str = "id"


@dataclass
class RenderReport:
    flags: list[dict] = field(default_factory=list)  # items needing manual review
    notes: list[str] = field(default_factory=list)


class FormatHandler:
    name: str = ""
    extensions: tuple[str, ...] = ()
    stability: str = "beta"  # stable | beta | planned
    requires: tuple[str, ...] = ()  # importable module names
    extra: str | None = None  # pip extra providing the requirements

    def missing_dependencies(self) -> list[str]:
        return [m for m in self.requires if importlib.util.find_spec(m) is None]

    def ensure_available(self) -> None:
        missing = self.missing_dependencies()
        if missing:
            hint = f"pip install 'id-translate[{self.extra}]'" if self.extra else "pip install " + " ".join(missing)
            raise DependencyMissingError(
                f"format {self.name!r} needs missing module(s): {', '.join(missing)}. Install with: {hint}"
            )

    def sniff(self, path: Path) -> bool:
        """Return True if this handler can process ``path`` (used to disambiguate extensions)."""
        return True

    def check_access(self, path: Path) -> None:
        """Raise EncryptedInputError for encrypted/DRM inputs. Default: nothing to check."""

    def inspect_info(self, path: Path) -> dict:
        """Extra format-specific facts for ``inspect`` (pages, scan verdict, ...)."""
        return {}

    def extract(self, path: Path) -> list[Segment]:
        raise NotImplementedError

    def render(
        self, path: Path, segments: list[Segment], translations: dict[str, str], options: ApplyOptions
    ) -> tuple[bytes, RenderReport]:
        """Return output bytes. ``translations`` maps id -> masked translated text (tokens validated)."""
        raise NotImplementedError

    # --- QA hooks -------------------------------------------------------------------------
    def qa_text(self, path: Path) -> str:
        """Plain text used by QA for this file (source or translated output)."""
        return "\n".join(strip_tokens(restore(s.text, s.protect)) for s in self.extract(path))

    def unit_count(self, path: Path) -> tuple[int, str] | None:
        """Structural unit count that must match between source and output (pages, cues, ...)."""
        return None

    def extra_qa(self, source: Path, target: Path) -> tuple[list[str], list[str], list[str]]:
        """Format-specific checks. Returns (errors, warnings, notes)."""
        return [], [], []
