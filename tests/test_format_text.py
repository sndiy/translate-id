"""Round-trip tests for Markdown and plain text."""

import codecs

from helpers import FIXTURES, assert_reextract_matches, expected_pseudo, pseudo, restored, run_roundtrip


def test_markdown_identity_roundtrip_is_byte_identical(tmp_path):
    src = FIXTURES / "sample.md"
    _, segs, out, res = run_roundtrip(src, tmp_path)
    assert out.read_bytes() == src.read_bytes()
    assert res.translated == 0 and res.unchanged_source > 10


def test_markdown_longer_text_keeps_structure(tmp_path):
    src = FIXTURES / "sample.md"
    h, segs, out, _ = run_roundtrip(src, tmp_path, translate=lambda s: pseudo(s.text))
    text = out.read_text(encoding="utf-8")
    # untouched regions stay byte-identical
    for keep in [
        "---\ntitle: Panduan Contoh\ntags: [demo, fixture]\n---",
        '```bash\necho "do not translate this code"\n```',
        "    indented code is never translated",
        "[ref]: https://example.com/ref",
        "<!-- a comment that must stay -->",
        "|---|:---:|",
        "===================",
        "](https://example.com/releases \"Releases\")",
        "`setup --quiet`",
        "{app_name}",
        "https://example.com/docs",
        "support@example.com",
        "<https://example.com/faq>",
        "&copy;",
        "<kbd>Ctrl</kbd>",
    ]:
        assert keep in text, keep
    # list markers, quote prefixes, and continuation indentation survive
    assert "\n1. Ïd Download" in text and "\n2. Ïd Run" in text
    assert "\n   This line continues the second item." in text
    assert "\n> Ïd Note: keep your API key secret.\n> Never share it with %s" in text
    assert "\n- [ ] Ïd Check the box" in text
    assert "# Ïd Getting Started with {app_name}" in text
    assert text.count("|") == (FIXTURES / "sample.md").read_text(encoding="utf-8").count("|")

    def expected(seg):
        e = expected_pseudo(seg)
        if seg.style.get("single_line"):
            e = " ".join(e.split("\n"))
        return e

    assert_reextract_matches(h, segs, out, expected)


def test_markdown_pipe_in_table_translation_is_escaped(tmp_path):
    src = tmp_path / "t.md"
    src.write_text("| A | B |\n|---|---|\n| one | two |\n", encoding="utf-8")
    _, segs, out, _ = run_roundtrip(src, tmp_path, translate=lambda s: s.text + " | x")
    rows = out.read_text(encoding="utf-8").splitlines()
    assert rows[2] == "| one \\| x | two \\| x |"


def test_markdown_placeholders_masked_in_segments():
    from id_translate.pipeline import extract_file

    _, segs, _ = extract_file(FIXTURES / "sample.md")
    by_text = {restored(s): s for s in segs}
    s = by_text["Getting Started with {app_name}"]
    assert s.text == "Getting Started with ⟦P1⟧"
    note = next(s for s in segs if "API key" in s.text)
    assert "%s" not in note.text and "%s" in note.protect.values()


def test_plaintext_identity_and_longer(tmp_path):
    src = FIXTURES / "sample.txt"
    h, segs, out, _ = run_roundtrip(src, tmp_path)
    assert out.read_bytes() == src.read_bytes()
    assert [s.status for s in segs][-1] == "skip"  # "12345" has no letters
    h, segs, out2, _ = run_roundtrip(src, tmp_path, translate=lambda s: pseudo(s.text), name="long")
    text = out2.read_text(encoding="utf-8")
    assert "\n    and keeps its indentation" in text and "{user}" in text and "\n12345\n" in text
    assert_reextract_matches(h, segs, out2, expected_pseudo)


def test_plaintext_preserves_bom_crlf_and_encoding(tmp_path):
    src = tmp_path / "w.txt"
    src.write_bytes(codecs.BOM_UTF8 + b"First line here.\r\nSecond line.\r\n\r\nNext para.\r\n")
    _, segs, out, _ = run_roundtrip(src, tmp_path, translate=lambda s: s.text.replace("line", "baris"))
    data = out.read_bytes()
    assert data.startswith(codecs.BOM_UTF8)
    assert data == codecs.BOM_UTF8 + b"First baris here.\r\nSecond baris.\r\n\r\nNext para.\r\n"

    src16 = tmp_path / "u16.txt"
    src16.write_bytes(codecs.BOM_UTF16_LE + "Hello world.\n".encode("utf-16-le"))
    _, _, out16, _ = run_roundtrip(src16, tmp_path, translate=lambda s: "Halo dunia.", name="u16out")
    assert out16.read_bytes() == codecs.BOM_UTF16_LE + "Halo dunia.\n".encode("utf-16-le")
