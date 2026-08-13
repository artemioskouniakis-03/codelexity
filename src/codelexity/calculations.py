from pathlib import Path
import re
import ast
import importlib


MULTILINE_COMMENTS = re.compile(r"^[\t ]*\"\"\".*?\"\"\"|^[\t ]*'''.*?'''", re.DOTALL | re.MULTILINE)
SINGLE_LINE_COMMENTS = re.compile(r"^[ \t]*#", re.MULTILINE)
EMPTY_LINES = re.compile("^[ \t]*$", re.MULTILINE)

def empty_lines(string: str):
    return re.findall(EMPTY_LINES, string)

def comments_and_docstrings(string: str):
    return re.findall(SINGLE_LINE_COMMENTS, string) + re.findall(MULTILINE_COMMENTS, string)

def functions(string):
    tree = ast.parse(string)
    fns = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fns.append(ast.get_source_segment(string, node))
    return fns

def imports(string, relative_to = None):
    tree = ast.parse(string)
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                path = importlib.util.find_spec(alias.name).origin
                out.add(path)
        elif isinstance(node, ast.ImportFrom):
            path = importlib.util.find_spec(node.module).origin
            out.add(path)
    if relative_to:
       out = sorted([path for path in out if Path(path).is_relative_to(relative_to)])
    return sorted(out)

def analyze_module(path, relative_to = None):
    pth = Path(path).resolve()
    print(path, pth)
    st = pth.open().read()
    total, empty, comments = len(st.split('\n')), len(empty_lines(st)), len(comments_and_docstrings(st))
    return {
            "imports" : imports(st, relative_to),
            "total_lines" : total,
            "empty_lines" : empty,
            "comments" : comments,
            "code_length": total - empty - comments,
            "contained_function_length" : [len(f.split('\n')) - len(empty_lines(f)) - len(comments_and_docstrings(f)) for f in functions(st)],
            }

def analyze_package(path):
    module_dict = {}
    for p in Path(path).rglob("*.py"):
        print(p)
        module_dict[p] = analyze_module(p, relative_to=path)
    return module_dict

