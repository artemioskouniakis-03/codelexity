import logging
import os
import time
from collections.abc import Callable
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

# Always pruned, regardless of the caller's exclude list - none of these are ever source
# code worth analyzing (VCS metadata, tool caches, framework build output), and a user
# who doesn't think to exclude them can otherwise turn a normal analysis into a very slow
# one: .git can hold hundreds of subdirectories under objects/, refs/, logs/ (each one
# feeding into Python/Java import resolution's search path once it's discovered, since
# every external/stdlib import lookup then has to probe it first); .next/dist-style build
# output routinely contains multi-megabyte minified/bundled JS files that are individually
# expensive to run through every metric pass, for a file nobody hand-authors anyway.
ALWAYS_EXCLUDED_DIRS = frozenset(
    {".git", ".hg", ".svn", ".next", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".turbo"}
)

# Files larger than this are skipped entirely (not read past a stat() call) rather than
# run through parsing/units/tokenization - a defense-in-depth backstop for generated or
# bundled files that live somewhere ALWAYS_EXCLUDED_DIRS/the caller's exclude list didn't
# anticipate (e.g. a checked-in vendor bundle sitting directly under src/). 500 KB is
# comfortably above any hand-authored source file while well below typical minified
# bundles, which commonly run into multiple megabytes.
DEFAULT_MAX_FILE_BYTES = 500_000


def _discover(root: Path, exclude: tuple[str, ...]) -> tuple[list[Path], list[Path]]:
    """Walks `root` once, pruning any directory whose own name is in `exclude` (plus
    ALWAYS_EXCLUDED_DIRS) before descending into it - unlike `Path.rglob("*")` followed
    by a per-file filter, this never enumerates the contents of an excluded directory at
    all. Matters a lot in practice: a `.venv` or `node_modules` can contain tens of
    thousands of files, and filtering them out after a full recursive walk still pays the
    cost of walking them. `include_only` is intentionally NOT used for pruning here - it
    only loosely matches "any path segment", so pruning by it could incorrectly skip a
    wanted nested folder; it stays a post-walk filter via is_valid(), same as before.

    Returns (files, dirs) - `dirs` is reused by coupling.resolve_edges() for Python/Java
    import resolution, so those don't each re-walk the whole tree per file (previously
    the single biggest cost with a .venv/node_modules present under the analyzed root)."""
    excluded = set(exclude) | ALWAYS_EXCLUDED_DIRS
    files: list[Path] = []
    dirs: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in excluded]
        dirs.extend(Path(dirpath) / d for d in dirnames)
        files.extend(Path(dirpath) / name for name in filenames)
    return files, dirs


def analyze_package_multi_lang(
    path: str | Path,
    *,
    component_depth: int = 1,
    duplication_min_tokens: int = DEFAULT_MIN_TOKENS,
    exclude: tuple[str, ...] = (),
    include_only: tuple[str, ...] = (),
    languages: tuple[str, ...] = (),
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    on_parse_progress: Callable[[int, int], None] | None = None,
) -> AnalysisResult:
    """`on_parse_progress(files_done, files_total)`, when given, is called once with
    (0, total) right after file discovery (so a caller can show the total up front before
    any parsing happens) and then periodically while parsing - UI-agnostic, so a caller
    (e.g. the Streamlit app) can drive a progress bar without this module depending on it."""
    root = Path(path).resolve()
    units: list[UnitMetric] = []
    file_loc: dict[str, int] = {}
    file_language: dict[str, str] = {}
    raw_imports: dict[str, list[str]] = {}
    csharp_namespaces: dict[str, list[str]] = {}
    file_tokens = {}
    unparsed_files: list[str] = []
    unsupported_files: list[str] = []
    skipped_large_files: list[str] = []

    discover_start = time.monotonic()
    all_paths, search_dirs = _discover(root, exclude)
    total_paths = len(all_paths)
    logger.info(
        "Discovered %d files under %s in %.2fs (pruned %s)",
        total_paths,
        root,
        time.monotonic() - discover_start,
        exclude or "nothing",
    )
    if on_parse_progress is not None:
        on_parse_progress(0, total_paths)

    progress_step = max(total_paths // 100, 1)  # ~100 UI updates over the whole run, regardless of repo size
    for index, file_path in enumerate(all_paths, start=1):
        if index % 200 == 0 or index == total_paths:
            logger.info("Parsed %d/%d files...", index, total_paths)
        if on_parse_progress is not None and (index % progress_step == 0 or index == total_paths):
            on_parse_progress(index, total_paths)
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
            if file_path.stat().st_size > max_file_bytes:
                skipped_large_files.append(posix)
                continue
        except OSError as exc:
            logger.warning("Failed to stat %s: %s", posix, exc)
            unparsed_files.append(posix)
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

    resolve_start = time.monotonic()
    logger.info("Resolving cross-file imports (module coupling)...")
    resolved_edges = resolve_edges(file_language, root, raw_imports, csharp_namespaces, search_dirs=search_dirs)
    logger.info("Resolved cross-file imports in %.2fs", time.monotonic() - resolve_start)
    incoming = module_coupling(resolved_edges, list(file_loc.keys()))

    grouped = group_files_by_component(list(file_loc.keys()), root, component_depth)
    component_of = {f: c for c, files in grouped.items() for f in files}
    ce, ca = component_edges(resolved_edges, component_of)

    logger.info(
        "Scanning for duplicate code across %d files (min_tokens=%d)...", len(file_tokens), duplication_min_tokens
    )
    duplicate_blocks_raw = find_duplicate_blocks(file_tokens, min_tokens=duplication_min_tokens)
    covered_lines = duplicate_loc_per_file(duplicate_blocks_raw)
    logger.info("Found %d duplicate block(s)", len(duplicate_blocks_raw))

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

    edges = tuple((importer, target) for importer, targets in resolved_edges.items() for target in targets)

    if skipped_large_files:
        logger.info(
            "Skipped %d file(s) larger than %d bytes (not read/parsed)", len(skipped_large_files), max_file_bytes
        )

    return AnalysisResult(
        total_loc=sum(file_loc.values()),
        units=tuple(units),
        files=tuple(files),
        components=tuple(components),
        duplicate_blocks=duplicate_blocks,
        edges=edges,
        unparsed_files=tuple(unparsed_files),
        unsupported_files=tuple(unsupported_files),
        skipped_large_files=tuple(skipped_large_files),
    )
