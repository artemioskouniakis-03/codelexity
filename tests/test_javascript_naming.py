"""Verifies the unit-naming fallback for anonymous functions passed as call arguments -
run only when the multi-lang extra (tree-sitter + grammars) is installed."""

import unittest

try:
    import tree_sitter_javascript  # noqa: F401

    MULTI_LANG_AVAILABLE = True
except ImportError:
    MULTI_LANG_AVAILABLE = False

if MULTI_LANG_AVAILABLE:
    from codelexity.languages.javascript_lang import JavaScriptAnalyzer


@unittest.skipUnless(MULTI_LANG_AVAILABLE, "tree-sitter grammars not installed (codelexity[multi-lang])")
class TestJavaScriptAnonymousNaming(unittest.TestCase):
    def _unit_names(self, source: str) -> list[str]:
        analyzer = JavaScriptAnalyzer()
        source_bytes = source.encode("utf-8")
        tree = analyzer.parse(source_bytes)
        return [u.name for u in analyzer.find_units(tree, source_bytes)]

    def test_callback_argument_is_named_after_the_outer_call(self):
        # The extremely common React/JS pattern the old fallback missed entirely: an
        # arrow function passed directly as a call argument, not assigned to a variable.
        names = self._unit_names("useEffect(() => { doThing(); }, []);")
        self.assertEqual(names, ["<arg of useEffect>"])

    def test_array_method_callback_is_named_after_the_method(self):
        names = self._unit_names("items.map(function (x) { return x + 1; });")
        self.assertEqual(names, ["<arg of items.map>"])

    def test_variable_assigned_arrow_still_gets_its_variable_name(self):
        names = self._unit_names("const handleClick = () => { doThing(); };")
        self.assertEqual(names, ["handleClick"])

    def test_truly_unplaceable_function_still_falls_back_to_anonymous_line(self):
        names = self._unit_names("(function () { doThing(); })();")
        self.assertEqual(len(names), 1)
        self.assertTrue(names[0].startswith("<anonymous>:"))


if __name__ == "__main__":
    unittest.main()
