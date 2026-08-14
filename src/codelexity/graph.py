from collections.abc import Iterable
import networkx as nx
from pyvis.network import Network
from pathlib import Path
import json

def node_data(data:dict):
    return json.dumps(data)

node_size = lambda num: max(min(num**0.42,35),2)

def create_graph(package_data: dict, fpath: str):
    G = nx.DiGraph()
    for module, data in package_data.items():
        G.add_node(module, title= node_data(data), size = node_size(data['total_lines']))
    for module, data in package_data.items():
        for imported in data['imports']:
            G.add_edge(imported, module)

    net = Network(height="600px", width="100%",notebook=False,directed=True)
    net.from_nx(G)
    net.save_graph(fpath)
