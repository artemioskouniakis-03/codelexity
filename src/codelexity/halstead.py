"""Halstead metrics from the parse tree.

Operators are ast node types, operands are the names and literals they act on. Working from
the tree rather than the token stream keeps paired delimiters as one operator (a `Call` node,
not a `(` plus a `)`) and drops comments without a filter, since ast never emits them.
"""

import ast
from collections import Counter
from math import log2

IGNORED = (
    ast.Module,
    ast.Expr,
    ast.expr_context,
    ast.arguments,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
)


def operators_and_operands(module_source: str):
    """Counts of each distinct operator and operand in `module_source`."""
    operators, operands = Counter(), Counter()
    for node in ast.walk(ast.parse(module_source)):
        if isinstance(node, IGNORED):
            continue
        if isinstance(node, ast.Constant):
            operands[repr(node.value)] += 1
        elif isinstance(node, ast.Name):
            operands[node.id] += 1
        elif isinstance(node, ast.arg):
            operands[node.arg] += 1
        elif isinstance(node, ast.alias):
            operands[node.name] += 1
        else:
            operators[type(node).__name__] += 1
            if isinstance(node, ast.Attribute):
                operands[node.attr] += 1  # `a.b` is the `.` operator applied to operand `b`
    return operators, operands


def halstead_metrics(module_source: str):
    operators, operands = operators_and_operands(module_source)
    distinct_operators, distinct_operands = len(operators), len(operands)
    total_operators, total_operands = sum(operators.values()), sum(operands.values())
    vocabulary = distinct_operators + distinct_operands
    length = total_operators + total_operands
    volume = length * log2(vocabulary) if vocabulary else 0.0
    difficulty = (distinct_operators * total_operands) / (2 * distinct_operands) if distinct_operands else 0.0
    effort = difficulty * volume
    return {
        "distinct_operators": distinct_operators,
        "distinct_operands": distinct_operands,
        "total_operators": total_operators,
        "total_operands": total_operands,
        "vocabulary": vocabulary,
        "length": length,
        "volume": volume,
        "difficulty": difficulty,
        "effort": effort,
        "time": effort / 18,
        "estimated_bugs": volume / 3000,
    }
