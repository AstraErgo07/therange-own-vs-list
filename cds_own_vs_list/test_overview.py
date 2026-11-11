"""docs/OVERVIEW.md matches the code, and the shared wording is in place.
Run: python -m unittest discover -s cds_own_vs_list -p "test_*.py"   (from the repository root)"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from common.text import FOOTER, VERSION  # noqa: E402
from tools.build_overview import OUT, build  # noqa: E402


class TestOverview(unittest.TestCase):
    def test_overview_doc_is_up_to_date(self):
        self.assertEqual(build(), OUT.read_text(encoding="utf-8"),
                         "docs/OVERVIEW.md is out of date: run python tools/build_overview.py")

    def test_footer_and_version(self):
        self.assertEqual(VERSION, "v1.0")
        self.assertIn("Author details available on request.", FOOTER)
        for bad in ("\u2014", "\u2013"):
            self.assertNotIn(bad, build())


if __name__ == "__main__":
    unittest.main()
