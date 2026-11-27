"""CLI end-to-end flow, exit codes, batching/resume, translation memory, glossary-scan."""

import json
from pathlib import Path

from helpers import FIXTURES, cli

from id_translate.memory import TranslationMemory, plan_batches
from id_translate.pipeline import apply_translations, extract_to
from id_translate.segments import Segment


def _segments(res: Path) -> list[dict]:
    return [json.loads(x) for x in (res / "work/segments.jsonl").read_text(encoding="utf-8").splitlines()]


def test_full_flow_init_extract_batch_apply_qa_verify(tmp_path):
    src = tmp_path / "guide.md"
    src.write_bytes((FIXTURES / "sample.md").read_bytes())
    r = cli("init", src, "--out-root", tmp_path / "hasil")
    assert r.returncode == 0, r.stderr
    res = Path(r.stdout.strip())
    assert {p.name for p in res.iterdir()} == {"output", "work", "reports", "MANIFEST.json"}

    r = cli("extract", src, "--result", res)
    assert r.returncode == 0, r.stderr
    summary = json.loads(r.stdout)
    assert summary["format"] == "markdown" and summary["pending"] > 10

    r = cli("batch", res / "work/segments.jsonl", "--max-tokens", "60")
    assert r.returncode == 0, r.stderr
    plan = json.loads(r.stdout)
    assert plan["batches"] >= 2
    batch_dir = Path(plan["batch_dir"])
    index = json.loads((batch_dir / "index.json").read_text(encoding="utf-8"))
    # "translate" only the first batch -> resume must exclude it next time
    first = index["files"][0]
    lines = (batch_dir / first["file"]).read_text(encoding="utf-8").splitlines()
    out_lines = [json.dumps({"id": json.loads(x)["id"], "text": json.loads(x)["text"] + " [ID]"},
                            ensure_ascii=False) for x in lines]
    Path(first["translations_file"]).parent.mkdir(parents=True, exist_ok=True)
    Path(first["translations_file"]).write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    r = cli("batch", res / "work/segments.jsonl", "--max-tokens", "60")
    plan2 = json.loads(r.stdout)
    assert plan2["already_translated"] == len(lines)
    assert plan2["segments_in_batches"] == plan["segments_in_batches"] - len(lines)

    # apply without all translations fails with exit 6, partial works
    r = cli("apply", "--result", res)
    assert r.returncode == 6, r.stderr
    r = cli("apply", "--result", res, "--allow-partial")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["translated"] == len(lines) and out["kept_source_ids"]
    assert Path(out["output"]).is_file() and Path(out["report"]).is_file()

    r = cli("qa", src, out["output"], "--report", res / "reports/QA_report.md")
    assert r.returncode == 0, r.stdout
    assert (res / "reports/QA_report.md").is_file()
    assert cli("verify", res).returncode == 0


