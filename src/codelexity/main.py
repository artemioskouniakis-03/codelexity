import argparse
import json
import sys
from pathlib import Path

from codelexity.calculations import analyze_package, shorten
from codelexity.graph import create_graph, maintainability
from codelexity.plot import create_viz

HTML_NAME = "codelexity.html"
JSON_NAME = "codelexity.json"

parser = argparse.ArgumentParser(description="Codelexity helps you measure and visualize the complexity of your code.")

parser.add_argument("filepath", help="The path to the code you want to process.")
parser.add_argument(
    "-j",
    "--json",
    action="store_true",
    help=f"Store the codelexity data in a json file `{JSON_NAME}` in the current directory.",
)
parser.add_argument(
    "-p",
    "--plot",
    action="store_true",
    help=f"Store the codelexity interactive plot in an html file `{HTML_NAME}` in the current directory.",
)
parser.add_argument(
    "-i", "--include-only", nargs="+", type=str, default=(), help="Provide the list of packages/modules to be included."
)
parser.add_argument(
    "-e",
    "--exclude",
    nargs="+",
    type=str,
    default=(".venv", "bin"),
    help="Provide a list of packages/modules to exclude.",
)
parser.add_argument("-a", "--absolute", action="store_true", help="If added all paths will be absolute.")
parser.add_argument(
    "--max",
    nargs=2,
    action="append",
    default=[],
    metavar=("KEY", "VALUE"),
    help="Exit non-zero if this analytics value exceeds VALUE, e.g. `--max total_lines 500`. Repeatable.",
)
parser.add_argument(
    "--min",
    nargs=2,
    action="append",
    default=[],
    metavar=("KEY", "VALUE"),
    help="Exit non-zero if this analytics value falls below VALUE, e.g. `--min maintainability_index 40`. Repeatable.",
)


def main():
    args = parser.parse_args()

    # find and resolve path
    path = Path(args.filepath).resolve()
    print(f"Analyzing code in : {path.as_posix()}")

    if not path.exists():
        raise FileNotFoundError(f"Could not locate: {args.filepath}")

    # analyze code
    data = analyze_package(path, exclude=args.exclude, include_only=args.include_only)
    G = create_graph(package_data=data)
    maintainability_index = maintainability(G)
    data["analytics"]["maintainability_index"] = maintainability_index

    if not args.absolute:
        # Keys and imports shortened together - create_graph matches edges between the two.
        data["modules"] = {
            shorten(Path(mod), path): {**d, "imports": [shorten(Path(i), path) for i in d["imports"]]}
            for mod, d in data["modules"].items()
        }

    if args.plot:
        create_viz(data, G, HTML_NAME)
        print(f"Interactive plot saved in: `{Path(HTML_NAME).resolve().as_posix()}`")

    if args.json:
        Path("codelexity.json").write_text(json.dumps(data, indent=4), encoding="utf-8")

    if not (args.plot or args.json):
        print(data["analytics"])

    sys_exit = ""
    for limit in ["max", "min"]:
        for key, value in vars(args)[limit]:
            key_ = key if key in data["analytics"] else key.replace("-", "_")
            if key_ not in data["analytics"]:
                print(f"skipping {key_}")
                continue
            if limit == "max" and data["analytics"][key_] > float(value):
                sys_exit += f"{key} {data['analytics'][key_]} exceeds the maximum allowed value of {value}\n"
            elif limit == "min" and data["analytics"][key_] < float(value):
                sys_exit += f"{key} {data['analytics'][key_]} is below the minimum allowed value of {value}\n"
    if sys_exit:
        sys.exit(sys_exit)


if __name__ == "__main__":
    main()
