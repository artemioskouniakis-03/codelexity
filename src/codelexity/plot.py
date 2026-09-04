from pathlib import Path

import networkx as nx
from pyvis.network import Network

from codelexity.graph import mi_color


def create_viz(package_data: dict, G: nx.DiGraph, fpath: str):

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
        f"background:{mi_color(package_data['analytics']['maintainability_index'])}"
        ';color:#333;padding:2px 10px;border-radius:2px;">'
        f"Maintainability: {package_data['analytics']['maintainability_index']}%</div><br>"
        f"Total lines of code: {package_data['analytics']['total_lines']}<br>"
        f"Total modules: {package_data['analytics']['total_modules']}<br>"
        f"Total functions/methods: {package_data['analytics']['total_functions']}<br>"
        f"Total comprehension time (h): {package_data['analytics']['total_man_hours']}</div>"
    )
    path = Path(fpath)
    html = path.read_text(encoding="utf-8")
    path.write_text(html.replace("<body>", f"<body>\n{legend}", 1), encoding="utf-8")
