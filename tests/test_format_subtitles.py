"""Round-trip and QA tests for SRT and WebVTT subtitles."""

from helpers import FIXTURES, assert_reextract_matches, expected_pseudo, pseudo, run_roundtrip

from id_translate.qa import run_qa


def test_srt_identity_and_longer(tmp_path):
    src = FIXTURES / "sample.srt"
    h, segs, out, _ = run_roundtrip(src, tmp_path)
    assert out.read_bytes() == src.read_bytes()
    assert len(segs) == 3
    assert segs[2].status == "skip"  # "100%" has no letters
    assert "<i>" not in segs[1].text and "{\\an8}" not in segs[1].text
    assert "{name}" not in segs[0].text

    h, segs, out2, _ = run_roundtrip(src, tmp_path, translate=lambda s: pseudo(s.text), name="long")
    text = out2.read_text(encoding="utf-8")
    assert "00:00:01,000 --> 00:00:04,500" in text
    assert "00:00:05,000 --> 00:00:08,200" in text
    assert "{\\an8}" in text and "<i>" in text and "{name}" in text and "https://example.com" in text
    assert_reextract_matches(h, segs, out2, expected_pseudo)


def test_srt_blank_line_in_translation_is_collapsed(tmp_path):
    src = FIXTURES / "sample.srt"
    h, segs, out, _ = run_roundtrip(
        src, tmp_path, translate=lambda s: s.text.replace("\n", "\n\n")
    )
    assert h.unit_count(out) == (3, "cue")


def test_vtt_identity_and_longer(tmp_path):
    src = FIXTURES / "sample.vtt"
    h, segs, out, _ = run_roundtrip(src, tmp_path)
    assert out.read_bytes() == src.read_bytes()
    assert len(segs) == 2
    assert "<v Host>" not in segs[0].text and "<00:06.500>" not in segs[1].text

    h, segs, out2, _ = run_roundtrip(src, tmp_path, translate=lambda s: pseudo(s.text), name="long")
    text = out2.read_text(encoding="utf-8")
    assert text.startswith("WEBVTT - Sample captions\n")
    assert "This comment block must not be translated." in text
    assert "color: white;" in text
    assert "align:start position:10%" in text
    assert "<v Host>" in text and "<00:06.500>" in text and "{course}" in text
    assert_reextract_matches(h, segs, out2, expected_pseudo)


def test_subtitle_qa_checks_timings_and_reading_speed(tmp_path):
    src = FIXTURES / "sample.srt"
    tgt = tmp_path / "fast.srt"
    tgt.write_text(
        "1\n00:00:01,000 --> 00:00:04,500\n"
        "Ini baris pertama yang sangat panjang sekali melebihi batas empat puluh dua karakter.\n"
        "Baris kedua.\nBaris ketiga.\n\n"
        "2\n00:00:05,000 --> 00:00:08,200\n<i>Catatan:</i> {\\an8}Kunjungi https://example.com.\n\n"
        "3\n00:00:09,000 --> 00:00:11,000\n100%\n",
        encoding="utf-8",
    )
    res = run_qa(src, tgt)
    assert any("melebihi 2 baris" in w for w in res.warnings)
    assert any("melebihi 42 karakter" in w for w in res.warnings)
    assert any("kecepatan baca" in w for w in res.warnings)
