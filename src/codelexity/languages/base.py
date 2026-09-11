import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class Span:
    start_byte: int
    end_byte: int
    start_line: int  # 1-indexed, inclusive
    end_line: int  # 1-indexed, inclusive


@dataclass(frozen=True, slots=True)
class UnitNode:
    name: str  # best-effort identifier; "<anonymous>:<line>" for unnamed fn expressions
    kind: str  # "function" | "method" | "arrow" | "constructor" | "local_function"
    span: Span
    node: object  # the tree-sitter Node for this unit, kept for complexity counting
    source: str  # raw source text for the unit's span


def _byte_to_line(source: bytes, byte_offset: int) -> int:
    """1-indexed line number for a byte offset."""
    return source.count(b"\n", 0, byte_offset) + 1


def walk_count(
    node,
    type_names: frozenset[str],
    exclude_types: frozenset[str] = frozenset(),
    _is_root: bool = True,
) -> int:
    """Counts nodes whose type is in `type_names`, not descending into subtrees whose
    root type is in `exclude_types` (used to keep a unit's complexity from including a
    nested unit's own branches)."""
    count = 0
    if not _is_root and node.type in exclude_types:
        return 0
    if node.type in type_names:
        count += 1
    for child in node.children:
        count += walk_count(child, type_names, exclude_types, _is_root=False)
    return count


def walk_collect(node, type_names: frozenset[str]) -> list:
    """All descendant nodes (including `node` itself) whose type is in `type_names`."""
    found = []
    if node.type in type_names:
        found.append(node)
    for child in node.children:
        found.extend(walk_collect(child, type_names))
    return found


def walk_leaves(node):
    """All leaf (childless) nodes in source order."""
    if not node.children:
        yield node
        return
    for child in node.children:
        yield from walk_leaves(child)


def strip_comments_and_blanks(
    source: str,
    line_comment: str | None,
    block_comment: tuple[str, str] | None,
) -> list[str]:
    """Source lines with comment text blanked out (line preserved so line numbers stay
    aligned with the original source)."""
    text = source
    if block_comment:
        start, end = block_comment
        pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)

        def _blank(match: re.Match) -> str:
            return "\n".join("" for _ in match.group(0).split("\n"))

        text = pattern.sub(_blank, text)
    lines = text.split("\n")
    if line_comment:
        out = []
        for line in lines:
            idx = line.find(line_comment)
            out.append(line if idx == -1 else line[:idx])
        return out
    return lines


