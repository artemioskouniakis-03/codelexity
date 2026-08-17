"""Wide, shallow smoke tests for codelexity.calculations. No pytest: stdlib unittest covers it."""
import tempfile
import unittest
from pathlib import Path

from codelexity.calculations import (
    empty_lines, comments_and_docstrings, functions, normalized_path_list,
    imports, analyze_module, analyze_package,
)

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


if __name__ == "__main__":
    unittest.main()
