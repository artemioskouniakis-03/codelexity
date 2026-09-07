from codelexity.languages.base import TreeSitterAnalyzer

try:
    import tree_sitter_python as _ts_python
    from tree_sitter import Language

    _LANGUAGE = Language(_ts_python.language())
except ImportError:
    _LANGUAGE = None


class PythonAnalyzer(TreeSitterAnalyzer):
    language_id = "python"
    file_extensions = (".py",)

    UNIT_TYPES = frozenset({"function_definition"})
    DECISION_TYPES = frozenset(
        {
            "if_statement",
            "elif_clause",
            "for_statement",
            "while_statement",
            "except_clause",
            "conditional_expression",
            "case_clause",
            "assert_statement",
            # Comprehension clauses: a for_in_clause + each if_clause together reproduce the
            # original "+1+len(ifs) per comprehension" rule (sum of 1's = number of for
            # clauses, sum of if_clauses = total ifs across all comprehensions).
            "for_in_clause",
            "if_clause",
        }
    )
    BOOLOP_TYPES = frozenset({"boolean_operator"})
    BOOLOP_OPERATORS = frozenset({"and", "or"})  # keep and/or chains separate, matching ast.BoolOp grouping
    IMPORT_TYPES = frozenset({"import_statement", "import_from_statement"})

    LINE_COMMENT = "#"
    BLOCK_COMMENTS = ()  # Python has no block-comment syntax; triple-quoted strings are
    # string literals, not comments - handled at the LOC level as ordinary code lines,
    # consistent with treating docstrings as code (matches tree-sitter's own tokenization).

    def _language(self):
        if _LANGUAGE is None:
            raise ImportError("tree-sitter-python is not installed; install codelexity[multi-lang]")
        return _LANGUAGE
