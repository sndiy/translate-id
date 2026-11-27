"""Safety invariants (PLAN rule 6): never overwrite, SHA-256 verification, refuse encrypted/DRM."""

import json
import re
import zipfile
from pathlib import Path

import pytest
from helpers import ROOT, cli, run_roundtrip

from id_translate.errors import EncryptedInputError, OverwriteRefusedError, SafetyError, ValidationError
from id_translate.formats.base import ApplyOptions
from id_translate.pipeline import apply_translations, extract_file, extract_to
from id_translate.safety import (
    check_epub_drm,
    make_result_dir,
    sha256_file,
    verify_result_dir,
    write_new_bytes,
)
from id_translate.segments import write_segments


@pytest.fixture
def md(tmp_path):
    p = tmp_path / "doc.md"
    p.write_text("# Title\n\nHello world, this is a test.\n", encoding="utf-8")
    return p


def test_write_new_bytes_never_overwrites(tmp_path):
    p = tmp_path / "a.txt"
    write_new_bytes(p, b"first")
    with pytest.raises(OverwriteRefusedError):
        write_new_bytes(p, b"second")
    assert p.read_bytes() == b"first"


def test_apply_refuses_existing_output_and_leaves_it_untouched(md, tmp_path):
    seg = tmp_path / "s.jsonl"
    segs, _ = extract_to(md, seg)
    out = tmp_path / "out.md"
    out.write_bytes(b"previous result")
    with pytest.raises(OverwriteRefusedError):
        apply_translations(md, seg, {s.id: s.text for s in segs}, out)
    assert out.read_bytes() == b"previous result"


def test_apply_refuses_writing_onto_source(md, tmp_path):
    seg = tmp_path / "s.jsonl"
    segs, _ = extract_to(md, seg)
    before = md.read_bytes()
    with pytest.raises(SafetyError):
        apply_translations(md, seg, {s.id: s.text for s in segs}, md)
    assert md.read_bytes() == before


def test_apply_refuses_when_source_changed_since_extract(md, tmp_path):
    seg = tmp_path / "s.jsonl"
    segs, _ = extract_to(md, seg)
    md.write_text("# Changed\n", encoding="utf-8")
    with pytest.raises(SafetyError, match="SHA-256"):
        apply_translations(md, seg, {s.id: s.text for s in segs}, tmp_path / "o.md")


def test_source_hash_unchanged_by_full_pipeline(md, tmp_path):
    before = sha256_file(md)
    run_roundtrip(md, tmp_path, translate=lambda s: s.text + " (id)")
    assert sha256_file(md) == before


def test_extract_refuses_to_overwrite_segments(md, tmp_path):
    seg = tmp_path / "s.jsonl"
    extract_to(md, seg)
    with pytest.raises(OverwriteRefusedError):
        extract_to(md, seg)


def test_write_segments_refuses_existing_meta(md, tmp_path):
    _, segs, meta = extract_file(md)
    (tmp_path / "s.meta.json").write_text("{}", encoding="utf-8")
    with pytest.raises(OverwriteRefusedError):
        write_segments(tmp_path / "s.jsonl", segs, meta)
    assert not (tmp_path / "s.jsonl").exists()


def test_result_dirs_unique_manifest_hash_and_verify(md, tmp_path):
    d1 = make_result_dir(md, tmp_path / "res")
    d2 = make_result_dir(md, tmp_path / "res")
    assert d1 != d2
    m = json.loads((d1 / "MANIFEST.json").read_text(encoding="utf-8"))
    assert m["source_sha256"] == sha256_file(md)
    assert verify_result_dir(d1)[0]
    md.write_text("tampered", encoding="utf-8")
    ok, msgs = verify_result_dir(d1)
    assert not ok and any("changed" in x for x in msgs)


