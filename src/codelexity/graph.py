from collections.abc import Iterable
import networkx as nx
from pyvis.network import Network
from pathlib import Path
import json

def node_data(data:dict):
    return "\n- ".join(f"{d}: {v}" for d,v in data.items() if isinstance(v, str | int | float))

node_size = lambda num:  max(min(num**.5,50),3)

def create_graph(package_data: dict, fpath: str):
    G = nx.DiGraph()
    for i, (module, data) in enumerate(package_data.items()):
        G.add_node(module, label=module.split('/')[-1], title= node_data({"path": module, **data}), size = node_size(data['total_lines']))
    for module, data in package_data.items():
        for imported in data['imports']:
            if imported not in G.nodes:
                G.add_node(imported, label=imported.split("/")[-1])
            G.add_edge(imported, module)

    net = Network(height="600px", width="100%",notebook=False,directed=True)
    net.from_nx(G)
    net.save_graph(fpath)
