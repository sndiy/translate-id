"""Round-trip and DRM tests for HTML and EPUB."""

import zipfile

from helpers import FIXTURES, assert_reextract_matches, cli, expected_pseudo, pseudo, run_roundtrip

from id_translate.qa import run_qa


def _make_epub(path):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?><container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        z.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0" encoding="utf-8"?>'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            "<dc:title>Demo Book</dc:title><dc:language>en</dc:language>"
            "</metadata>"
            '<manifest><item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/></manifest>'
            '<spine><itemref idref="c1"/></spine></package>',
        )
        z.writestr(
            "OEBPS/ch1.xhtml",
            '<?xml version="1.0" encoding="utf-8"?>'
            '<html xmlns="http://www.w3.org/1999/xhtml" lang="en">'
            "<head><title>Chapter One</title></head>"
            "<body><h1>Introduction</h1>"
            "<p>Welcome {reader}, read https://example.com for updates.</p>"
            "<pre>code_stays_here()</pre></body></html>",
        )
    return path


def test_html_identity_longer_and_lang(tmp_path):
    src = FIXTURES / "sample.html"
    h, segs, out, _ = run_roundtrip(src, tmp_path)
    assert out.read_bytes() == src.read_bytes()
    assert all("do not translate" not in s.text for s in segs)
    assert all("id-translate" not in s.text for s in segs)
    assert any(s.type == "attr" and s.style["tag"] == "img@alt" for s in segs)
    assert any(s.type == "attr" and s.style["tag"] == "meta@content" for s in segs)

    h, segs, out2, _ = run_roundtrip(
        src, tmp_path, translate=lambda s: pseudo(s.text), set_lang=True, name="long"
    )
    text = out2.read_text(encoding="utf-8")
    assert '<html lang="id">' in text
    assert 'href="https://example.com/docs"' in text
    assert "<code>id-translate</code>" in text
    assert 'const msg = "do not translate";' in text
    assert "{app_name}" in text
    assert_reextract_matches(h, segs, out2, expected_pseudo)
    assert run_qa(src, out2).errors == []


def test_epub_identity_longer_mimetype_and_lang(tmp_path):
    src = _make_epub(tmp_path / "demo.epub")
    h, segs, out, _ = run_roundtrip(src, tmp_path)
    assert out.read_bytes() == src.read_bytes()
    assert h.unit_count(src) == (1, "dokumen XHTML")
    assert all("code_stays_here" not in s.text for s in segs)

    h, segs, out2, _ = run_roundtrip(
        src, tmp_path, translate=lambda s: pseudo(s.text), set_lang=True, name="long"
    )
    with zipfile.ZipFile(out2) as z:
        infos = z.infolist()
        assert infos[0].filename == "mimetype" and infos[0].compress_type == zipfile.ZIP_STORED
        opf = z.read("OEBPS/content.opf").decode("utf-8")
        assert "<dc:language>id</dc:language>" in opf
        ch1 = z.read("OEBPS/ch1.xhtml").decode("utf-8")
        assert 'lang="id"' in ch1
        assert "{reader}" in ch1 and "https://example.com" in ch1
        assert "<pre>code_stays_here()</pre>" in ch1
    assert_reextract_matches(h, segs, out2, expected_pseudo)
    assert run_qa(src, out2).errors == []


def test_epub_drm_refused_via_cli(tmp_path):
    p = tmp_path / "drm.epub"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr(
            "META-INF/encryption.xml",
            '<encryption><EncryptedData><EncryptionMethod '
            'Algorithm="http://www.w3.org/2001/04/xmlenc#aes128-cbc"/></EncryptedData></encryption>',
        )
    r = cli("inspect", p)
    assert r.returncode == 4 and "encrypted" in r.stderr.lower()
