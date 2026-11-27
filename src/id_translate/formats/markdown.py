"""Markdown handler (CommonMark-ish line parser, edited in place).

Translated: paragraphs, headings, list items, blockquote text, table cells, link/image text.
Never touched: front matter, fenced/indented code, HTML comments, link reference definitions,
inline code, link destinations, autolinks, HTML tags, heading ids ``{#id}``.
"""

from __future__ import annotations

import re
from pathlib import Path

from id_translate.formats.textdoc import InPlaceTextHandler, TextDoc, line_spans
from id_translate.protect import MARKUP_OPTIONS, has_translatable_text, mask
from id_translate.segments import Segment

FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
ATX_RE = re.compile(r"^( {0,3}#{1,6})(?:[ \t]+(.*?))??(?:[ \t]+#+)?[ \t]*$")
HR_RE = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
SETEXT_RE = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
LIST_RE = re.compile(r"^([ \t]*)([-*+]|\d{1,9}[.)])([ \t]+)(\[[ xX]\][ \t]+)?")
QUOTE_RE = re.compile(r"^(?:[ \t]{0,3}>[ \t]?)+")
DELIM_CELL_RE = re.compile(r"^\s*:?-+:?\s*$")
REFDEF_RE = re.compile(r"^ {0,3}\[[^\]^][^\]]*\]:\s*\S")

INLINE_CODE_RE = re.compile(r"(`+)(?!`).+?(?<!`)\1(?!`)", re.S)
LINK_RE = re.compile(
    r"(!?\[)((?:[^\[\]]|\[[^\]]*\])*)(\]\((?:[^()\s]|\([^)]*\))*(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\))"
)
REFLINK_RE = re.compile(r"(!?\[)((?:[^\[\]]|\[[^\]]*\])+)(\]\[[^\]]*\])")
FOOTNOTE_RE = re.compile(r"\[\^[^\]]+\](?::)?")
AUTOLINK_RE = re.compile(r"<(?:https?|ftp|mailto):[^>\s]+>|<[^>@\s]+@[^>\s]+>")
ENTITY_RE = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]*|#\d+|#x[0-9A-Fa-f]+);")
HEADING_ID_RE = re.compile(r"\{#[\w:.-]+\}")


def md_protected_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for m in INLINE_CODE_RE.finditer(text):
        spans.append(m.span())
    for rx in (LINK_RE, REFLINK_RE):
        for m in rx.finditer(text):
            spans.append(m.span(1))
            spans.append(m.span(3))
    for rx in (FOOTNOTE_RE, AUTOLINK_RE, ENTITY_RE, HEADING_ID_RE):
        spans += [m.span() for m in rx.finditer(text)]
    # drop spans contained in inline code
    code = [m.span() for m in INLINE_CODE_RE.finditer(text)]
    return [s for s in spans if s in code or not any(c0 <= s[0] and s[1] <= c1 for c0, c1 in code)]


def _quote_depth(prefix: str) -> int:
    return prefix.count(">")


