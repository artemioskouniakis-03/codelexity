from collections import Counter, defaultdict
from pathlib import Path

_JS_EXTENSION_PROBE = (".ts", ".tsx", ".js", ".jsx")


def _resolve_python(module_path: Path, raw_import_text: str, root: Path) -> list[Path]:
    """Reuses the existing calculations.imports() machinery unchanged."""
    from codelexity.calculations import imports as existing_imports

    del raw_import_text  # Python resolution works from the compiled module, not per-import text
    return [Path(p) for p in existing_imports(module_path, root=root)]


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


def _resolve_java(module_path: Path, raw_import_text: str, root: Path) -> list[Path]:
    dotted = raw_import_text.replace("import", "", 1).strip().rstrip(";").strip()
    dotted = dotted.removeprefix("static ").strip()
    parts = dotted.split(".")
    if parts and parts[-1] == "*":
        return []
    rel_path = Path(*parts).with_suffix(".java")
    for src_root in {p for p in root.rglob("java") if p.is_dir()} | {root}:
        candidate = (src_root / rel_path).resolve()
        if candidate.is_file():
            return [candidate]
    return []


def resolve_edges(
    files: dict[str, "codelexity.languages.base.LanguageAnalyzer"],  # noqa: F821 - forward ref, see multi_lang.py
    root: Path,
    raw_imports: dict[str, list[str]],
    csharp_namespaces: dict[str, list[str]] | None = None,
) -> dict[str, set[str]]:
    """importer_posix_path -> set(imported_posix_paths), resolved per-language, external
    imports dropped. `files` maps posix path -> Language value; `raw_imports` maps posix
    path -> the raw import specifier texts collected by each LanguageAnalyzer."""
    edges: dict[str, set[str]] = defaultdict(set)
    csharp_namespaces = csharp_namespaces or {}
    namespace_to_files: dict[str, list[str]] = defaultdict(list)
    for file, namespaces in csharp_namespaces.items():
        for ns in namespaces:
            namespace_to_files[ns].append(file)

    for file, language in files.items():
        module_path = Path(file)
        targets: set[Path] = set()
        if language == "python":
            targets.update(_resolve_python(module_path, "", root))
        else:
            for raw in raw_imports.get(file, []):
                if language in ("javascript", "typescript"):
                    targets.update(_resolve_js_like(module_path, raw, root))
                elif language == "java":
                    targets.update(_resolve_java(module_path, raw, root))
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
