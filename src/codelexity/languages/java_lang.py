from codelexity.languages.base import TreeSitterAnalyzer

try:
    import tree_sitter_java as _ts_java
    from tree_sitter import Language

    _LANGUAGE = Language(_ts_java.language())
except ImportError:
    _LANGUAGE = None


class JavaAnalyzer(TreeSitterAnalyzer):
    language_id = "java"
    file_extensions = (".java",)

    UNIT_TYPES = frozenset({"method_declaration", "constructor_declaration"})
    DECISION_TYPES = frozenset(
        {
            "if_statement",
            "for_statement",
            "enhanced_for_statement",
            "while_statement",
            "do_statement",
            "switch_block_statement_group",
            "switch_rule",
            "catch_clause",
            "ternary_expression",
        }
    )
    BOOLOP_TYPES = frozenset({"binary_expression"})
    BOOLOP_OPERATORS = frozenset({"&&", "||"})
    IMPORT_TYPES = frozenset({"import_declaration"})

    LINE_COMMENT = "//"
    BLOCK_COMMENTS = (("/*", "*/"),)

    def _language(self):
        if _LANGUAGE is None:
            raise ImportError("tree-sitter-java is not installed; install codelexity[multi-lang]")
        return _LANGUAGE
