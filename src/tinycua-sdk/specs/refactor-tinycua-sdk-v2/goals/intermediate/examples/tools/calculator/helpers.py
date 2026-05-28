"""Private math helpers for the calculator tool."""

import ast
import operator

SUPPORTED_OPS = [
    "+", "-", "*", "/", "//", "%", "**",
    "abs", "round",
]

_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


class UnsafeExpressionError(ValueError):
    """Raised when the expression contains disallowed nodes."""


class _SafeEvaluator(ast.NodeVisitor):
    """AST visitor that only allows numeric operations."""

    def visit_BinOp(self, node: ast.BinOp) -> float | int:
        left = self.visit(node.left)
        right = self.visit(node.right)
        op_type = type(node.op)
        if op_type not in _OPERATORS:
            raise UnsafeExpressionError(f"Unsupported operator: {op_type.__name__}")
        return _OPERATORS[op_type](left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> float | int:
        operand = self.visit(node.operand)
        op_type = type(node.op)
        if op_type not in _OPERATORS:
            raise UnsafeExpressionError(f"Unsupported unary operator: {op_type.__name__}")
        return _OPERATORS[op_type](operand)

    def visit_Constant(self, node: ast.Constant) -> float | int:
        if isinstance(node.value, (int, float)):
            return node.value
        raise UnsafeExpressionError(f"Unsupported constant: {node.value!r}")

    def visit_Num(self, node: ast.Num) -> float | int:  # py<3.8 compat
        return node.n

    def generic_visit(self, node: ast.AST) -> None:
        raise UnsafeExpressionError(f"Unsupported expression node: {type(node).__name__}")


def safe_eval_expr(expression: str) -> float | int:
    """Safely evaluate a numeric expression using AST.

    Args:
        expression: Math expression string.

    Returns:
        Numeric result.

    Raises:
        UnsafeExpressionError: If the expression contains disallowed syntax.
    """
    tree = ast.parse(expression.strip(), mode="eval")
    return _SafeEvaluator().visit(tree.body)
