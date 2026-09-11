import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx
from pyvis.network import Network

from codelexity.models import AnalysisResult

EDGE_COLOR = "#9aa5b1"

# A categorical palette for per-component node coloring in the file-level graph -
# deliberately distinct from the report's risk-band colors (green/yellow/orange/red)
# so the two color systems are never confused for one another. Cycles if there are more
# components than colors.
COMPONENT_PALETTE = (
    "#4C78A8",
    "#F58518",
    "#54A24B",
    "#B279A2",
    "#E45756",
    "#72B7B2",
    "#EECA3B",
    "#9D755D",
    "#BAB0AC",
    "#FF9DA6",
)

_HEAD_RE = re.compile(r"<head>(.*)</head>", re.DOTALL)
_BODY_RE = re.compile(r"<body>(.*)</body>", re.DOTALL)


@dataclass(frozen=True, slots=True)
class GraphFragment:
    head: str  # extra <link>/<script>/<style> tags - injected into the report's own <head>
    body: str  # the graph container div + its setup <script> - injected into the report's body


@dataclass(frozen=True, slots=True)
class FileGraph:
    graph: nx.DiGraph
    legend: tuple[tuple[str, str], ...] = field(default_factory=tuple)  # (component name, hex color), sorted


def build_file_graph(analysis: AnalysisResult) -> FileGraph:
    """One node per file, one directed edge per (importer -> imported) resolved import.
    A mutual dependency (A imports B and B imports A) becomes two separate directed
    edges, each rendered with its own arrowhead - "arrows for both incoming and outgoing
    calls" falls directly out of this being a real directed graph, not a heuristic.

    Nodes are colored by component (a deterministic palette assigned here, not
    vis-network's own automatic per-"group" coloring) precisely so the returned legend
    can tell a viewer which color means which component - vis-network's internal group
    color choices aren't something this code can read back to build a legend from."""
    components = sorted({f.component for f in analysis.files})
    color_by_component = {c: COMPONENT_PALETTE[i % len(COMPONENT_PALETTE)] for i, c in enumerate(components)}

    graph = nx.DiGraph()
    file_by_path = {f.file: f for f in analysis.files}
    for file_metric in analysis.files:
        graph.add_node(
            file_metric.file,
            label=Path(file_metric.file).name,
            title=f"{file_metric.file}\ncomponent: {file_metric.component}",
            color=color_by_component[file_metric.component],
            size=max(min(file_metric.loc**0.5, 40), 5),
        )
    for importer, imported in analysis.edges:
        if importer in file_by_path and imported in file_by_path and importer != imported:
            graph.add_edge(importer, imported, color=EDGE_COLOR)

    legend = tuple((c, color_by_component[c]) for c in components)
    return FileGraph(graph=graph, legend=legend)


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


# File-level graphs can have many small nodes - a modest anti-overlap nudge is enough.
# Component-level graphs are usually just a handful of much bigger nodes, which need
# considerably more breathing room or they clump into an unreadable knot in the middle -
# a much longer spring length, weaker central pull, and a strong overlap-avoidance push.
_FILE_GRAPH_OPTIONS = """
    var options = {
      "physics": {
        "maxVelocity": 5,
        "barnesHut": { "springLength": 130, "avoidOverlap": 0.6 }
      },
      "edges": {
        "arrows": { "to": { "enabled": true } },
        "smooth": { "type": "curvedCW", "roundness": 0.15 }
      }
    }
    """
_COMPONENT_GRAPH_OPTIONS = """
    var options = {
      "physics": {
        "solver": "barnesHut",
        "barnesHut": {
          "gravitationalConstant": -12000,
          "centralGravity": 0.15,
          "springLength": 320,
          "springConstant": 0.02,
          "damping": 0.5,
          "avoidOverlap": 1
        },
        "stabilization": { "iterations": 300 }
      },
      "edges": {
        "width": 2,
        "arrows": { "to": { "enabled": true } },
        "smooth": { "type": "curvedCW", "roundness": 0.15 }
      },
      "nodes": {
        "font": { "size": 16 }
      }
    }
    """


def render_graph_html(graph: nx.DiGraph, height: str = "600px", spacious: bool = False) -> str:
    """Returns the graph as a full, standalone HTML page (string, not written to disk).
    Kept for direct/standalone use; the report embeds render_graph_fragment() instead -
    see its docstring for why. `spacious=True` (used for the component-level view, far
    fewer/larger nodes) trades a longer physics settle time for much clearer spacing;
    the file-level view keeps tighter default spacing since it can have many nodes."""
    net = Network(height=height, width="100%", directed=True, notebook=False)
    net.from_nx(graph)
    net.set_options(_COMPONENT_GRAPH_OPTIONS if spacious else _FILE_GRAPH_OPTIONS)
    # local=False: without it, pyvis's own small interaction-helper script
    # (lib/bindings/utils.js) is referenced as a bare relative path with nothing to
    # resolve it against once this stops being a real file on disk - harmless on its own
    # (a 404 on an external <script> doesn't halt the page), but avoided anyway since
    # there's no reason to keep a dangling reference once we're not writing files.
    return net.generate_html(local=False)


def render_graph_fragment(graph: nx.DiGraph, height: str = "600px", spacious: bool = False) -> GraphFragment:
    """Extracts the <head> extras (CDN links, sizing <style>) and <body> content (the
    graph container div + its vis-network setup <script>) from pyvis's generated page,
    for embedding directly into the report's own document instead of through a nested
    iframe. An earlier version embedded the full page via <iframe srcdoc="...">, which
    rendered blank: Streamlit's st.components.v1.html already renders the whole report
    inside its own sandboxed srcdoc iframe, and a plain nested <iframe srcdoc> inside a
    sandboxed browsing context does not reliably inherit the permissions needed to
    execute scripts - so vis-network's setup script never ran. Embedding in the same
    document sidesteps that entirely; there's only ever one graph per report, so the
    fixed `#mynetwork` id pyvis emits doesn't need to be namespaced."""
    html = render_graph_html(graph, height=height, spacious=spacious)
    head_match = _HEAD_RE.search(html)
    body_match = _BODY_RE.search(html)
    head = head_match.group(1) if head_match else ""
    body = body_match.group(1) if body_match else html
    # Defensive: node/component titles and labels are derived from repo file/folder
    # names, which - unlike everything else on this page - come from data outside our
    # control. A pathological file name containing a literal "</script>" could otherwise
    # break out of pyvis's inline setup script now that it shares this page's document
    # (a nested iframe's srcdoc would have isolated this; a same-document embed doesn't).
    # Only escape occurrences BEFORE the real closing tag - there's exactly one genuine
    # <script>...</script> block here (pyvis's drawGraph setup), so its own closing tag
    # must survive untouched or the fragment breaks; any "</script" appearing earlier can
    # only be embedded string data, never legitimate markup.
    last_close = body.rfind("</script>")
    if last_close != -1:
        body = body[:last_close].replace("</script", "<\\/script") + body[last_close:]
    return GraphFragment(head=head, body=body)
