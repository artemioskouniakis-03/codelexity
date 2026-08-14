from pydoc import resolve
from pathlib import Path
import re
import ast
import dis
import sys
import importlib.machinery
from functools import lru_cache


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
    """Dotted names a code object imports, e.g. `from a.b import c` -> a, a.b, a.b.c."""
    for name, level, fromlist in dis._find_imports(code):
        yield name
        for item in fromlist or ():
            if item != "*":
                yield f"{name}.{item}"
    for const in code.co_consts:
        if isinstance(const, type(code)):
            yield from _import_names(const)

def _resolve(name, search):
    """Deepest importable spec for a dotted name, walking package search
    locations without importing/executing anything."""
    spec, parts = None, name.split(".")
    for i in range(len(parts)):
        locations = spec.submodule_search_locations if spec else search
        try:
            found = locations and importlib.machinery.PathFinder.find_spec(".".join(parts[:i + 1]), locations)
        except KeyError:
            # ponytail: namespace packages need their own parent in sys.modules
            # to build a submodule spec; we never import, so treat as unresolved.
            found = None
        if not found:
            break
        spec = found
    return spec

def imports(module_path, root=None):
    """Full filesystem paths of the local modules `module_path` imports."""
    path = Path(module_path).resolve()
    code = compile(path.read_text(), str(path), "exec")
    root = Path(root).resolve() if root else path.parent
    search = sys.path + [str(root), *(str(d) for d in root.rglob("*") if d.is_dir())]
    names = {n for n in _import_names(code) if n.split(".")[0] not in sys.builtin_module_names}
    specs = (_resolve(n, search) for n in names)
    return sorted({s.origin for s in specs if s and s.origin})

def analyze_module(path, root=None):
    pth = Path(path).resolve()
    st = pth.open().read()
    total, empty, comments = len(st.split('\n')), len(empty_lines(st)), len(comments_and_docstrings(st))
    return {
            "imports" : imports(pth, root),
            "total_lines" : total,
            "empty_lines" : empty,
            "comments" : comments,
            "code_length": total - empty - comments,
            "contained_function_length" : sorted([len(f.split('\n')) - len(empty_lines(f)) - len(comments_and_docstrings(f)) for f in functions(st)]),
            }


def normalized_path_list(path: str):
    suffixes = Path(path).suffixes
    name = Path(path).name
    path_list = path.split("/")[:-1]
    for suff in suffixes:
        name = name.replace(suff,"")
    return path_list + [name]

def is_valid(module_path: str, include_only, exclude):
    pathlist = normalized_path_list(module_path)
    included = not include_only or set(pathlist).isdisjoint(set(include_only))
    excluded = exclude and set(pathlist).isdisjoint(set(exclude))
    return included and not excluded

def analyze_package(path, exclude = (), include_only = (), max_recursion=25):
    module_dict = {}
    resolved_path = Path(path)
    for p in resolved_path.rglob("*.py"):
        if not is_valid(p.as_posix(), exclude, include_only):
            continue
        module_data = analyze_module(p, root=resolved_path)
        module_data['imports'] = [imp_mod for imp_mod in module_data['imports'] if is_valid(imp_mod, exclude, include_only)]
        module_dict[p.resolve().as_posix()] = module_data
        for imp in set(module_data['imports']).difference(set(module_dict.keys())):
            module_data = analyze_module(imp, root=resolved_path)
            module_data['imports'] = [imp_mod for imp_mod in module_data['imports'] if is_valid(imp_mod, exclude, include_only)]
            module_dict[imp] = module_data
    return module_dict
