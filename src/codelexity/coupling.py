import sys
from collections import Counter, defaultdict
from pathlib import Path

_JS_EXTENSION_PROBE = (".ts", ".tsx", ".js", ".jsx")


def _resolve_python(module_path: Path, search_dirs: list[Path]) -> list[Path]:
    """Reuses the existing calculations._import_names/_resolve machinery, but with a
    caller-supplied, already-pruned `search_dirs` list instead of calling
    calculations.imports() (which does its own unconditional root.rglob("*") for every
    single file - with a .venv or node_modules present under the analyzed root, that
    turned a per-repo cost into a per-file one)."""
    from codelexity.calculations import _import_names, _resolve

    code = compile(module_path.read_text(encoding="utf-8"), str(module_path), "exec")
    search = sys.path + [str(d) for d in search_dirs]
    names = {n for n in _import_names(code) if n.split(".")[0] not in sys.builtin_module_names}
    resolved = []
    for name in names:
        spec = _resolve(name, search)
        if spec and spec.origin:
            resolved.append(Path(spec.origin).resolve())
    return resolved


def _resolve_js_like(module_path: Path, raw_import_text: str, root: Path) -> list[Path]:
    """Relative specifiers only - bare specifiers (react, @angular/core) are external and
    dropped. Full tsconfig.json path-alias resolution is out of scope."""
    specifier = _extract_specifier(raw_import_text)
    if specifier is None or not specifier.startswith("."):
        return []
    base = (module_path.parent / specifier).resolve()
    candidates = [base] if base.suffix else []
    for ext in _JS_EXTENSION_PROBE:
        candidates.append(base.with_suffix(ext) if not base.suffix else base)
        candidates.append(base / f"index{ext}")
    for candidate in candidates:
        if candidate.is_file():
            return [candidate]
    return []


def _extract_specifier(raw_import_text: str) -> str | None:
    for quote in ('"', "'"):
        if quote in raw_import_text:
            parts = raw_import_text.split(quote)
            if len(parts) >= 2:
                return parts[1]
    return None


def _resolve_java(raw_import_text: str, root: Path, java_src_roots: list[Path]) -> list[Path]:
    dotted = raw_import_text.replace("import", "", 1).strip().rstrip(";").strip()
    dotted = dotted.removeprefix("static ").strip()
    parts = dotted.split(".")
    if parts and parts[-1] == "*":
        return []
    rel_path = Path(*parts).with_suffix(".java")
    for src_root in {*java_src_roots, root}:
        candidate = (src_root / rel_path).resolve()
        if candidate.is_file():
            return [candidate]
    return []


def resolve_edges(
    files: dict[str, "codelexity.languages.base.LanguageAnalyzer"],  # noqa: F821 - forward ref, see multi_lang.py
    root: Path,
    raw_imports: dict[str, list[str]],
    csharp_namespaces: dict[str, list[str]] | None = None,
    search_dirs: list[Path] | None = None,
) -> dict[str, set[str]]:
    """importer_posix_path -> set(imported_posix_paths), resolved per-language, external
    imports dropped. `files` maps posix path -> Language value; `raw_imports` maps posix
    path -> the raw import specifier texts collected by each LanguageAnalyzer.
    `search_dirs`, when given, is the already-discovered (and exclude-pruned) list of
    directories under `root` - passed in by multi_lang.py, which walks the tree once
    anyway for file discovery, so Python/Java resolution below can reuse it instead of
    each re-walking the whole tree per file. Falls back to a plain `root.rglob("*")` if
    not given, matching the old behavior for any other caller."""
    edges: dict[str, set[str]] = defaultdict(set)
    csharp_namespaces = csharp_namespaces or {}
    namespace_to_files: dict[str, list[str]] = defaultdict(list)
    for file, namespaces in csharp_namespaces.items():
        for ns in namespaces:
            namespace_to_files[ns].append(file)

    if search_dirs is None:
        search_dirs = [p for p in root.rglob("*") if p.is_dir()]
    python_search = [root, *search_dirs]
    java_src_roots = [d for d in search_dirs if d.name == "java"]

    for file, language in files.items():
        module_path = Path(file)
        targets: set[Path] = set()
        if language == "python":
            targets.update(_resolve_python(module_path, python_search))
        else:
            for raw in raw_imports.get(file, []):
                if language in ("javascript", "typescript"):
                    targets.update(_resolve_js_like(module_path, raw, root))
                elif language == "java":
                    targets.update(_resolve_java(raw, root, java_src_roots))
                elif language == "csharp":
                    using_name = raw.replace("using", "", 1).strip().rstrip(";").strip()
                    for target_file in namespace_to_files.get(using_name, []):
                        if target_file != file:
                            edges[file].add(target_file)
        for target in targets:
            target_posix = target.as_posix()
            if target_posix != file:
                edges[file].add(target_posix)
    return dict(edges)


def module_coupling(resolved_edges: dict[str, set[str]], all_files: list[str]) -> dict[str, int]:
    """Incoming reference count (fan-in) per file. Every file gets an explicit entry,
    including 0, so downstream scoring never treats a missing key as "unknown"."""
    incoming: Counter = Counter({f: 0 for f in all_files})
    for _importer, targets in resolved_edges.items():
        for target in targets:
            incoming[target] += 1
    return dict(incoming)
