"""End-to-end smoke tests for the additive multi-language pipeline, run only when the
`multi-lang` extra (tree-sitter + grammars) is installed."""

import tempfile
import unittest
from pathlib import Path

try:
    import tree_sitter_python  # noqa: F401

    MULTI_LANG_AVAILABLE = True
except ImportError:
    MULTI_LANG_AVAILABLE = False

if MULTI_LANG_AVAILABLE:
    from codelexity.components import component_for, independence
    from codelexity.multi_lang import analyze_package_multi_lang


@unittest.skipUnless(MULTI_LANG_AVAILABLE, "tree-sitter grammars not installed (codelexity[multi-lang])")
class TestMultiLangPipeline(unittest.TestCase):
    def test_python_units_and_cross_file_coupling(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "util").mkdir()
            (root / "util" / "helper.py").write_text("def add(a, b):\n    return a + b\n")
            (root / "src").mkdir()
            (root / "src" / "main.py").write_text(
                "from util.helper import add\n\n"
                "def compute(a, b):\n"
                "    if a and b:\n"
                "        return add(a, b)\n"
                "    return 0\n"
            )

            result = analyze_package_multi_lang(root, component_depth=1)

            names = {u.qualified_name for u in result.units}
            self.assertEqual(names, {"add", "compute"})

            compute = next(u for u in result.units if u.qualified_name == "compute")
            self.assertEqual(compute.complexity, 3)  # base 1 + if + boolop chain (2 operands - 1)

            helper_file = next(f for f in result.files if f.file.endswith("helper.py"))
            self.assertEqual(helper_file.incoming_references, 1)

    def test_on_parse_progress_reports_total_up_front_and_reaches_completion(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for i in range(5):
                (root / f"m{i}.py").write_text(f"x = {i}\n")

            calls: list[tuple[int, int]] = []
            analyze_package_multi_lang(root, on_parse_progress=lambda done, total: calls.append((done, total)))

            self.assertEqual(calls[0], (0, 5))  # total known before any file is parsed
            self.assertEqual(calls[-1], (5, 5))  # always reaches 100% at the end

    def test_component_depth_zero_is_one_component(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a").mkdir()
            (root / "a" / "x.py").write_text("x = 1\n")
            (root / "b").mkdir()
            (root / "b" / "y.py").write_text("y = 2\n")

            result = analyze_package_multi_lang(root, component_depth=0)
            self.assertEqual({c.name for c in result.components}, {"."})

    def test_component_for_handles_files_above_the_requested_depth(self):
        root = Path("/repo")
        self.assertEqual(component_for("/repo/top_level.py", root, depth=1), ".")
        self.assertEqual(component_for("/repo/a/b/c.py", root, depth=2), "a/b")

    def test_independence_is_max_when_isolated(self):
        self.assertEqual(independence(0, 0), 1.0)
        self.assertEqual(independence(1, 0), 0.0)  # pure efferent (unstable, low independence)
        self.assertEqual(independence(0, 1), 1.0)  # pure afferent (stable, high independence)


if __name__ == "__main__":
    unittest.main()
