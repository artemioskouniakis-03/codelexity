from pathlib import Path
import re
import ast
import importlib


pth = Path("./test.py")
st = pth.open().read()

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
       out = sorted([Path(path).relative_to(relative_to) for path in out])
    return sorted(out)

comments_and_docstrings(st)
empty_lines(st)
