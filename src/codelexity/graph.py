from pathlib import Path

import networkx as nx
from pyvis.network import Network


def node_data(data: dict):
    return "\n- ".join(f"{d}: {v}" for d, v in data.items() if isinstance(v, str | int | float))


node_size = lambda num: max(min(num**0.5, 50), 3)


def create_graph(package_data: dict):
    G = nx.DiGraph()
    for i, (module, data) in enumerate(package_data["modules"].items()):
        G.add_node(
            module,
            label=module.split("/")[-1],
            title=node_data({"path": module, **data}),
            size=node_size(data["total_lines"]),
            maintainability=data["maintainability_index"],
        )
    for module, data in package_data["modules"].items():
        for imported in data["imports"]:
            G.add_edge(imported, module)
    return G


MI_BANDS = ((65, "#2e7d32"), (40, "#f9a825"))  # first threshold met wins; below all -> red


def mi_color(score):
    return next((colour for threshold, colour in MI_BANDS if score >= threshold), "#c62828")


def maintainability(G, damping=0.5):
    """0-100. Importance-weighted mean of raw MI over the modules that carry data."""
    # Edges pull in transitive imports that were never analyzed, so they have no attributes.
    scored = [n for n in G if "maintainability" in G.nodes[n]]
    if not scored:
        return 100.0
    try:
        centrality = nx.katz_centrality(G.reverse(copy=True), alpha=damping)
    except nx.PowerIterationFailedConvergence:
        # ponytail: alpha=0.5 is near the convergence bound for dense graphs. Fall back to
        # size-only weighting rather than crash the whole viz; lower `damping` for a real fix.
        centrality = dict.fromkeys(G, 1.0)
    w = {n: G.nodes[n]["size"] * centrality[n] for n in scored}
    return round(sum(w[n] * G.nodes[n]["maintainability"] for n in scored) / sum(w.values()), 1)


def create_viz(package_data: dict, fpath: str):
    G = create_graph(package_data=package_data)
    maintainability_score = int(round(maintainability(G)))

    net = Network(height="600px", width="100%", notebook=False, directed=True)
    net.from_nx(G)
    net.save_graph(fpath)

    legend = (
        '<div style="position:fixed;top:10px;left:10px;background:#fff;'
        "border:1px solid #ccc;padding:8px 12px;font-family:sans-serif;"
        'font-size:14px;z-index:1000;">'
        '<div style="font-size:22px;font-weight:bold;margin-bottom:6px;">Codelexity Analysis</div>'
        f'<div style="font-size:18px;font-weight:bold;margin-bottom:6px;'
        f'color:{mi_color(maintainability_score)};">Maintainability: {maintainability_score}%</div>'
        f"<b>Total lines of code:</b> {package_data['analytics']['total_lines']}<br>"
        f"<b>Total modules:</b> {package_data['analytics']['total_modules']}<br>"
        f"<b>Total functions/methods:</b> {package_data['analytics']['total_functions']}</div>"
    )
    path = Path(fpath)
    path.write_text(path.read_text().replace("<body>", f"<body>\n{legend}", 1))
