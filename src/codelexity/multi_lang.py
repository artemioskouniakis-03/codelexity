import logging
from pathlib import Path

from codelexity.calculations import is_valid
from codelexity.components import component_edges, group_files_by_component, independence
from codelexity.coupling import module_coupling, resolve_edges
from codelexity.duplication import DEFAULT_MIN_TOKENS, duplicate_loc_per_file, find_duplicate_blocks, tokenize
from codelexity.languages import analyzer_for
from codelexity.languages.csharp_lang import CSharpAnalyzer
from codelexity.models import AnalysisResult, ComponentMetric, DuplicateBlock, FileMetric, Language, UnitMetric
from codelexity.units import loc, unit_complexity, unit_size

logger = logging.getLogger(__name__)


def analyze_package_multi_lang(
    path: str | Path,
    *,
    component_depth: int = 1,
    duplication_min_tokens: int = DEFAULT_MIN_TOKENS,
    exclude: tuple[str, ...] = (),
    include_only: tuple[str, ...] = (),
    languages: tuple[str, ...] = (),
) -> AnalysisResult:
    root = Path(path).resolve()
    units: list[UnitMetric] = []
    file_loc: dict[str, int] = {}
    file_language: dict[str, str] = {}
    raw_imports: dict[str, list[str]] = {}
    csharp_namespaces: dict[str, list[str]] = {}
    file_tokens = {}
    unparsed_files: list[str] = []
    unsupported_files: list[str] = []

    all_paths = [p for p in root.rglob("*") if p.is_file()]
    for file_path in all_paths:
        posix = file_path.resolve().as_posix()
        if not is_valid(posix, exclude, include_only):
            continue
        analyzer = analyzer_for(file_path)
        if analyzer is None:
            if file_path.suffix:
                unsupported_files.append(posix)
            continue
        if languages and analyzer.language_id not in languages:
            continue
        try:
            source_bytes = file_path.read_bytes()
            tree = analyzer.parse(source_bytes)
        except ImportError:
            unsupported_files.append(posix)
            continue
        except (OSError, ValueError) as exc:
            logger.warning("Failed to read/parse %s: %s", posix, exc)
            unparsed_files.append(posix)
            continue

        if tree.root_node.has_error:
            unparsed_files.append(posix)

        source_text = source_bytes.decode("utf-8", errors="replace")
        file_loc[posix] = loc(source_text, analyzer)
        file_language[posix] = analyzer.language_id
        raw_imports[posix] = analyzer.import_targets(tree, source_bytes)
        file_tokens[posix] = tokenize(tree, source_bytes, analyzer)

        if isinstance(analyzer, CSharpAnalyzer):
            csharp_namespaces[posix] = analyzer.namespaces_declared(tree, source_bytes)

        for unit_node in analyzer.find_units(tree, source_bytes):
            units.append(
                UnitMetric(
                    file=posix,
                    qualified_name=unit_node.name,
                    kind=unit_node.kind,
                    language=Language(analyzer.language_id),
                    start_line=unit_node.span.start_line,
                    end_line=unit_node.span.end_line,
                    loc=unit_size(unit_node.source, analyzer),
                    complexity=unit_complexity(unit_node.node, analyzer, source_bytes),
                )
            )

    resolved_edges = resolve_edges(file_language, root, raw_imports, csharp_namespaces)
    incoming = module_coupling(resolved_edges, list(file_loc.keys()))

    grouped = group_files_by_component(list(file_loc.keys()), root, component_depth)
    component_of = {f: c for c, files in grouped.items() for f in files}
    ce, ca = component_edges(resolved_edges, component_of)

    duplicate_blocks_raw = find_duplicate_blocks(file_tokens, min_tokens=duplication_min_tokens)
    covered_lines = duplicate_loc_per_file(duplicate_blocks_raw)

    files: list[FileMetric] = []
    for posix, total in file_loc.items():
        duplicate_count = len(covered_lines.get(posix, set()))
        files.append(
            FileMetric(
                file=posix,
                language=Language(file_language[posix]),
                loc=total,
                incoming_references=incoming.get(posix, 0),
                duplicate_loc=min(duplicate_count, total),
                component=component_of.get(posix, "."),
            )
        )

    components: list[ComponentMetric] = []
    for name, comp_files in grouped.items():
        components.append(
            ComponentMetric(
                name=name,
                depth=component_depth,
                loc=sum(file_loc[f] for f in comp_files),
                file_count=len(comp_files),
                efferent=ce.get(name, 0),
                afferent=ca.get(name, 0),
                independence_score=independence(ce.get(name, 0), ca.get(name, 0)),
                files=tuple(comp_files),
            )
        )

    duplicate_blocks = tuple(
        DuplicateBlock(
            file_a=b.file_a,
            lines_a=b.lines_a,
            file_b=b.file_b,
            lines_b=b.lines_b,
            token_length=b.token_length,
        )
        for b in duplicate_blocks_raw
    )

    return AnalysisResult(
        total_loc=sum(file_loc.values()),
        units=tuple(units),
        files=tuple(files),
        components=tuple(components),
        duplicate_blocks=duplicate_blocks,
        unparsed_files=tuple(unparsed_files),
        unsupported_files=tuple(unsupported_files),
    )
