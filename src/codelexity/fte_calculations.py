import json
import random
from functools import lru_cache


@lru_cache(500)
def dependency_percentage(package_data_json: str, child: str, parent: str):
    package_data = json.loads(package_data_json)
    parents = package_data["modules"][child]["imports"]
    if not parents:
        return 0
    return package_data["modules"][parent]["code_length"] / (
        sum(package_data["modules"][p]["code_length"] for p in parents)
    )


@lru_cache(500)
def children(package_data_json: str, parent: str):
    package_data = json.loads(package_data_json)
    return list({m for m in package_data["modules"] if parent in package_data["modules"][m]["imports"]})


def sample_initial_module(package_data: dict):
    modules = [m for m in package_data["modules"] if package_data["modules"][m]["contained_function_length"]]
    lines = [package_data["modules"][m]["code_length"] for m in modules]
    return random.choices(modules, weights=[w / sum(lines) for w in lines], k=1)[0]


def child_broke(package_data: dict, parent: str, child: str):
    dep_perc = dependency_percentage(json.dumps(package_data), parent, child)
    return random.random() < dep_perc


def sample_function(package_data: dict, module: str):
    lines = [f for f in package_data["modules"][module]["contained_function_length"]]
    if not lines:
        return 0
    return random.choices(lines, weights=[w / sum(lines) for w in lines], k=1)[0]


def simulate(package_data: dict, n_scenarios=1000):
    package_data_json = json.dumps(package_data)
    total_lines_affected = []
    for i in range(n_scenarios):
        modules_affected = [sample_initial_module(package_data)]
        scenario_lines_affected = 0
        j = 0
        while modules_affected:
            current_module = modules_affected.pop()

            # sample a function from current module
            scenario_lines_affected += sample_function(package_data, current_module)

            for child in children(package_data_json, current_module):
                if child_broke(package_data, parent=current_module, child=child):
                    modules_affected.append(child)
            j += 1
        print(f"scenario {i}: complete - lines affected : {scenario_lines_affected}")
        total_lines_affected.append(scenario_lines_affected)
    return total_lines_affected
