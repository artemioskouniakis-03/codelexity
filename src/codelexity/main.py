import argparse
import json
from pathlib import Path

from codelexity.calculations import analyze_package, shorten
from codelexity.graph import create_viz

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

args = parser.parse_args()
print(args)


def main():
    # find and resolve path
    path = Path(args.filepath).resolve()
    print(f"Analyzing code in : {path.as_posix()}")

    if not path.exists():
        raise FileNotFoundError(f"Could not locate: {args.filepath}")

    # analyze code
    data = analyze_package(path, exclude=args.exclude, include_only=args.include_only)

    if not args.absolute:
        # Keys and imports shortened together — create_graph matches edges between the two.
        data["modules"] = {
            shorten(Path(mod), path): {**d, "imports": [shorten(Path(i), path) for i in d["imports"]]}
            for mod, d in data["modules"].items()
        }

    if args.plot:
        create_viz(data, HTML_NAME)
        print(f"Interactive plot saved in: `{Path(HTML_NAME).resolve().as_posix()}`")

    if args.json:
        Path("codelexity.json").write_text(json.dumps(data, indent=4), encoding="utf-8")

    if not (args.plot or args.json):
        print(json.dumps(data, indent=4))


if __name__ == "__main__":
    main()
