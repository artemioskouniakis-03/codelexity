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
        )
    for module, data in package_data["modules"].items():
        for imported in data["imports"]:
            if imported not in G.nodes:
                G.add_node(imported, label=imported.split("/")[-1])
            G.add_edge(imported, module)
    return G


def propagate_complexity(graph: nx.DiGraph):
    pass


def create_viz(package_data: dict, fpath: str):
    G = create_graph(package_data=package_data)

    net = Network(height="600px", width="100%", notebook=False, directed=True)
    net.from_nx(G)
    net.save_graph(fpath)

    legend = (
        '<div style="position:fixed;top:10px;left:10px;background:#fff;'
        "border:1px solid #ccc;padding:8px 12px;font-family:sans-serif;"
        'font-size:14px;z-index:1000;">'
        '<div style="font-size:22px;font-weight:bold;margin-bottom:6px;">Codelexity Analysis</div>'
        f"<b>Total lines of code:</b> {package_data['analytics']['total_lines']}<br>"
        f"<b>Total modules:</b> {package_data['analytics']['total_modules']}<br>"
        f"<b>Total functions/methods:</b> {package_data['analytics']['total_functions']}</div>"
    )
    path = Path(fpath)
    path.write_text(path.read_text().replace("<body>", f"<body>\n{legend}", 1))
