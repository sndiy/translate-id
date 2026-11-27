"""Uji asap untuk tiga skrip. Jalankan: python -m unittest discover -s tests -v"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

S = Path(__file__).resolve().parents[1] / "skills" / "translate-id" / "scripts"


def run(*args, **kw):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, **kw)


class SafeOutput(unittest.TestCase):
    def test_never_overwrites_and_verifies(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "a.md"
            src.write_text("hello", encoding="utf-8")
            r1 = run(S / "safe_output.py", src)
            r2 = run(S / "safe_output.py", src)
            self.assertEqual(r1.returncode, 0)
            p1, p2 = r1.stdout.strip(), r2.stdout.strip()
            self.assertNotEqual(p1, p2)  # folder kedua berbeda, bukan menimpa
            for sub in ("output", "work", "reports"):
                self.assertTrue((Path(p1) / sub).is_dir())
            self.assertEqual(run(S / "safe_output.py", "--verify", p1).returncode, 0)
            src.write_text("changed", encoding="utf-8")
            self.assertEqual(run(S / "safe_output.py", "--verify", p1).returncode, 1)
            self.assertEqual(run(S / "safe_output.py", "--check", src).returncode, 1)
            self.assertTrue(run(S / "safe_output.py", "--unique", src).stdout.strip().endswith("a-2.md"))


class QA(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "en.md").write_text(
            "Visit https://example.com now. Price 1,250.50 for 3 items. Hello {name}, %d left. "
            "The Interest Curve matters and part of the art is clear.\n", encoding="utf-8")
        (self.d / "g.md").write_text(
            "## Glosarium\n| EN | ID |\n|---|---|\n| Interest Curve | Kurva Minat |\n| art | seni |\n"
            "## Terjemahan terlarang\n- Kurva Bunga → Kurva Minat\n", encoding="utf-8")

    def qa(self, text):
        (self.d / "id.md").write_text(text, encoding="utf-8")
        return run(S / "qa_check.py", "--source", self.d / "en.md", "--target", self.d / "id.md",
                   "--glossary", self.d / "g.md", "--strict")

    def test_good_translation_passes(self):
        r = self.qa("Kunjungi https://example.com sekarang. Harga 1.250,50 untuk 3 barang. Halo {name}, sisa %d. "
                    "Kurva Minat itu penting dan sebagian seni sudah jelas.\n")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_forbidden_term_and_lost_url_fail(self):
        r = self.qa("Kunjungi situs sekarang. Harga 1.250,50 untuk 3 barang. Halo {name}, sisa %d. Kurva Bunga.\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Kurva Bunga", r.stdout)
        self.assertIn("URL hilang", r.stdout)

    def test_word_boundary_in_glossary(self):
        # "art" ada di "part"; hanya kata utuh "art" yang dihitung
        r = self.qa("Kunjungi https://example.com. Harga 1.250,50 untuk 3 barang. Halo {name}, sisa %d. Kurva Minat.\n")
        self.assertIn('"art"', r.stdout)  # "art" (kata utuh) ada di sumber, "seni" tidak ada di hasil


class Inventory(unittest.TestCase):
    def test_text_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.srt"
            p.write_text("1\n00:00:01,000 --> 00:00:02,000\nHi\n", encoding="utf-8")
            r = run(S / "inventory.py", p)
            self.assertEqual(r.returncode, 0)
            self.assertIn('"cues": 1', r.stdout)


if __name__ == "__main__":
    unittest.main()