def test_dry_run_writes_nothing(tmp_path):
    src = tmp_path / "a.md"
    src.write_text("Hello there friend.\n", encoding="utf-8")
    r = cli("init", src, "--dry-run")
    assert r.returncode == 0 and not (tmp_path / "hasil-terjemahan").exists()
    r = cli("extract", src, "--out", tmp_path / "s.jsonl", "--dry-run")
    assert r.returncode == 0 and not (tmp_path / "s.jsonl").exists()
    cli("extract", src, "--out", tmp_path / "s.jsonl")
    tr = tmp_path / "t.jsonl"
    tr.write_text(json.dumps({"id": "md0001", "text": "Halo kawan."}) + "\n", encoding="utf-8")
    r = cli("apply", src, "--segments", tmp_path / "s.jsonl", "--translations", tr,
            "--out", tmp_path / "o.md", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert not (tmp_path / "o.md").exists()


def test_exit_codes(tmp_path):
    assert cli("inspect", tmp_path / "missing.md").returncode == 3
    (tmp_path / "x.unknownext").write_text("hi", encoding="utf-8")
    assert cli("inspect", tmp_path / "x.unknownext").returncode == 3
    assert cli("apply").returncode == 2  # usage: missing required paths
    assert cli("nonsense-command").returncode == 2
    bad = tmp_path / "s.jsonl"
    bad.write_text("{not json\n", encoding="utf-8")
    src = tmp_path / "a.md"
    src.write_text("Hello.\n", encoding="utf-8")
    r = cli("apply", src, "--segments", bad, "--translations", bad, "--out", tmp_path / "o.md")
    assert r.returncode == 6


def test_inspect_reports_segments_and_tokens():
    r = cli("inspect", FIXTURES / "sample.md")
    assert r.returncode == 0, r.stderr
    info = json.loads(r.stdout)
    assert info["format"] == "markdown" and info["segments_pending"] > 0
    assert info["estimated_input_tokens"] > 0 and info["encrypted"] is False


def test_plan_batches_budget_dedup_tm():
    segs = [Segment(id=f"s{i}", type="p", text=f"word{i} " * 20) for i in range(5)]
    segs.append(Segment(id="dup", type="p", text=segs[0].text))
    segs.append(Segment(id="num", type="p", text="123", status="skip"))
    tm = TranslationMemory(None)
    tm.add_many([(segs[4].text.strip() + "  ", "kata " * 20)])  # normalized key match
    plan = plan_batches(segs, done={"s1": "x"}, tm=tm, max_tokens=40)
    assert plan.already_done == 1 and plan.duplicates == 1 and "s4" in plan.tm_hits
    ids = [s.id for b in plan.batches for s in b]
    assert ids == ["s0", "s2", "s3"] and all(len(b) == 1 for b in plan.batches)
    assert plan.input_tokens > 0 and plan.output_tokens > 0


def test_apply_propagates_duplicates_and_appends_tm(tmp_path):
    src = tmp_path / "d.txt"
    src.write_text("Same sentence here.\n\nSame sentence here.\n\nOther one.\n", encoding="utf-8")
    seg = tmp_path / "s.jsonl"
    segs, _ = extract_to(src, seg)
    tm = TranslationMemory(tmp_path / "tm.jsonl")
    res = apply_translations(src, seg, {"t0001": "Kalimat sama di sini.", "t0003": "Yang lain."},
                             tmp_path / "o.txt", tm=tm)
    assert res.propagated == 1
    assert (tmp_path / "o.txt").read_text(encoding="utf-8").count("Kalimat sama di sini.") == 2
    assert len(TranslationMemory(tmp_path / "tm.jsonl")) == 2
    # TM file is append-only: a second run adds nothing new
    size = (tmp_path / "tm.jsonl").stat().st_size
    apply_translations(src, seg, {"t0001": "Kalimat sama di sini.", "t0003": "Yang lain."},
                       tmp_path / "o2.txt", tm=TranslationMemory(tmp_path / "tm.jsonl"))
    assert (tmp_path / "tm.jsonl").stat().st_size == size


def test_glossary_scan_candidates_and_violations(tmp_path):
    src = tmp_path / "g.md"
    src.write_text(
        "The Interest Curve shows player interest.\n\nThe Interest Curve is key. Game Design Document "
        "matters. Game Design Document again.\n", encoding="utf-8")
    gl = tmp_path / "glossary.md"
    gl.write_text("## Glosarium\n| EN | ID |\n|---|---|\n| Interest Curve | Kurva Minat |\n"
                  "## Terjemahan terlarang\n- Kurva Bunga → Kurva Minat\n", encoding="utf-8")
    seg = tmp_path / "s.jsonl"
    extract_to(src, seg)
    r = cli("glossary-scan", seg, "--glossary", gl)
    assert r.returncode == 0, r.stderr
    assert "Game Design Document" in r.stdout and "| Interest Curve | Kurva Minat | 2 |" in r.stdout
    tr = tmp_path / "t.jsonl"
    tr.write_text(json.dumps({"id": "md0001", "text": "Kurva Bunga menunjukkan minat pemain."}) + "\n",
                  encoding="utf-8")
    r = cli("glossary-scan", seg, "--glossary", gl, "--translations", tr)
    assert r.returncode == 1 and "forbidden translation 'Kurva Bunga'" in r.stdout
