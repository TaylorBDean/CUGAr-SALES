"""
Simple Calculator Tool Example

Demonstrates basic tool creation with:
- Input validation
- Parameter schema
- Error handling
- Testing
"""

from typing import Dict, Any
from cuga.modular.tools import ToolSpec, ToolRegistry
from cuga.modular.agents import WorkerAgent
from cuga.modular.memory import VectorMemory


def calculator_handler(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform basic arithmetic operations.
    
    Args:
        inputs:
            - operation: str (required) - One of: add, subtract, multiply, divide
            - a: float (required) - First operand
            - b: float (required) - Second operand
        context:
            - profile: Execution profile
            - trace_id: Trace ID
    
    Returns:
        Result dictionary with operation, operands, and result
    
    Raises:
        ValueError: Invalid operation or division by zero
    """
    operation = inputs.get("operation")
    a = inputs.get("a")
    b = inputs.get("b")
    
    # Validation
    if operation not in ["add", "subtract", "multiply", "divide"]:
        raise ValueError(
            f"Invalid operation: {operation}. "
            f"Must be one of: add, subtract, multiply, divide"
        )
    
    if a is None or b is None:
        raise ValueError("Both operands (a, b) are required")
    
    # Convert to float
    try:
        a = float(a)
        b = float(b)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Operands must be numbers: {e}")
    
    # Perform operation
    if operation == "add":
        result = a + b
    elif operation == "subtract":
        result = a - b
    elif operation == "multiply":
        result = a * b
    elif operation == "divide":
        if b == 0:
            raise ValueError("Division by zero")
        result = a / b
    
    return {
        "operation": operation,
        "a": a,
        "b": b,
        "result": result,
    }


# Create ToolSpec
CALCULATOR_TOOL = ToolSpec(
    name="calculator",
    description="Perform basic arithmetic operations (add, subtract, multiply, divide)",
    handler=calculator_handler,
    parameters={
        "operation": {
            "type": "string",
            "required": True,
            "enum": ["add", "subtract", "multiply", "divide"],
            "description": "Arithmetic operation to perform",
        },
        "a": {
            "type": "number",
            "required": True,
            "description": "First operand",
        },
        "b": {
            "type": "number",
            "required": True,
            "description": "Second operand",
        },
    },
    cost=0.01,  # Very low cost (local computation)
    sandbox_profile="py-slim",
    read_only=True,
    network_allowed=False,
    tags=["math", "calculator", "arithmetic"],
    version="1.0.0",
)


# Example usage
def main():
    """Demonstrate calculator tool usage."""
    
    # Setup
    registry = ToolRegistry(tools=[CALCULATOR_TOOL])
    worker = WorkerAgent(registry=registry, memory=VectorMemory())
    
    # Example 1: Addition
    print("Example 1: Addition")
    result = worker.execute([
        {"tool": "calculator", "input": {"operation": "add", "a": 10, "b": 5}}
    ])
    print(f"  {result.output}")  # {'operation': 'add', 'a': 10.0, 'b': 5.0, 'result': 15.0}
    
    # Example 2: Multiplication
    print("\nExample 2: Multiplication")
    result = worker.execute([
        {"tool": "calculator", "input": {"operation": "multiply", "a": 7, "b": 8}}
    ])
    print(f"  {result.output}")  # {'operation': 'multiply', 'a': 7.0, 'b': 8.0, 'result': 56.0}
    
    # Example 3: Division
    print("\nExample 3: Division")
    result = worker.execute([
        {"tool": "calculator", "input": {"operation": "divide", "a": 100, "b": 4}}
    ])
    print(f"  {result.output}")  # {'operation': 'divide', 'a': 100.0, 'b': 4.0, 'result': 25.0}
    
    # Example 4: Error handling (division by zero)
    print("\nExample 4: Error handling")
    try:
        result = worker.execute([
            {"tool": "calculator", "input": {"operation": "divide", "a": 10, "b": 0}}
        ])
    except Exception as e:
        print(f"  Error caught: {e}")  # ValueError: Division by zero
    
    # Example 5: Multi-step calculation
    print("\nExample 5: Multi-step calculation (10 + 5) * 2")
    steps = [
        {"tool": "calculator", "input": {"operation": "add", "a": 10, "b": 5}},
        {"tool": "calculator", "input": {"operation": "multiply", "a": 15, "b": 2}},
    ]
    # Note: In real usage, you'd extract result from step 1 and pass to step 2
    # This is simplified for demonstration


if __name__ == "__main__":
    main()