class MarkdownHandler(InPlaceTextHandler):
    name = "markdown"
    extensions = (".md", ".markdown", ".mdown", ".mkd")

    def _make(self, segs: list[Segment], kind: str, text: str, start: int, end: int, style: dict) -> None:
        masked, protect = mask(text, MARKUP_OPTIONS, extra_spans=md_protected_spans(text))
        status = "pending" if has_translatable_text(masked) else "skip"
        segs.append(
            Segment(
                id=f"md{len(segs) + 1:04d}",
                type=kind,
                text=masked,
                style=style,
                loc={"start": start, "end": end},
                protect=protect,
                status=status,
            )
        )

    def parse(self, doc: TextDoc, path: Path) -> list[Segment]:
        text = doc.text
        spans = line_spans(text)
        lines = [text[s:e] for s, e, _ in spans]
        n = len(lines)
        segs: list[Segment] = []
        i = 0
        # front matter
        if n and lines[0].strip() == "---":
            for j in range(1, n):
                if lines[j].strip() in ("---", "..."):
                    i = j + 1
                    break
        in_list = False

        def is_table_start(k: int, qdepth: int) -> bool:
            if k + 1 >= n or "|" not in lines[k]:
                return False
            nxt = lines[k + 1]
            qm = QUOTE_RE.match(nxt)
            if _quote_depth(qm.group(0) if qm else "") != qdepth:
                return False
            body = nxt[len(qm.group(0)) :] if qm else nxt
            if "|" not in body and "-" not in body:
                return False
            cells = [c for c in self._split_cells(body)]
            return bool(cells) and all(DELIM_CELL_RE.match(body[a:b]) for a, b in cells) and "|" in body

        def starts_block(body: str) -> bool:
            return bool(
                FENCE_RE.match(body)
                or ATX_RE.match(body)
                or HR_RE.match(body)
                or LIST_RE.match(body)
                or body.lstrip().startswith("<!--")
            )

        while i < n:
            s, e, _ = spans[i]
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            fm = FENCE_RE.match(line)
            if fm:
                fence = fm.group(1)
                j = i + 1
                while j < n and not re.match(rf"^ {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*$", lines[j]):
                    j += 1
                i = j + 1
                continue
            if line.lstrip().startswith("<!--"):
                j = i
                while j < n and "-->" not in lines[j]:
                    j += 1
                i = j + 1
                continue
            if REFDEF_RE.match(line) or HR_RE.match(line):
                i += 1
                continue
            if (line.startswith("    ") or line.startswith("\t")) and not in_list:
                while i < n and (not lines[i].strip() or lines[i].startswith(("    ", "\t"))):
                    i += 1
                continue
            qm = QUOTE_RE.match(line)
            qp = qm.group(0) if qm else ""
            qdepth = _quote_depth(qp)
            body = line[len(qp) :]
            bstart = s + len(qp)
            if not body.strip():
                i += 1
                continue
            if is_table_start(i, qdepth):
                j = i
                row = 0
                while j < n and lines[j].strip() and "|" in lines[j]:
                    rq = QUOTE_RE.match(lines[j])
                    rp = rq.group(0) if rq else ""
                    rbody = lines[j][len(rp) :]
                    rstart = spans[j][0] + len(rp)
                    if j != i + 1:
                        for col, (a, b) in enumerate(self._split_cells(rbody)):
                            cell = rbody[a:b]
                            lead = len(cell) - len(cell.lstrip())
                            content = cell.strip()
                            if content:
                                cs = rstart + a + lead
                                self._make(
                                    segs, "table_cell", content, cs, cs + len(content),
                                    {"row": row, "col": col, "single_line": True, "escape_pipe": True},
                                )
                        row += 1
                    j += 1
                i = j
                continue
            hm = ATX_RE.match(body)
            if hm:
                if hm.group(2):
                    cs = bstart + hm.start(2)
                    self._make(segs, "heading", hm.group(2), cs, bstart + hm.end(2),
                               {"level": hm.group(1).strip().count("#"), "single_line": True})
                i += 1
                continue
            lm = LIST_RE.match(body)
            if lm:
                in_list = True
                kind = "list_item"
                cstart = bstart + lm.end()
                default_prefix = qp + " " * lm.end()
            else:
                if not line.startswith((" ", "\t")):
                    in_list = False
                kind = "paragraph"
                lead = len(body) - len(body.lstrip(" \t"))
                cstart = bstart + lead
                default_prefix = qp + body[:lead]
            parts = [text[cstart:e]]
            end = e
            cont_prefix = None
            setext_level = 0
            j = i + 1
            while j < n:
                l2 = lines[j]
                if not l2.strip():
                    break
                q2 = QUOTE_RE.match(l2)
                qp2 = q2.group(0) if q2 else ""
                if _quote_depth(qp2) != qdepth:
                    break
                b2 = l2[len(qp2) :]
                if kind == "paragraph" and SETEXT_RE.match(b2):
                    setext_level = 1 if b2.strip().startswith("=") else 2
                    j += 1
                    break
                if starts_block(b2) or is_table_start(j, qdepth):
                    break
                lead2 = len(b2) - len(b2.lstrip(" \t"))
                if cont_prefix is None:
                    cont_prefix = l2[: len(qp2) + lead2]
                parts.append(b2[lead2:])
                end = spans[j][1]
                j += 1
            style: dict = {"cont_prefix": cont_prefix if cont_prefix is not None else default_prefix}
            if setext_level:
                kind = "heading"
                style = {"level": setext_level, "cont_prefix": style["cont_prefix"]}
            self._make(segs, kind, "\n".join(parts), cstart, end, style)
            i = j
        return segs

    @staticmethod
    def _split_cells(body: str) -> list[tuple[int, int]]:
        """Return (start, end) of cells between unescaped pipes (outer pipes optional)."""
        pipes = [m.start() for m in re.finditer(r"(?<!\\)\|", body)]
        bounds = [-1, *pipes, len(body)]
        cells = [(a + 1, b) for a, b in zip(bounds, bounds[1:])]
        if body.lstrip().startswith("|"):
            cells = cells[1:]
        if body.rstrip().endswith("|") and not body.rstrip().endswith("\\|"):
            cells = cells[:-1]
        return cells

    def encode(self, seg: Segment, final_text: str, doc: TextDoc) -> str:
        if seg.style.get("single_line"):
            final_text = re.sub(r"\s*\n\s*", " ", final_text)
        if seg.style.get("escape_pipe"):
            final_text = re.sub(r"(?<!\\)\|", r"\\|", final_text)
        return super().encode(seg, final_text, doc)