class TreeSitterAnalyzer:
    """Shared tree-walk implementation. Concrete languages are mostly data: two
    frozensets of tree-sitter node-type names (unit types, decision-point types) plus a
    comment convention. Only genuinely language-specific quirks (e.g. JS anonymous
    function naming) need method overrides."""

    language_id: str = ""
    file_extensions: tuple[str, ...] = ()

    UNIT_TYPES: frozenset[str] = frozenset()
    DECISION_TYPES: frozenset[str] = frozenset()
    BOOLOP_TYPES: frozenset[str] = frozenset()  # e.g. "&&"/"||" chains: (operand_count - 1)
    BOOLOP_OPERATORS: frozenset[str] = frozenset()  # operator token text, e.g. {"&&", "||"};
    # empty means "any node whose type is in BOOLOP_TYPES counts" (Python's dedicated node type)
    IMPORT_TYPES: frozenset[str] = frozenset()
    NAME_FIELD_TYPES: dict[str, str] = {}  # unit node type -> child field name holding its name

    LINE_COMMENT: str | None = None
    BLOCK_COMMENTS: tuple[tuple[str, str], ...] = ()

    def _language(self):
        raise NotImplementedError

    def parse(self, source: bytes):
        from tree_sitter import Parser

        parser = Parser(self._language())
        return parser.parse(source)

    def _unit_kind(self, node_type: str) -> str:
        return "constructor" if "constructor" in node_type else ("method" if "method" in node_type else "function")

    def _unit_name(self, node, source: bytes) -> str:
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return source[name_node.start_byte : name_node.end_byte].decode("utf-8", errors="replace")
        parent = node.parent
        if parent is not None and parent.type in ("variable_declarator", "assignment_expression"):
            left = parent.child_by_field_name("name") or parent.child_by_field_name("left")
            if left is not None:
                return source[left.start_byte : left.end_byte].decode("utf-8", errors="replace")
        if parent is not None and parent.type == "pair":
            key = parent.child_by_field_name("key")
            if key is not None:
                return source[key.start_byte : key.end_byte].decode("utf-8", errors="replace")
        # By far the most common case left unnamed otherwise: a function/arrow passed
        # directly as a call argument - useEffect(() => {...}), array.map(x => ...),
        # promise.then(...) - extremely common in JS/TS/React code, where most inline
        # callbacks are written this way rather than assigned to a variable first.
        if parent is not None and parent.type == "arguments":
            call = parent.parent
            if call is not None and call.type == "call_expression":
                callee = call.child_by_field_name("function")
                if callee is not None:
                    callee_text = source[callee.start_byte : callee.end_byte].decode("utf-8", errors="replace")
                    return f"<arg of {callee_text}>"
        return f"<anonymous>:{_byte_to_line(source, node.start_byte)}"

    def find_units(self, tree, source: bytes) -> list[UnitNode]:
        units = []
        for node in walk_collect(tree.root_node, self.UNIT_TYPES):
            span = Span(
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                start_line=_byte_to_line(source, node.start_byte),
                end_line=_byte_to_line(source, node.end_byte),
            )
            units.append(
                UnitNode(
                    name=self._unit_name(node, source),
                    kind=self._unit_kind(node.type),
                    span=span,
                    node=node,
                    source=source[node.start_byte : node.end_byte].decode("utf-8", errors="replace"),
                )
            )
        return units

    def _operator_text(self, node, source: bytes) -> str:
        op_node = node.child_by_field_name("operator")
        if op_node is None:
            return ""
        return source[op_node.start_byte : op_node.end_byte].decode("utf-8", errors="replace")

    def _is_boolop(self, node, source: bytes) -> bool:
        if node.type not in self.BOOLOP_TYPES:
            return False
        if not self.BOOLOP_OPERATORS:
            return True
        return self._operator_text(node, source) in self.BOOLOP_OPERATORS

    def _count_boolop_chains(self, node, source: bytes, exclude_types: frozenset[str], _is_root: bool = True) -> int:
        """Sums (operand_count - 1) for every maximal chain of the same boolean operator,
        without descending into nested units."""
        total = 0
        if not _is_root and node.type in exclude_types:
            return 0
        is_boolop = self._is_boolop(node, source)
        parent = node.parent
        parent_is_same_chain = bool(
            is_boolop
            and parent is not None
            and self._is_boolop(parent, source)
            and (not self.BOOLOP_OPERATORS or self._operator_text(parent, source) == self._operator_text(node, source))
        )
        if is_boolop and not parent_is_same_chain:
            total += self._chain_length(node, source) - 1
        for child in node.children:
            total += self._count_boolop_chains(child, source, exclude_types, _is_root=False)
        return total

    def _chain_length(self, node, source: bytes) -> int:
        """Counts leaves of a left/right-recursive same-operator chain rooted at `node`."""
        op = self._operator_text(node, source) if self.BOOLOP_OPERATORS else None
        count = 0
        for child in node.children:
            same = self._is_boolop(child, source) and (op is None or self._operator_text(child, source) == op)
            if same:
                count += self._chain_length(child, source)
            elif child.is_named:
                count += 1
        return max(count, 2)

    def count_decision_points(self, node, source: bytes, exclude_nested: bool = True) -> int:
        exclude = self.UNIT_TYPES if exclude_nested else frozenset()
        base = walk_count(node, self.DECISION_TYPES, exclude, _is_root=True)
        boolops = self._count_boolop_chains(node, source, exclude, _is_root=True)
        return base + boolops

    def import_targets(self, tree, source: bytes) -> list[str]:
        targets = []
        for node in walk_collect(tree.root_node, self.IMPORT_TYPES):
            text = source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
            targets.append(text)
        return targets

    def strip_for_loc(self, source: str) -> list[str]:
        lines = source.split("\n")
        for start, end in self.BLOCK_COMMENTS:
            lines = strip_comments_and_blanks("\n".join(lines), None, (start, end))
        if self.LINE_COMMENT:
            lines = strip_comments_and_blanks("\n".join(lines), self.LINE_COMMENT, None)
        return lines


@runtime_checkable
class LanguageAnalyzer(Protocol):
    language_id: str
    file_extensions: tuple[str, ...]

    def parse(self, source: bytes):
        """Returns a tree_sitter.Tree for `source`."""
        ...

    def find_units(self, tree, source: bytes) -> list[UnitNode]:
        """All function/method-like definitions, including nested ones."""
        ...

    def count_decision_points(self, node, source: bytes, exclude_nested: bool = True) -> int:
        """McCabe count (excluding the +1 base) for the subtree rooted at `node`."""
        ...

    def import_targets(self, tree, source: bytes) -> list[str]:
        """Raw imported/required module specifiers as written in source."""
        ...

    def strip_for_loc(self, source: str) -> list[str]:
        """Source lines with comments blanked out, for the Volume/Unit-Size LOC rule."""
        ...
