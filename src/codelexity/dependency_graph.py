from collections import Counter
from pathlib import Path

import networkx as nx
from pyvis.network import Network

from codelexity.models import AnalysisResult

NODE_COLOR = "#6c9ef8"
EDGE_COLOR = "#9aa5b1"


def build_file_graph(analysis: AnalysisResult) -> nx.DiGraph:
    """One node per file, one directed edge per (importer -> imported) resolved import.
    A mutual dependency (A imports B and B imports A) becomes two separate directed
    edges, each rendered with its own arrowhead - "arrows for both incoming and outgoing
    calls" falls directly out of this being a real directed graph, not a heuristic."""
    graph = nx.DiGraph()
    file_by_path = {f.file: f for f in analysis.files}
    for file_metric in analysis.files:
        graph.add_node(
            file_metric.file,
            label=Path(file_metric.file).name,
            title=file_metric.file,
            group=file_metric.component,
            size=max(min(file_metric.loc**0.5, 40), 5),
        )
    for importer, imported in analysis.edges:
        if importer in file_by_path and imported in file_by_path and importer != imported:
            graph.add_edge(importer, imported, color=EDGE_COLOR)
    return graph


def build_component_graph(analysis: AnalysisResult) -> nx.DiGraph:
    """One node per component, one directed edge per distinct (component -> component)
    pair with at least one cross-component file dependency - edge width scales with how
    many underlying file-level dependencies it represents."""
    graph = nx.DiGraph()
    for component in analysis.components:
        graph.add_node(
            component.name,
            label=component.name,
            title=f"{component.name} ({component.file_count} files, {component.loc} LOC)",
            size=max(min(component.loc**0.5, 60), 10),
        )
    file_to_component = {f.file: f.component for f in analysis.files}
    pair_counts: Counter[tuple[str, str]] = Counter()
    for importer, imported in analysis.edges:
        src = file_to_component.get(importer)
        dst = file_to_component.get(imported)
        if src is not None and dst is not None and src != dst:
            pair_counts[(src, dst)] += 1
    for (src, dst), count in pair_counts.items():
        graph.add_edge(src, dst, value=count, title=f"{count} file-level dependencies", color=EDGE_COLOR)
    return graph


def render_graph_html(graph: nx.DiGraph, height: str = "600px") -> str:
    """Returns the graph as a full, self-contained standalone HTML page (string, not
    written to disk) - meant to be embedded via an iframe's `srcdoc` attribute rather
    than referenced by a sibling file path, since the latter breaks once the report is
    shown inline (Streamlit's st.components.v1.html renders via srcdoc, which has no
    base URL for a relative file reference to resolve against)."""
    net = Network(height=height, width="100%", directed=True, notebook=False)
    net.from_nx(graph)
    net.set_options("""
        var options = {
          "physics": { "maxVelocity": 5 },
          "edges": { "arrows": { "to": { "enabled": true } }, "smooth": { "type": "curvedCW", "roundness": 0.15 } }
        }
        """)
    return net.generate_html()
