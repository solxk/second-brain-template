"""Tests for check_wiki_links.py. Run from the vault root:
    python3 -m unittest Scripts/test_check_wiki_links.py -v
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_wiki_links as C  # noqa: E402


def vault(files: dict) -> Path:
    root = Path(tempfile.mkdtemp())
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def run(root: Path, *args) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = C.main(list(args), root=root)
    return rc, out.getvalue()


class CheckLinks(unittest.TestCase):
    def test_scan_finds_broken_and_archived_and_skips_code(self):
        root = vault({
            "Home.md": "See [[Plan]], [[Missing]], [[Old plan]] and `[[In code]]`.\n",
            "Plan.md": "x\n",
            "Archive/Old plan.md": "x\n",
        })
        broken, archived = C.scan(root)
        self.assertEqual([b[2] for b in broken], ["[[Missing]]"])
        self.assertEqual([a[2] for a in archived], ["[[Old plan]]"])

    def test_archived_links_are_counted_not_listed_by_default(self):
        root = vault({"Home.md": "Done: [[Old plan]]\n", "Archive/Old plan.md": "x\n"})
        rc, out = run(root)
        self.assertEqual(rc, 0)
        self.assertIn("1 link points into Archive/", out)
        self.assertNotIn("Home.md:1", out)

    def test_archived_flag_lists_them(self):
        root = vault({"Home.md": "Done: [[Old plan]]\n", "Archive/Old plan.md": "x\n"})
        rc, out = run(root, "--archived")
        self.assertEqual(rc, 0)
        self.assertIn("Home.md:1  [[Old plan]] -> Archive/Old plan.md", out)

    def test_broken_link_fails(self):
        rc, out = run(vault({"Home.md": "[[Nowhere]]\n"}))
        self.assertEqual(rc, 1)
        self.assertIn("BROKEN LINKS: 1", out)


if __name__ == "__main__":
    unittest.main()
