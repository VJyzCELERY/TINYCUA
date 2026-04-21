"""Safe command parser using shlex."""

import ast
import operator
import shlex
from dataclasses import dataclass
from typing import Any, List, Dict


@dataclass
class ParsedCommand:
    """Parsed command structure."""
    command: str
    args: List[str]
    flags: Dict[str, str]


class CommandParser:
    """Safe command parser.
    
    Uses shlex for safe parsing of command strings to prevent
    shell injection attacks.
    """
    
    def parse(self, command_string: str) -> ParsedCommand:
        """Parse command string safely.
        
        Args:
            command_string: Raw command string to parse.
            
        Returns:
            ParsedCommand with command, args, and flags.
            
        Raises:
            ValueError: If command string is empty.
        """
        parts = shlex.split(command_string)
        
        if not parts:
            raise ValueError("Empty command")
        
        command = parts[0]
        args = []
        flags = {}
        
        for part in parts[1:]:
            if part.startswith("--"):
                if "=" in part:
                    key, value = part[2:].split("=", 1)
                    flags[key] = value
                else:
                    flags[part[2:]] = ""
            elif part.startswith("-"):
                flags[part[1:]] = ""
            else:
                args.append(part)
        
        return ParsedCommand(command=command, args=args, flags=flags)


class MathEvalError(Exception):
    """Error during math expression evaluation."""
    pass


class MathEvalVisitor(ast.NodeVisitor):
    """AST visitor for safe math expression evaluation."""

    def __init__(self):
        self.result: Any = None
        self.allowed_operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.UAdd: operator.pos,
            ast.USub: operator.neg,
        }

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        left = self.visit(node.left)
        right = self.visit(node.right)
        op_type = type(node.op)
        if op_type not in self.allowed_operators:
            raise MathEvalError(f"Unsupported operator: {op_type.__name__}")
        return self.allowed_operators[op_type](left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        operand = self.visit(node.operand)
        op_type = type(node.op)
        if op_type not in self.allowed_operators:
            raise MathEvalError(f"Unsupported operator: {op_type.__name__}")
        return self.allowed_operators[op_type](operand)

    def visit_Constant(self, node: ast.Constant) -> Any:
        return node.value

    def visit_Num(self, node: ast.Num) -> Any:
        return node.n


def safe_eval(expression: str) -> float:
    """Safely evaluate a mathematical expression using AST.

    This is a secure replacement for eval() that only allows basic
    arithmetic operations.

    Args:
        expression: A math expression string (e.g., "2 + 2", "10 * 5").

    Returns:
        The result of the expression as a float.

    Raises:
        MathEvalError: If the expression contains unsupported operations.
    """
    allowed_expression_nodes = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Num)
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as e:
        raise MathEvalError(f"Invalid syntax: {e}")

    if not isinstance(tree.body, allowed_expression_nodes):
        raise MathEvalError(f"Unsupported expression type: {type(tree.body).__name__}")

    visitor = MathEvalVisitor()
    return visitor.visit(tree.body)
