from pydoc import resolve
from pathlib import Path
import re
import ast
import dis
import sys
import importlib.machinery


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

def _resolve(name, search):
    """Deepest spec for a dotted name, walking package search locations (never imports anything)."""
    spec, parts = None, name.split(".")
    for i in range(len(parts)):
        locations = spec.submodule_search_locations if spec else search
        found = locations and importlib.machinery.PathFinder.find_spec(".".join(parts[:i + 1]), locations)
        if not found:
            break
        spec = found
    return spec

def imports(path: Path, exclude_regex = None):
    code = compile(path.read_text(), str(path), "exec")
    root = path.parent
    search = sys.path + [str(root), *(str(d) for d in root.rglob("*") if d.is_dir())]
    names = {n for n in _import_names(code) if n.split(".")[0] not in sys.builtin_module_names}
    specs = (_resolve(n, search) for n in names)
    imports_sorted = sorted({s.origin for s in specs if s and s.origin})
    return imports_sorted if not exclude_regex else [i for i in imports_sorted if not re.search(exclude_regex,i)]

def analyze_module(path, exclude_regex = None):
    pth = Path(path).resolve()
    st = pth.open().read()
    total, empty, comments = len(st.split('\n')), len(empty_lines(st)), len(comments_and_docstrings(st))
    return {
            "imports" : imports(pth, exclude_regex=exclude_regex),
            "total_lines" : total,
            "empty_lines" : empty,
            "comments" : comments,
            "code_length": total - empty - comments,
            "contained_function_length" : [len(f.split('\n')) - len(empty_lines(f)) - len(comments_and_docstrings(f)) for f in functions(st)],
            }

def analyze_package(path, exclude_regex = None):
    module_dict = {}
    resolved_path = Path(path)
    print(resolved_path)
    for p in resolved_path.rglob("*.py"):
        module_dict[p.as_posix()] = analyze_module(p, exclude_regex = exclude_regex)
    return module_dict

