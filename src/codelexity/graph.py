import networkx as nx

MI_BANDS = ((60, "#97c2fc89"), (20, "#ccb7b789"), (0, "#d0515189"))

node_size = lambda num: max(min(num**0.5, 50), 3)


def node_data(data: dict):
    return "\n-".join(f"{k}: {v}" for k, v in data.items() if isinstance(v, (str, int, float)))


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
            if imported in package_data["modules"]:
                G.add_edge(imported, module)
    return G


def maintainability(G, damping=0.25):
    """0-100. Importance-weighted mean of raw MI over the modules that carry data."""
    try:
        centrality = nx.katz_centrality(G.reverse(copy=True), alpha=damping)
    except nx.PowerIterationFailedConvergence:
        print("Failed to converge!")
        centrality = dict.fromkeys(G, 1.0)
    weights = {n: G.nodes[n]["size"] * centrality[n] for n in G.nodes}  # weight by size and centrality
    weights = {n: v / sum(weights.values()) for n, v in weights.items()}
    adjusted_m = [G.nodes[n]["maintainability"] * weights[n] for n in G.nodes]
    return round(sum(adjusted_m), 1)


def coupling(G, package_data):
    """0-1 Average fraction of the codebase's lines that transitively depend on a single module."""
    modules = package_data["modules"]
    total_lines = sum(d["code_length"] for d in modules.values())
    if total_lines == 0:
        return 0.0
    reach_fractions = [
        sum(modules[m]["code_length"] for m in nx.descendants(G, module)) / total_lines for module in modules
    ]
    return sum(reach_fractions) / len(reach_fractions)
