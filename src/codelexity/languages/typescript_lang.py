from codelexity.languages.javascript_lang import JavaScriptAnalyzer

try:
    import tree_sitter_typescript as _ts_ts
    from tree_sitter import Language

    _TS_LANGUAGE = Language(_ts_ts.language_typescript())
    _TSX_LANGUAGE = Language(_ts_ts.language_tsx())
except ImportError:
    _TS_LANGUAGE = None
    _TSX_LANGUAGE = None


class TypeScriptAnalyzer(JavaScriptAnalyzer):
    """Handles .ts and .tsx. Angular components/services are plain .ts files - decorators
    like @Component are irrelevant to unit/complexity/coupling extraction and need no
    special node-type handling, so Angular gets no bespoke code path."""

    def __init__(self, dialect: str = "ts"):
        self.dialect = dialect
        self.language_id = "typescript"
        self.file_extensions = (".tsx",) if dialect == "tsx" else (".ts",)

    IMPORT_TYPES = frozenset({"import_statement", "import_alias"})

    def _language(self):
        language = _TSX_LANGUAGE if self.dialect == "tsx" else _TS_LANGUAGE
        if language is None:
            raise ImportError("tree-sitter-typescript is not installed; install codelexity[multi-lang]")
        return language