def test_verify_detects_modified_output(md, tmp_path):
    r = cli("init", md, "--out-root", tmp_path / "res")
    assert r.returncode == 0, r.stderr
    res = Path(r.stdout.strip())
    assert cli("extract", md, "--result", res).returncode == 0
    segs = [json.loads(x) for x in (res / "work/segments.jsonl").read_text(encoding="utf-8").splitlines()]
    tr = res / "work/translations/t.jsonl"
    tr.parent.mkdir(parents=True)
    tr.write_text("".join(json.dumps({"id": s["id"], "text": s["text"] + " ID"}) + "\n" for s in segs), "utf-8")
    r = cli("apply", "--result", res)
    assert r.returncode == 0, r.stderr
    out = Path(json.loads(r.stdout)["output"])
    assert cli("verify", res).returncode == 0
    out.write_text("edited by someone", encoding="utf-8")
    r = cli("verify", res)
    assert r.returncode == 1 and "modified" in r.stdout


def test_second_apply_in_result_dir_creates_new_file(md, tmp_path):
    res = Path(cli("init", md, "--out-root", tmp_path / "res").stdout.strip())
    cli("extract", md, "--result", res)
    segs = [json.loads(x) for x in (res / "work/segments.jsonl").read_text(encoding="utf-8").splitlines()]
    tr = res / "work/translations/t.jsonl"
    tr.parent.mkdir(parents=True)
    tr.write_text("".join(json.dumps({"id": s["id"], "text": s["text"]}) + "\n" for s in segs), "utf-8")
    o1 = json.loads(cli("apply", "--result", res).stdout)["output"]
    first = Path(o1).read_bytes()
    o2 = json.loads(cli("apply", "--result", res).stdout)["output"]
    assert o1 != o2 and Path(o1).read_bytes() == first


def test_epub_with_drm_is_refused(tmp_path):
    p = tmp_path / "book.epub"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/encryption.xml",
                   '<encryption><EncryptedData><EncryptionMethod '
                   'Algorithm="http://www.w3.org/2001/04/xmlenc#aes128-cbc"/></EncryptedData></encryption>')
    with pytest.raises(EncryptedInputError):
        check_epub_drm(p)
    p2 = tmp_path / "rights.epub"
    with zipfile.ZipFile(p2, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/rights.xml", "<rights/>")
    with pytest.raises(EncryptedInputError):
        check_epub_drm(p2)


def test_epub_font_obfuscation_is_not_treated_as_drm(tmp_path):
    p = tmp_path / "fonts.epub"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/encryption.xml",
                   '<encryption><EncryptedData><EncryptionMethod '
                   'Algorithm="http://www.idpf.org/2008/embedding"/></EncryptedData></encryption>')
    check_epub_drm(p)  # no exception


def test_no_drm_removal_or_password_code_in_package():
    """Static guard: the package never calls decryption/authentication APIs."""
    forbidden = re.compile(r"\.authenticate\(|\bdecrypt\w*\(|remove_drm|\.permissions\s*=|owner_pw")
    hits = []
    for f in (ROOT / "src" / "id_translate").rglob("*.py"):
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if forbidden.search(line):
                hits.append(f"{f.name}:{n}: {line.strip()}")
    assert hits == []


def test_token_errors_block_output(md, tmp_path):
    p = tmp_path / "p.md"
    p.write_text("Hello {name}, welcome.\n", encoding="utf-8")
    seg = tmp_path / "s.jsonl"
    segs, _ = extract_to(p, seg)
    out = tmp_path / "o.md"
    with pytest.raises(ValidationError, match="missing tokens"):
        apply_translations(p, seg, {segs[0].id: "Halo, selamat datang."}, out)
    assert not out.exists()
    res = apply_translations(p, seg, {segs[0].id: "Halo, selamat datang."}, out, allow_partial=True,
                             options=ApplyOptions())
    assert res.kept_source_ids == [segs[0].id]
    assert out.read_text(encoding="utf-8") == p.read_text(encoding="utf-8")


def test_qa_report_and_compare_never_overwrite(md, tmp_path):
    tgt = tmp_path / "doc_id.md"
    tgt.write_text("# Judul\n\nHalo dunia, ini adalah uji.\n", encoding="utf-8")
    rep = tmp_path / "qa.md"
    cli("qa", md, tgt, "--report", rep)
    cli("qa", md, tgt, "--report", rep)
    assert rep.exists() and (tmp_path / "qa-2.md").exists()
    png = tmp_path / "c.png"
    png.write_bytes(b"old")
    r = cli("compare", md, tgt, "--out", png)
    assert r.returncode == 4 and png.read_bytes() == b"old"
