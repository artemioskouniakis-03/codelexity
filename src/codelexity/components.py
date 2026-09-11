from collections import Counter, defaultdict
from pathlib import Path


def component_for(file_path: str, root: Path, depth: int) -> str:
    if depth == 0:
        return "."  # whole repo is one component
    rel_parts = Path(file_path).relative_to(root).parts[:-1]  # directory parts only, drop filename
    if len(rel_parts) <= depth:
        return "/".join(rel_parts) if rel_parts else "."
    return "/".join(rel_parts[:depth])


def component_edges(
    resolved_edges: dict[str, set[str]], component_of: dict[str, str]
) -> tuple[dict[str, int], dict[str, int]]:
    """Cross-component-only Ce (efferent, outgoing) / Ca (afferent, incoming) per component.
    Intra-component edges are ignored so independence measures only external coupling,
    never internal cohesion (Martin's separation of concerns)."""
    ce: Counter = Counter()
    ca: Counter = Counter()
    for importer, targets in resolved_edges.items():
        src = component_of.get(importer)
        if src is None:
            continue
        for target in targets:
            dst = component_of.get(target)
            if dst is None or dst == src:
                continue
            ce[src] += 1
            ca[dst] += 1
    return dict(ce), dict(ca)


def independence(ce: int, ca: int) -> float:
    """1 - Martin's Instability (Ce/(Ce+Ca)). A fully isolated component (no cross-
    component edges at all) is maximally independent, not undefined."""
    if ce + ca == 0:
        return 1.0
    return 1.0 - (ce / (ce + ca))


def group_files_by_component(files: list[str], root: Path, depth: int) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for file in files:
        grouped[component_for(file, root, depth)].append(file)
    return dict(grouped)
