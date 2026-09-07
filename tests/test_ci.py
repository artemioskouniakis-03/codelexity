"""CI command tests - run only when the multi-lang and ci extras are installed."""

import json
import tempfile
import unittest
from pathlib import Path

try:
    import jinja2  # noqa: F401
    import tree_sitter_python  # noqa: F401

    CI_AVAILABLE = True
except ImportError:
    CI_AVAILABLE = False

if CI_AVAILABLE:
    from codelexity import ci


@unittest.skipUnless(CI_AVAILABLE, "codelexity[multi-lang,ci] extras not installed")
class TestCi(unittest.TestCase):
    def _write_fixture(self, root: Path) -> None:
        (root / "clean.py").write_text("def add(a, b):\n    return a + b\n")

    def test_exits_zero_when_score_meets_threshold(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_fixture(root)
            exit_code = ci.main([str(root), "--min-stars", "1.0"])
            self.assertEqual(exit_code, 0)

    def test_exits_nonzero_when_score_below_threshold(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_fixture(root)
            exit_code = ci.main([str(root), "--min-stars", "6.0"])
            self.assertEqual(exit_code, 1)

    def test_writes_json_summary_with_expected_shape(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_fixture(root)
            json_path = root / "summary.json"
            ci.main([str(root), "--json", str(json_path)])
            summary = json.loads(json_path.read_text())
            for key in ("overall_stars", "overall_raw", "metrics", "cocomo", "total_loc"):
                self.assertIn(key, summary)

    def test_writes_html_report(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_fixture(root)
            report_path = root / "report.html"
            ci.main([str(root), "--report", str(report_path)])
            self.assertTrue(report_path.exists())
            self.assertIn("Codelexity Report", report_path.read_text())

    def test_test_files_excluded_by_default_included_with_flag(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_fixture(root)
            (root / "tests").mkdir()
            (root / "tests" / "test_clean.py").write_text("def test_add():\n    assert True\n")

            json_default = root / "default.json"
            ci.main([str(root), "--json", str(json_default)])
            self.assertFalse(json.loads(json_default.read_text())["exclude_tests"] is False)

            json_included = root / "included.json"
            ci.main([str(root), "--json", str(json_included), "--include-tests"])
            summary = json.loads(json_included.read_text())
            self.assertFalse(summary["exclude_tests"])
            self.assertGreater(summary["units"], 1)  # picks up test_add on top of add


if __name__ == "__main__":
    unittest.main()
