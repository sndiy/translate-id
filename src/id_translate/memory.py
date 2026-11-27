"""Translation memory (append-only JSONL) and token-budget batching."""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path

from id_translate.safety import append_jsonl
from id_translate.segments import Segment

PER_SEGMENT_OVERHEAD = 12  # JSON scaffolding + id, rough
CHARS_PER_TOKEN = 4.0  # rough heuristic for Latin-script text; documented as an estimate
OUTPUT_RATIO = 1.25  # Indonesian output tends to be longer than English input


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / CHARS_PER_TOKEN))


def normalize_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


class TranslationMemory:
    """Exact-match memory keyed by the masked source text. Stored as append-only JSONL."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else None
        self._mem: dict[str, str] = {}
        if self.path and self.path.is_file():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    d = json.loads(line)
                    self._mem[normalize_key(d["src"])] = d["tgt"]

    def __len__(self) -> int:
        return len(self._mem)

    def get(self, src: str) -> str | None:
        return self._mem.get(normalize_key(src))

    def add_many(self, pairs: list[tuple[str, str]]) -> int:
        added = 0
        for src, tgt in pairs:
            key = normalize_key(src)
            if self._mem.get(key) == tgt:
                continue
            self._mem[key] = tgt
            if self.path:
                append_jsonl(self.path, {"src": src, "tgt": tgt, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")})
            added += 1
        return added


@dataclass
class BatchPlan:
    batches: list[list[Segment]]
    tm_hits: dict[str, str]
    already_done: int
    duplicates: int
    pending_total: int

    @property
    def input_tokens(self) -> int:
        return sum(estimate_tokens(s.text) + PER_SEGMENT_OVERHEAD for b in self.batches for s in b)

    @property
    def output_tokens(self) -> int:
        return math.ceil(sum(estimate_tokens(s.text) for b in self.batches for s in b) * OUTPUT_RATIO)


def plan_batches(
    segments: list[Segment],
    done: dict[str, str],
    tm: TranslationMemory | None,
    max_tokens: int,
) -> BatchPlan:
    """Pending segments minus already translated, minus TM hits, deduplicated, split by budget."""
    pending = [s for s in segments if s.status == "pending"]
    todo: list[Segment] = []
    tm_hits: dict[str, str] = {}
    seen_text: set[str] = set()
    already = dups = 0
    for s in pending:
        if s.id in done:
            already += 1
            continue
        hit = tm.get(s.text) if tm else None
        if hit is not None:
            tm_hits[s.id] = hit
            continue
        key = normalize_key(s.text)
        if key in seen_text:
            dups += 1  # apply() propagates the translation to identical source texts
            continue
        seen_text.add(key)
        todo.append(s)
    batches: list[list[Segment]] = []
    cur: list[Segment] = []
    cur_tokens = 0
    for s in todo:
        cost = estimate_tokens(s.text) + PER_SEGMENT_OVERHEAD
        if cur and cur_tokens + cost > max_tokens:
            batches.append(cur)
            cur, cur_tokens = [], 0
        cur.append(s)
        cur_tokens += cost
    if cur:
        batches.append(cur)
    return BatchPlan(batches, tm_hits, already, dups, len(pending))
