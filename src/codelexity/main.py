import argparse
from codelexity.graph import create_graph
from codelexity.calculations import analyze_package
from pathlib import Path
import json

HTML_NAME = "codelexity.html"
JSON_NAME = "codelexity.json"

parser = argparse.ArgumentParser(description="Codelexity helps you measure and visualize the complexity of your code.")

parser.add_argument("filepath", help="The path to the code you want to process.")
parser.add_argument("-of", "--output-file", action="store_true", help=f"Store the codelexity data in a json file `{JSON_NAME}` in the current directory.")
parser.add_argument("-og", "--output-graph", action="store_true", help=f"Store the codelexity interactive plot in an html file `{HTML_NAME}` in the current directory.")

args = parser.parse_args()


def main():
    #find and resolve path
    path = Path(args.filepath).resolve()
    print(f"Analyzing code in : {path.as_posix()}")
    
    if not path.exists():
        raise FileNotFoundError(f"Could not locate: {args.filepath}")
    
    #analyze code
    data = analyze_package(path)

    if args.output_graph:
        create_graph(data, HTML_NAME)
        print(f"Interactive plot saved in: `{Path(HTML_NAME).resolve().as_posix()}`")

    if args.output_file:
        Path("codelexity.json").write_text(json.dumps(data, indent=4), encoding = "utf-8")
    
    if not (args.output_graph or args.output_file):
        print(json.dumps(data, indent=4))
    


if __name__ == "__main__":
    main()