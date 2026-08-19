from pathlib import Path

import networkx as nx
from pyvis.network import Network


def node_data(data: dict):
    return "\n-".join(f"{k}: {v}" for k, v in data.items() if isinstance(v, (str, int, float)))


node_size = lambda num: max(min(num**0.5, 50), 3)

MI_BANDS = ((60, "#97c2fc89"), (20, "#ccb7b789"), (0, "#d0515189"))


def mi_color(score):
    """Position on the light blue -> gray -> red ramp: healthy blue, middling gray, poor red."""
    for threshold, colour in MI_BANDS:
        if score >= threshold:
            return colour
    return MI_BANDS[-1][-1]


def create_graph(package_data: dict):
    G = nx.DiGraph()
    for i, (module, data) in enumerate(package_data["modules"].items()):
        G.add_node(
            module,
            label=module.split("/")[-1],
            title=node_data({"path": module, **data}),
            size=node_size(data["total_lines"]),
            maintainability=data["maintainability_index"],
            color=mi_color(data["maintainability_index"]),
        )
    for module, data in package_data["modules"].items():
        for imported in data["imports"]:
            # Only edges between analyzed modules. analyze_package stops at depth 1, so deeper
            # imports have no metrics; add_edge would invent attribute-less nodes for them.
            if imported in package_data["modules"]:
                G.add_edge(imported, module)
    return G


def maintainability(G, damping=0.5):
    """0-100. Importance-weighted mean of raw MI over the modules that carry data."""
    # Edges pull in transitive imports that were never analyzed, so they have no attributes.
    try:
        centrality = nx.katz_centrality(G.reverse(copy=True), alpha=damping)
    except nx.PowerIterationFailedConvergence:
        print("Failed to converge!")
        centrality = dict.fromkeys(G, 1.0)
    weights = {n: G.nodes[n]["size"] * centrality[n] for n in G.nodes}  # weight by size and centrality
    weights = {n: v / sum(weights.values()) for n, v in weights.items()}
    adjusted_m = [G.nodes[n]["maintainability"] * weights[n] for n in G.nodes]
    return sum(adjusted_m)


def create_viz(package_data: dict, fpath: str):
    G = create_graph(package_data=package_data)
    maintainability_score = int(round(maintainability(G)))

    net = Network(
        height="600px",
        width="100%",
        notebook=False,
        directed=True,
    )
    net.from_nx(G)
    net.set_options("""
        var options = {
        "physics": {
            "maxVelocity": 5
        }
        }
        """)
    net.save_graph(fpath)

    legend = (
        '<div style="position:fixed;top:10px;left:10px;background:#fff;'
        "border:1px solid #ccc;padding:8px 12px;"
        "font-family:ui-monospace,Consolas,monospace;"
        'letter-spacing:0.2px;font-size:14px;z-index:1000;">'
        '<div style="font-size:20px;margin-bottom:6px;">Codelexity</div>'
        f'<div style="font-size:15px;margin-bottom:4px;display:inline-block;'
        f'background:{mi_color(maintainability_score)};color:#333;padding:2px 10px;border-radius:2px;">'
        f"Maintainability: {maintainability_score}%</div><br>"
        f"Total lines of code: {package_data['analytics']['total_lines']}<br>"
        f"Total modules: {package_data['analytics']['total_modules']}<br>"
        f"Total functions/methods: {package_data['analytics']['total_functions']}<br>"
        f"Total comprehension time (h): {package_data['analytics']['total_man_hours']}</div>"
    )
    path = Path(fpath)
    path.write_text(path.read_text().replace("<body>", f"<body>\n{legend}", 1))
