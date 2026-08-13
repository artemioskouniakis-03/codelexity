from collections.abc import Iterable
import networkx as nx
from pyvis.network import Network
from pathlib import Path

def node_data(data:dict):
    return "\n".join(f"{k}: {v}" for k,v in data.items() if not isinstance(v, Iterable))

def node_size(total_length: int, range: int):
    minnode, maxnode = 10, 50
    return minnode + max(int(total_length/range),1)*(maxnode-minnode)

def create_graph(module_data: dict):
    G = nx.DiGraph()
    for module, data in module_data.items():
        G.add_node(module, label=node_data(data), size = node_size(data['total_lines'], 10, 1000))
    for module, data in module_data.items():
        for imported in data['imports']:
            pass

    net = Network(height="600px", width="100%",notebook=False,directed=True)
    net.from_nx(G)
    html_string = net.generate_html()
