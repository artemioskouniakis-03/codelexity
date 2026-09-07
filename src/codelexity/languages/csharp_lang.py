from codelexity.languages.base import TreeSitterAnalyzer

try:
    import tree_sitter_c_sharp as _ts_csharp
    from tree_sitter import Language

    _LANGUAGE = Language(_ts_csharp.language())
except ImportError:
    _LANGUAGE = None


class CSharpAnalyzer(TreeSitterAnalyzer):
    language_id = "csharp"
    file_extensions = (".cs",)

    UNIT_TYPES = frozenset({"method_declaration", "local_function_statement", "constructor_declaration"})
    DECISION_TYPES = frozenset(
        {
            "if_statement",
            "for_statement",
            "foreach_statement",
            "while_statement",
            "do_statement",
            "switch_section",
            "switch_expression_arm",
            "catch_clause",
            "conditional_expression",
        }
    )
    BOOLOP_TYPES = frozenset({"binary_expression"})
    BOOLOP_OPERATORS = frozenset({"&&", "||", "??"})
    IMPORT_TYPES = frozenset({"using_directive"})

    LINE_COMMENT = "//"
    BLOCK_COMMENTS = (("/*", "*/"),)

    def _language(self):
        if _LANGUAGE is None:
            raise ImportError("tree-sitter-c-sharp is not installed; install codelexity[multi-lang]")
        return _LANGUAGE

    NAMESPACE_TYPES = frozenset({"namespace_declaration", "file_scoped_namespace_declaration"})

    def namespaces_declared(self, tree, source: bytes) -> list[str]:
        """Namespace names this file declares - used by coupling.py's C# using-directive
        resolution (namespace -> [files]) since `using` doesn't map 1:1 to a file path."""
        from codelexity.languages.base import walk_collect

        names = []
        for node in walk_collect(tree.root_node, self.NAMESPACE_TYPES):
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                names.append(source[name_node.start_byte : name_node.end_byte].decode("utf-8", errors="replace"))
        return names
