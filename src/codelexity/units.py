from codelexity.languages.base import LanguageAnalyzer


def loc(source: str, analyzer: LanguageAnalyzer) -> int:
    """Lines of code excluding blank lines, comments, and lines that are exactly `[` or
    `]` with nothing else on them."""
    count = 0
    for line in analyzer.strip_for_loc(source):
        stripped = line.strip()
        if not stripped or stripped in ("[", "]"):
            continue
        count += 1
    return count


def unit_size(unit_source: str, analyzer: LanguageAnalyzer) -> int:
    return loc(unit_source, analyzer)


def unit_complexity(unit_node, analyzer: LanguageAnalyzer, source: bytes) -> int:
    """1 + McCabe decision points within the unit's own body, excluding nested units'
    branches (a function's complexity must not include a closure's internal branching)."""
    return 1 + analyzer.count_decision_points(unit_node, source, exclude_nested=True)


def module_complexity(root_node, analyzer: LanguageAnalyzer, source: bytes) -> int:
    """Whole-file McCabe complexity, tree-sitter equivalent of the existing
    `calculations.cyclomatic_complexity` for languages other than Python. Kept separate
    from the ast-based Python pipeline so results are never silently mixed."""
    return 1 + analyzer.count_decision_points(root_node, source, exclude_nested=False)
