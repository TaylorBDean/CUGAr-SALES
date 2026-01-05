"""
Safe expression evaluation without using eval().

This module provides secure expression evaluation using AST parsing and
controlled execution contexts, enforcing AGENTS.md guardrails:
- No eval()/exec() for simple expressions
- Allowlist-based operations and functions
- Deny-by-default for imports and builtins
"""
import ast
import math
import operator
from typing import Any, Dict, Optional, Set


class SafeExpressionEvaluator:
    """
    Evaluates mathematical expressions safely without eval().
    
    Uses AST parsing to validate and execute expressions with
    strict operator and function allowlists.
    """
    
    # Allowlisted binary operators
    SAFE_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    
    # Allowlisted unary operators
    SAFE_UNARY_OPERATORS = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }
    
    # Allowlisted comparison operators
    SAFE_COMPARE_OPERATORS = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
    }
    
    # Allowlisted math functions
    SAFE_FUNCTIONS = {
        'abs': abs,
        'round': round,
        'min': min,
        'max': max,
        'sum': sum,
        # Math module functions
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'asin': math.asin,
        'acos': math.acos,
        'atan': math.atan,
        'sinh': math.sinh,
        'cosh': math.cosh,
        'tanh': math.tanh,
        'log': math.log,
        'log10': math.log10,
        'log2': math.log2,
        'exp': math.exp,
        'sqrt': math.sqrt,
        'ceil': math.ceil,
        'floor': math.floor,
        'pow': pow,
    }
    
    # Allowlisted constants
    SAFE_CONSTANTS = {
        'pi': math.pi,
        'e': math.e,
        'tau': math.tau,
        'inf': math.inf,
    }
    
    def __init__(
        self,
        extra_functions: Optional[Dict[str, Any]] = None,
        extra_constants: Optional[Dict[str, Any]] = None,
        max_depth: int = 50,
    ):
        """
        Initialize the safe evaluator.
        
        Args:
            extra_functions: Additional allowlisted functions (optional)
            extra_constants: Additional allowlisted constants (optional)
            max_depth: Maximum AST depth to prevent stack overflow (default: 50)
        """
        self.functions = {**self.SAFE_FUNCTIONS, **(extra_functions or {})}
        self.constants = {**self.SAFE_CONSTANTS, **(extra_constants or {})}
        self.max_depth = max_depth
        self._depth = 0
    
    def evaluate(self, expression: str) -> float:
        """
        Safely evaluate a mathematical expression.
        
        Args:
            expression: The expression string to evaluate
            
        Returns:
            The numeric result of the expression
            
        Raises:
            ValueError: If the expression is invalid or contains forbidden operations
            SyntaxError: If the expression has syntax errors
            TypeError: If the expression produces non-numeric results
        """
        if not expression or not isinstance(expression, str):
            raise ValueError("Expression must be a non-empty string")
        
        # Parse the expression into an AST
        try:
            tree = ast.parse(expression, mode='eval')
        except SyntaxError as e:
            raise SyntaxError(f"Invalid expression syntax: {e}")
        
        # Validate and evaluate the AST
        self._depth = 0
        result = self._eval_node(tree.body)
        
        # Ensure result is numeric
        if not isinstance(result, (int, float)):
            raise TypeError(f"Expression must evaluate to a number, got {type(result).__name__}")
        
        return float(result)
    
    def _eval_node(self, node: ast.AST) -> Any:
        """
        Recursively evaluate an AST node.
        
        Args:
            node: The AST node to evaluate
            
        Returns:
            The evaluated result
            
        Raises:
            ValueError: If the node contains forbidden operations
            RecursionError: If the AST depth exceeds max_depth
        """
        self._depth += 1
        if self._depth > self.max_depth:
            raise RecursionError(f"Expression too complex (depth > {self.max_depth})")
        
        try:
            # Numeric constant
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    return node.value
                raise ValueError(f"Unsupported constant type: {type(node.value).__name__}")
            
            # Legacy Num node (Python < 3.8)
            if isinstance(node, ast.Num):
                return node.n
            
            # Binary operation (e.g., a + b)
            if isinstance(node, ast.BinOp):
                op_type = type(node.op)
                if op_type not in self.SAFE_OPERATORS:
                    raise ValueError(f"Forbidden operation: {op_type.__name__}")
                
                left = self._eval_node(node.left)
                right = self._eval_node(node.right)
                op_func = self.SAFE_OPERATORS[op_type]
                
                # Handle division by zero
                if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right == 0:
                    raise ValueError("Division by zero")
                
                return op_func(left, right)
            
            # Unary operation (e.g., -a, +a)
            if isinstance(node, ast.UnaryOp):
                op_type = type(node.op)
                if op_type not in self.SAFE_UNARY_OPERATORS:
                    raise ValueError(f"Forbidden unary operation: {op_type.__name__}")
                
                operand = self._eval_node(node.operand)
                op_func = self.SAFE_UNARY_OPERATORS[op_type]
                return op_func(operand)
            
            # Comparison (e.g., a < b)
            if isinstance(node, ast.Compare):
                if len(node.ops) != 1:
                    raise ValueError("Chained comparisons not supported")
                
                op_type = type(node.ops[0])
                if op_type not in self.SAFE_COMPARE_OPERATORS:
                    raise ValueError(f"Forbidden comparison: {op_type.__name__}")
                
                left = self._eval_node(node.left)
                right = self._eval_node(node.comparators[0])
                op_func = self.SAFE_COMPARE_OPERATORS[op_type]
                return 1.0 if op_func(left, right) else 0.0
            
            # Function call
            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name):
                    raise ValueError("Only simple function calls are allowed")
                
                func_name = node.func.id
                if func_name not in self.functions:
                    raise ValueError(f"Forbidden or unknown function: {func_name}")
                
                # Evaluate arguments
                args = [self._eval_node(arg) for arg in node.args]
                
                # No keyword arguments allowed for security
                if node.keywords:
                    raise ValueError("Keyword arguments not allowed")
                
                func = self.functions[func_name]
                try:
                    return func(*args)
                except Exception as e:
                    raise ValueError(f"Error calling {func_name}: {e}")
            
            # Name lookup (constants and variables)
            if isinstance(node, ast.Name):
                name = node.id
                if name in self.constants:
                    return self.constants[name]
                raise ValueError(f"Undefined variable or forbidden name: {name}")
            
            # List expression (for functions like min, max, sum)
            if isinstance(node, ast.List):
                return [self._eval_node(elem) for elem in node.elts]
            
            # Tuple expression
            if isinstance(node, ast.Tuple):
                return tuple(self._eval_node(elem) for elem in node.elts)
            
            # Reject everything else (assignments, imports, attribute access, etc.)
            raise ValueError(
                f"Forbidden expression type: {type(node).__name__}. "
                "Only simple mathematical expressions are allowed."
            )
        
        finally:
            self._depth -= 1


def safe_eval_expression(
    expression: str,
    extra_functions: Optional[Dict[str, Any]] = None,
    extra_constants: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Convenience function to safely evaluate a mathematical expression.
    
    This replaces unsafe eval() calls with AST-based safe evaluation.
    
    Args:
        expression: The expression string to evaluate
        extra_functions: Additional allowlisted functions (optional)
        extra_constants: Additional allowlisted constants (optional)
        
    Returns:
        The numeric result of the expression
        
    Raises:
        ValueError: If the expression is invalid or contains forbidden operations
        SyntaxError: If the expression has syntax errors
        TypeError: If the expression produces non-numeric results
        
    Example:
        >>> safe_eval_expression("2 + 3 * 4")
        14.0
        >>> safe_eval_expression("sin(pi / 2)")
        1.0
        >>> safe_eval_expression("sqrt(16) + 2**3")
        12.0
    """
    evaluator = SafeExpressionEvaluator(
        extra_functions=extra_functions,
        extra_constants=extra_constants,
    )
    return evaluator.evaluate(expression)
