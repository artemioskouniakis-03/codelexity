from codelexity.languages.base import TreeSitterAnalyzer, walk_collect

try:
    import tree_sitter_javascript as _ts_js
    from tree_sitter import Language

    _LANGUAGE = Language(_ts_js.language())
except ImportError:
    _LANGUAGE = None


class JavaScriptAnalyzer(TreeSitterAnalyzer):
    """Handles .js and .jsx - JSX is part of the tree-sitter-javascript grammar already."""

    language_id = "javascript"
    file_extensions = (".js", ".jsx")

    UNIT_TYPES = frozenset(
        {
            "function_declaration",
            "function_expression",
            "arrow_function",
            "method_definition",
            "generator_function_declaration",
        }
    )
    DECISION_TYPES = frozenset(
        {
            "if_statement",
            "for_statement",
            "for_in_statement",
            "while_statement",
            "do_statement",
            "switch_case",
            "catch_clause",
            "ternary_expression",
        }
    )
    BOOLOP_TYPES = frozenset({"binary_expression"})
    BOOLOP_OPERATORS = frozenset({"&&", "||"})
    IMPORT_TYPES = frozenset({"import_statement"})

    LINE_COMMENT = "//"
    BLOCK_COMMENTS = (("/*", "*/"),)

    def _language(self):
        if _LANGUAGE is None:
            raise ImportError("tree-sitter-javascript is not installed; install codelexity[multi-lang]")
        return _LANGUAGE

    def import_targets(self, tree, source: bytes) -> list[str]:
        targets = super().import_targets(tree, source)
        for call in walk_collect(tree.root_node, frozenset({"call_expression"})):
            callee = call.child_by_field_name("function")
            if callee is None or callee.type != "identifier":
                continue
            if source[callee.start_byte : callee.end_byte] != b"require":
                continue
            args = call.child_by_field_name("arguments")
            if args is None:
                continue
            targets.append(source[call.start_byte : call.end_byte].decode("utf-8", errors="replace"))
        return targets
