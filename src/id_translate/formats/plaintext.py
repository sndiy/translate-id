"""Plain text handler: one segment per paragraph (blocks separated by blank lines)."""

from __future__ import annotations

from pathlib import Path

from id_translate.formats.textdoc import InPlaceTextHandler, TextDoc, line_spans
from id_translate.protect import has_translatable_text, mask
from id_translate.segments import Segment


class PlainTextHandler(InPlaceTextHandler):
    name = "text"
    extensions = (".txt", ".text")

    def parse(self, doc: TextDoc, path: Path) -> list[Segment]:
        text = doc.text
        spans = line_spans(text)
        segs: list[Segment] = []
        i, n = 0, len(spans)
        while i < n:
            s, e, _ = spans[i]
            line = text[s:e]
            if not line.strip():
                i += 1
                continue
            lead = len(line) - len(line.lstrip())
            start = s + lead
            parts = [text[start:e]]
            end = e
            cont_prefix = ""
            j = i + 1
            first_cont = True
            while j < n:
                s2, e2, _ = spans[j]
                l2 = text[s2:e2]
                if not l2.strip():
                    break
                lead2 = len(l2) - len(l2.lstrip())
                if first_cont:
                    cont_prefix = l2[:lead2]
                    first_cont = False
                parts.append(l2[lead2:])
                end = e2
                j += 1
            raw = "\n".join(parts)
            masked, protect = mask(raw)
            segs.append(
                Segment(
                    id=f"t{len(segs) + 1:04d}",
                    type="paragraph",
                    text=masked,
                    style={"cont_prefix": cont_prefix},
                    loc={"start": start, "end": end},
                    protect=protect,
                    status="pending" if has_translatable_text(masked) else "skip",
                )
            )
            i = j
        return segs
