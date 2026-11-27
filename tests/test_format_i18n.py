"""Round-trip tests for JSON, ARB, YAML, PO, and Android strings.xml."""

import json
import xml.etree.ElementTree as ET

import yaml
from helpers import FIXTURES, assert_reextract_matches, expected_pseudo, pseudo, run_roundtrip

from id_translate.qa import run_qa


def test_json_identity_and_longer(tmp_path):
    src = FIXTURES / "sample.json"
    h, segs, out, _ = run_roundtrip(src, tmp_path)
    assert out.read_bytes() == src.read_bytes()
    assert [s.status for s in segs][-1] == "skip"  # "42"
    assert "{app_name}" not in segs[0].text and "{{user}}" not in segs[1].text

    h, segs, out2, _ = run_roundtrip(src, tmp_path, translate=lambda s: pseudo(s.text), name="long")
    data = json.loads(out2.read_text(encoding="utf-8"))
    assert data["version"] == 2 and data["enabled"] is True
    assert "{app_name}" in data["app"]["title"]
    assert "{{user}}" in data["app"]["greeting"] and "https://example.com" in data["app"]["greeting"]
    assert data["app"]["items"][2] == "42"
    assert_reextract_matches(h, segs, out2, expected_pseudo)
    assert run_qa(src, out2).errors == []


def test_arb_skips_metadata_and_sets_locale(tmp_path):
    src = FIXTURES / "sample.arb"
    h, segs, out, _ = run_roundtrip(src, tmp_path)
    assert out.read_bytes() == src.read_bytes()
    assert len(segs) == 2
    assert segs[0].style["context"] == "Greeting on the home screen"
    assert "plural" not in segs[1].text

    h, segs, out2, _ = run_roundtrip(
        src, tmp_path, translate=lambda s: pseudo(s.text), set_lang=True, name="long"
    )
    data = json.loads(out2.read_text(encoding="utf-8"))
    assert data["@@locale"] == "id"
    assert data["@welcome"]["description"] == "Greeting on the home screen"
    assert "{name}" in data["welcome"]
    assert "{count, plural," in data["itemCount"]
    assert_reextract_matches(h, segs, out2, expected_pseudo)


def test_yaml_identity_and_longer(tmp_path):
    src = FIXTURES / "sample.yaml"
    h, segs, out, _ = run_roundtrip(src, tmp_path)
    assert out.read_bytes() == src.read_bytes()
    assert len(segs) == 4

    h, segs, out2, _ = run_roundtrip(
        src, tmp_path, translate=lambda s: pseudo(s.text) + ": # safe", name="long"
    )
    raw = out2.read_text(encoding="utf-8")
    assert raw.startswith("# Application messages\n")
    data = yaml.safe_load(raw)
    assert data["app"]["count"] == 10 and data["app"]["enabled"] is True
    assert "{name}" in data["app"]["description"]
    assert "https://example.com" in data["app"]["description"]
    assert run_qa(src, out2).errors == []


def test_po_identity_longer_and_header_lang(tmp_path):
    src = FIXTURES / "sample.po"
    h, segs, out, _ = run_roundtrip(src, tmp_path)
    assert out.read_bytes() == src.read_bytes()
    assert len(segs) == 4
    assert segs[1].style["context"] == "button"
    assert "%(name)s" not in segs[0].text and "%d" not in segs[2].text

    h, segs, out2, _ = run_roundtrip(
        src, tmp_path, translate=lambda s: pseudo(s.text), set_lang=True, name="long"
    )
    text = out2.read_text(encoding="utf-8")
    assert "Language: id\\n" in text
    assert "Plural-Forms: nplurals=1; plural=0;\\n" in text
    assert 'msgctxt "button"' in text
    assert "%(name)s" in text and "%d" in text
    qa_text = h.qa_text(out2)
    assert "Ïd Welcome, %(name)s!" in qa_text
    assert run_qa(src, out2).errors == []


def test_android_xml_identity_longer_and_escaping(tmp_path):
    src = FIXTURES / "strings.xml"
    h, segs, out, _ = run_roundtrip(src, tmp_path)
    assert out.read_bytes() == src.read_bytes()
    assert all(s.style.get("name") != "app_id" for s in segs)
    assert len(segs) == 6  # 2 strings + 2 array items + 2 plural items

    h, segs, out2, _ = run_roundtrip(
        src, tmp_path, translate=lambda s: "It's " + pseudo(s.text), name="long"
    )
    raw = out2.read_text(encoding="utf-8")
    assert "com.example.demo" in raw
    assert "<!-- Untranslatable app id -->" in raw
    assert "It\\'s " in raw  # apostrophe escaped for Android
    assert "<b>%1$s</b>" in raw and '<xliff:g id="user">%s</xliff:g>' in raw
    assert "&amp;" in raw
    ET.fromstring(raw)  # valid XML
    assert run_qa(src, out2).errors == []
