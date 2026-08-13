from pydoc import resolve
from pathlib import Path
import re
import ast
import dis


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

def _import_names(code):
    for name, level, fromlist in dis._find_imports(code):
        yield name
    for const in code.co_consts:
        if isinstance(const, type(code)):
            yield from _import_names(const)

def imports(path: Path, relative_to = None):
    code = compile(path.read_text(), str(path), "exec")
    return sorted(set(_import_names(code)))

def analyze_module(path, relative_to = None):
    print(f"--{path}")
    pth = Path(path).resolve()
    st = pth.open().read()
    total, empty, comments = len(st.split('\n')), len(empty_lines(st)), len(comments_and_docstrings(st))
    return {
            "imports" : imports(pth, relative_to),
            "total_lines" : total,
            "empty_lines" : empty,
            "comments" : comments,
            "code_length": total - empty - comments,
            "contained_function_length" : [len(f.split('\n')) - len(empty_lines(f)) - len(comments_and_docstrings(f)) for f in functions(st)],
            }

def analyze_package(path):
    module_dict = {}
    resolved_path = Path(path).resolve()
    print(resolved_path)
    for p in resolved_path.rglob("*.py"):
        module_dict[p.as_posix()] = analyze_module(p, relative_to=resolved_path)
    return module_dict

