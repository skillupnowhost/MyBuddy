import ast
import operator

from app.services.tools.base import Tool, ToolContext

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node: ast.AST) -> float:
    """Evaluates a restricted arithmetic expression AST. No names, calls, attributes, or
    subscripts are permitted — only numeric literals and the operators above. This is
    deliberately not Python's eval(): a malicious "expression" cannot execute arbitrary code."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Expression contains disallowed syntax")


class CalculatorTool(Tool):
    name = "calculator"
    description = 'Evaluates a basic arithmetic expression. Args: {"expression": "2 + 2 * 3"}'

    def run(self, args: dict, context: ToolContext | None = None) -> str:
        expression = args.get("expression", "")
        try:
            tree = ast.parse(expression, mode="eval")
            result = _safe_eval(tree.body)
            return str(result)
        except Exception:
            return f"Error: could not evaluate '{expression}' as a basic arithmetic expression."
