"""Wide, shallow smoke tests for codelexity. No pytest: stdlib unittest covers it."""
import tempfile
import unittest
from math import log2
from pathlib import Path

import networkx as nx

from codelexity.calculations import (
    empty_lines, comments_and_docstrings, functions, normalized_path_list,
    imports, analyze_module, analyze_package, cyclomatic_complexity, maintainability_index,
)
from codelexity.graph import maintainability, mi_color
from codelexity.halstead import halstead_metrics, operators_and_operands

SAMPLE = Path(__file__).with_name("test_module.py").read_text()


class TestTextMetrics(unittest.TestCase):
    def test_empty_lines(self):
        self.assertEqual(empty_lines("a\n\nb\n \nc"), ["", " "])

    def test_comments_and_docstrings(self):
        found = comments_and_docstrings(SAMPLE)
        self.assertTrue(any("test module docstring" in f for f in found))
        self.assertTrue(any(f.strip() == "#" for f in found))

    def test_functions(self):
        fns = functions(SAMPLE)
        self.assertEqual(len(fns), 6)  # 5 top-level + nest1 nested inside nest0
        self.assertTrue(any(f.startswith("def nest0") for f in fns))


class TestPathFiltering(unittest.TestCase):
    def test_normalized_path_list(self):
        self.assertEqual(normalized_path_list("a/b/c.py"), ["a", "b", "c"])

    # is_valid's own params (module_path, include_only, exclude) are called positionally
    # as (path, exclude, include_only) by analyze_package, with inverted boolean logic on
    # top — the two cancel out for the exclude case below but not in general. Not fixing
    # per scope, testing through the public analyze_package entrypoint instead.


class TestImportResolution(unittest.TestCase):
    def test_resolves_regular_and_namespace_packages(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "pkg").mkdir()
            (root / "pkg" / "__init__.py").write_text("")
            (root / "pkg" / "mod.py").write_text("x = 1\n")
            (root / "ns").mkdir()  # namespace package: no __init__.py
            (root / "ns" / "sub.py").write_text("y = 2\n")
            user = root / "user.py"
            user.write_text("import pkg.mod\nimport ns.sub\nimport os\n")

            found = imports(user, root=root)

            self.assertIn(str((root / "pkg" / "mod.py").resolve()), found)
            self.assertIn(str((root / "ns" / "sub.py").resolve()), found)

    def test_unresolvable_import_is_dropped_not_raised(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            user = root / "user.py"
            user.write_text("import this_does_not_exist_anywhere\n")
            self.assertEqual(imports(user, root=root), [])


class TestModuleAndPackageAnalysis(unittest.TestCase):
    def test_analyze_module_shape(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "m.py"
            f.write_text(SAMPLE)
            data = analyze_module(f, root=Path(d))
            for key in ("imports", "total_lines", "empty_lines", "comments", "code_length", "contained_function_length"):
                self.assertIn(key, data)
            self.assertEqual(len(data["contained_function_length"]), 6)

    def test_analyze_package_walks_tree_and_filters(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "keep").mkdir()
            (root / "keep" / "a.py").write_text("import os\n")
            (root / "drop").mkdir()
            (root / "drop" / "b.py").write_text("import os\n")

            result = analyze_package(root, exclude=("drop",))
            self.assertTrue(any("keep/a.py" in k for k in result))
            self.assertFalse(any("drop/b.py" in k for k in result))

            result = analyze_package(root, include_only=("drop",))
            self.assertTrue(any("drop/b.py" in k for k in result))
            self.assertFalse(any("keep/a.py" in k for k in result))


class TestHalstead(unittest.TestCase):
    def test_splits_operators_from_operands(self):
        m = halstead_metrics("a = b + 1\n")  # operators: = + ; operands: a b 1
        self.assertEqual((m["distinct_operators"], m["total_operators"]), (2, 2))
        self.assertEqual((m["distinct_operands"], m["total_operands"]), (3, 3))
        self.assertEqual((m["vocabulary"], m["length"]), (5, 5))
        self.assertAlmostEqual(m["volume"], 5 * log2(5))
        self.assertAlmostEqual(m["difficulty"], (2 * 3) / (2 * 3))

    def test_statements_count_as_operators(self):
        m = halstead_metrics("for x in y:\n    pass\n")  # For, Pass
        self.assertEqual(m["total_operators"], 2)
        self.assertEqual(m["distinct_operands"], 2)  # x, y

    def test_call_is_one_operator_not_a_paired_delimiter(self):
        ops, _ = operators_and_operands("f(1)\n")
        self.assertEqual(dict(ops), {"Call": 1})

    def test_empty_source_does_not_divide_by_zero(self):
        m = halstead_metrics("")
        self.assertEqual((m["volume"], m["difficulty"], m["effort"]), (0.0, 0.0, 0.0))


class TestComplexityMetrics(unittest.TestCase):
    def test_cyclomatic_complexity_counts_branches(self):
        self.assertEqual(cyclomatic_complexity(""), 1)  # straight-line code is 1, never 0
        self.assertEqual(cyclomatic_complexity("if a:\n    pass\n"), 2)
        self.assertEqual(cyclomatic_complexity("if a and b and c:\n    pass\n"), 4)  # If + 2 BoolOp branches
        self.assertEqual(cyclomatic_complexity("[x for x in y if x]\n"), 3)  # comprehension + its if

    def test_cyclomatic_complexity_counts_except_handlers(self):
        src = "try:\n    pass\nexcept KeyError:\n    pass\nexcept ValueError:\n    pass\n"
        self.assertEqual(cyclomatic_complexity(src), 3)

    def test_maintainability_index_is_a_percentage(self):
        self.assertEqual(maintainability_index(""), 100.0)  # nothing to maintain
        mi = maintainability_index(SAMPLE)
        self.assertGreaterEqual(mi, 0.0)
        self.assertLessEqual(mi, 100.0)

    def test_maintainability_index_drops_as_code_gets_hairier(self):
        simple = "def f(a):\n    return a\n"
        hairy = simple + "".join(f"def g{i}(a, b):\n    return a if a and b else b\n" for i in range(30))
        self.assertLess(maintainability_index(hairy), maintainability_index(simple))


class TestGraphMetrics(unittest.TestCase):
    def test_mi_color_bands(self):
        self.assertEqual(mi_color(65), "#2e7d32")
        self.assertEqual(mi_color(64), "#f9a825")
        self.assertEqual(mi_color(40), "#f9a825")
        self.assertEqual(mi_color(39), "#c62828")

    def test_maintainability_ignores_nodes_without_data(self):
        G = nx.DiGraph()
        G.add_node("a", size=10, maintainability=40.0)
        G.add_node("b", size=10, maintainability=60.0)
        G.add_edge("transitive_import", "a")  # no attributes: must not raise
        self.assertAlmostEqual(maintainability(G), 50.0, delta=10.0)

    def test_maintainability_of_empty_graph(self):
        self.assertEqual(maintainability(nx.DiGraph()), 100.0)


if __name__ == "__main__":
    unittest.main()
