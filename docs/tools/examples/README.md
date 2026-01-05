# Tool Examples

This directory contains working examples of tool implementations for the Cuga agent system.

## Available Examples

### 1. Calculator Tool (`calculator_tool.py`)

**Complexity:** Beginner  
**Features:**
- Basic arithmetic operations (add, subtract, multiply, divide)
- Input validation
- Parameter schema
- Error handling (division by zero)

**Run:**
```bash
python docs/tools/examples/calculator_tool.py
```

**Key Concepts:**
- Tool handler signature
- Parameter validation
- ToolSpec configuration
- WorkerAgent integration

---

### 2. GitHub Repository Tool (`github_tool.py`)

**Complexity:** Intermediate  
**Features:**
- External API integration (GitHub API)
- Network error handling with retry
- Rate limit handling
- Response transformation
- Optional detailed stats

**Setup:**
```bash
# Optional: Set GitHub token for higher rate limits
export GITHUB_TOKEN=your_github_personal_access_token

# Run
python docs/tools/examples/github_tool.py
```

**Key Concepts:**
- External API calls
- Retryable vs non-retryable errors
- ConnectionError for network failures
- TimeoutError for request timeouts
- Environment-based configuration

---

## Running Examples

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# For GitHub example, install requests
pip install requests
```

### Run Individual Example

```bash
# Calculator
python docs/tools/examples/calculator_tool.py

# GitHub
python docs/tools/examples/github_tool.py
```

### Run in Interactive Mode

```python
# Python REPL
>>> from docs.tools.examples.calculator_tool import CALCULATOR_TOOL
>>> from cuga.modular.tools import ToolRegistry
>>> from cuga.modular.agents import WorkerAgent
>>> from cuga.modular.memory import VectorMemory
>>>
>>> registry = ToolRegistry(tools=[CALCULATOR_TOOL])
>>> worker = WorkerAgent(registry=registry, memory=VectorMemory())
>>>
>>> result = worker.execute([
...     {"tool": "calculator", "input": {"operation": "add", "a": 10, "b": 5}}
... ])
>>> print(result.output)
{'operation': 'add', 'a': 10.0, 'b': 5.0, 'result': 15.0}
```

---

## Example Patterns

### Pattern 1: Local Computation (Calculator)

```python
def handler(inputs, context):
    # Validate inputs
    # Perform computation
    # Return result
    pass

ToolSpec(
    sandbox_profile="py-slim",
    network_allowed=False,
    cost=0.01,  # Low cost
)
```

### Pattern 2: External API (GitHub)

```python
def handler(inputs, context):
    try:
        response = requests.get(url, timeout=10.0)
        response.raise_for_status()
        return transform_response(response.json())
    except requests.ConnectionError as e:
        raise ConnectionError(f"API unavailable: {e}")  # Retryable
    except requests.Timeout as e:
        raise TimeoutError(f"Request timeout: {e}")  # Retryable

ToolSpec(
    sandbox_profile="py-full",
    network_allowed=True,
    cost=0.5,  # Medium cost
    allowlist=["requests"],
)
```

---

## Testing Examples

Each example includes test scenarios:

```bash
# Test calculator
pytest tests/tools/examples/test_calculator_tool.py -v

# Test GitHub tool (with mocked API)
pytest tests/tools/examples/test_github_tool.py -v
```

Example test structure:

```python
# tests/tools/examples/test_calculator_tool.py
import pytest
from docs.tools.examples.calculator_tool import calculator_handler

def test_addition():
    result = calculator_handler(
        {"operation": "add", "a": 10, "b": 5},
        {"profile": "test", "trace_id": "test-123"}
    )
    assert result["result"] == 15.0

def test_division_by_zero():
    with pytest.raises(ValueError, match="Division by zero"):
        calculator_handler(
            {"operation": "divide", "a": 10, "b": 0},
            {"profile": "test", "trace_id": "test-123"}
        )
```

---

## Next Steps

1. **Modify Examples:** Try changing parameters, adding features
2. **Create Your Own:** Use as templates for new tools
3. **Read Guides:**
   - [Tool Creation Guide](../TOOL_CREATION_GUIDE.md) - Step-by-step tutorial
   - [Modular Tool Integration](../MODULAR_TOOL_INTEGRATION.md) - Complete reference

---

## Common Issues

### Issue: "requests library not available"

**Solution:** Add to allowlist:
```python
ToolSpec(allowlist=["requests"])
```

### Issue: "Network access denied"

**Solution:** Enable network:
```python
ToolSpec(
    sandbox_profile="py-full",
    network_allowed=True,
)
```

### Issue: "Tool always retries on validation errors"

**Solution:** Use correct exception types:
```python
# Not retryable (validation errors)
raise ValueError("Invalid input")

# Retryable (transient failures)
raise ConnectionError("Network unavailable")
raise TimeoutError("Request timeout")
```

---

## Contributing Examples

Want to add an example? Follow these guidelines:

1. **File naming:** `{tool_name}_tool.py`
2. **Include:**
   - Docstring explaining what it does
   - Handler function with type hints
   - ToolSpec configuration
   - Example usage in `main()`
   - Error handling demonstrations
3. **Add tests:** `tests/tools/examples/test_{tool_name}_tool.py`
4. **Update this README:** Add to "Available Examples" section

Submit via PR to main repository!
