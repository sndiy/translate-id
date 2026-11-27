"""YAML handler using PyYAML's node tree for in-place scalar value replacement.

Translated: string scalar values only (never keys, numbers, booleans, nulls, or comments).
Preserves comments, key order, and untouched sections byte-for-byte.
"""

from __future__ import annotations

import json
from pathlib import Path

from id_translate.errors import InputError
from id_translate.formats.textdoc import InPlaceTextHandler, TextDoc, read_text_doc
from id_translate.protect import DEFAULT_OPTIONS, has_translatable_text, mask
from id_translate.segments import Segment


def _yaml_skeleton(obj):
    if isinstance(obj, dict):
        return {k: _yaml_skeleton(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_yaml_skeleton(v) for v in obj]
    return type(obj).__name__


class YamlHandler(InPlaceTextHandler):
    name = "yaml"
    extensions = (".yaml", ".yml")
    requires = ("yaml",)
    extra = "yaml"

    def parse(self, doc: TextDoc, path: Path) -> list[Segment]:
        import yaml

        try:
            root = yaml.compose(doc.text, Loader=yaml.SafeLoader)
        except yaml.YAMLError as exc:
            raise InputError(f"invalid YAML: {exc}") from exc
        segs: list[Segment] = []
        if root is None:
            return segs

        def walk(node, key_path: tuple[str | int, ...]) -> None:
            if isinstance(node, yaml.MappingNode):
                for k_node, v_node in node.value:
                    key = k_node.value if isinstance(k_node, yaml.ScalarNode) else "?"
                    walk(v_node, (*key_path, str(key)))
            elif isinstance(node, yaml.SequenceNode):
                for idx, item in enumerate(node.value):
                    walk(item, (*key_path, idx))
            elif isinstance(node, yaml.ScalarNode) and node.tag == "tag:yaml.org,2002:str":
                s = node.start_mark.index
                e = node.end_mark.index
                # Trim trailing newline/comment whitespace PyYAML sometimes includes on block scalars
                if node.style in ("|", ">"):
                    while e > s and doc.text[e - 1] in "\r\n":
                        e -= 1
                val = node.value
                masked, protect = mask(val, DEFAULT_OPTIONS)
                segs.append(
                    Segment(
                        id=f"yml{len(segs) + 1:04d}",
                        type="string",
                        text=masked,
                        style={
                            "key": ".".join(str(p) for p in key_path),
                            "yaml_style": node.style or "plain",
                            "column": node.start_mark.column,
                        },
                        loc={"start": s, "end": e, "key": ".".join(str(p) for p in key_path)},
                        protect=protect,
                        status="pending" if has_translatable_text(masked) else "skip",
                    )
                )

        walk(root, ())
        return segs

    def encode(self, seg: Segment, final_text: str, doc: TextDoc) -> str:
        # JSON double-quoted string is always valid YAML 1.2 and safe with colons, #, quotes, newlines.
        return json.dumps(final_text, ensure_ascii=False)

    def extra_qa(self, source: Path, target: Path) -> tuple[list[str], list[str], list[str]]:
        import yaml

        try:
            s_obj = yaml.safe_load(read_text_doc(source).text)
            t_obj = yaml.safe_load(read_text_doc(target).text)
        except yaml.YAMLError as exc:
            return [f"YAML hasil tidak valid: {exc}"], [], []
        if _yaml_skeleton(s_obj) != _yaml_skeleton(t_obj):
            return ["Struktur kunci/tipe YAML berubah antara sumber dan hasil."], [], []
        return [], [], ["Struktur kunci YAML identik dengan sumber."]
