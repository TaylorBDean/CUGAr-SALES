# Quick Start: Adding Your First Tool

**Time to first tool:** ~5 minutes  
**Prerequisites:** Fork completed, tests passing (118/118)

---

## 🚀 3-Step Tool Integration

### **Step 1: Create Handler (2 min)**

Create `src/cuga/modular/tools/my_tool.py`:

```python
"""
My custom tool for processing data.
"""
from typing import Dict, Any


def my_tool_handler(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process data using my custom logic.
    
    Args:
        inputs: Tool inputs
            - query (str, required): Search query
            - max_results (int, optional): Max results (default: 10)
        context: Execution context
            - profile (str): Execution profile
            - trace_id (str): Trace identifier
    
    Returns:
        Dict with results and metadata
        
    Raises:
        ValueError: If required params missing
    """
    # 1. Validate required params
    if "query" not in inputs:
        raise ValueError("Missing required parameter: query")
    
    query = inputs["query"]
    max_results = inputs.get("max_results", 10)
    
    # 2. Get context
    profile = context.get("profile", "default")
    trace_id = context.get("trace_id", "no-trace")
    
    # 3. Your tool logic here
    results = [
        {"id": 1, "title": f"Result for {query}"},
        {"id": 2, "title": f"Another result for {query}"},
    ][:max_results]
    
    # 4. Return structured result
    return {
        "query": query,
        "results": results,
        "count": len(results),
        "profile": profile,
        "trace_id": trace_id,
    }


# Export for testing
SCHEMA = {
    "name": "my_tool",
    "inputs": {
        "query": {"type": "string", "required": True},
        "max_results": {"type": "integer", "required": False, "default": 10},
    },
    "outputs": {
        "results": {"type": "array"},
        "count": {"type": "integer"},
    },
}
```

---

### **Step 2: Register Tool (1 min)**

Option A: **Direct Registration** (Simple)

```python
from cuga.modular.tools import ToolSpec, ToolRegistry
from cuga.modular.tools.my_tool import my_tool_handler

# Create registry
registry = ToolRegistry()

# Register tool
my_tool = ToolSpec(
    name="my_tool",
    description="Custom tool for processing data",
    handler=my_tool_handler,
    parameters={
        "query": {"type": "string", "required": True},
        "max_results": {"type": "integer", "default": 10},
    },
)

registry.register(my_tool)
```

Option B: **Config-Based Registration** (Production)

Add to `registry.yaml`:

```yaml
tools:
  - name: my_tool
    description: Custom tool for processing data
    module: cuga.modular.tools.my_tool.my_tool_handler
    parameters:
      query:
        type: string
        required: true
      max_results:
        type: integer
        default: 10
```

Then load:

```python
from cuga.modular.tools import ToolRegistry

registry = ToolRegistry.from_config(config_tools)
```

---

### **Step 3: Use in Agents (2 min)**

```python
from cuga.modular.agents import PlannerAgent, WorkerAgent
from cuga.modular.memory import VectorMemory
from cuga.modular.config import AgentConfig

# Setup
memory = VectorMemory(profile="dev")
config = AgentConfig(profile="dev", max_steps=5)

# Create agents
planner = PlannerAgent(
    registry=registry,
    memory=memory,
    config=config,
)

worker = WorkerAgent(
    registry=registry,
    memory=memory,
)

# Use your tool!
goal = "Use my_tool to search for Python tutorials"
plan = planner.plan(goal)

print(f"Plan created with {len(plan.steps)} steps")
for step in plan.steps:
    print(f"  - {step['tool']}: {step['reason']}")

# Execute
result = worker.execute(plan.steps)
print(f"Result: {result.output}")
```

**Output:**
```
Plan created with 1 steps
  - my_tool: matched with score 0.67
Result: {'query': 'Python tutorials', 'results': [...], 'count': 2, ...}
```

---

## ✅ Validation Checklist

After adding your tool, verify:

- [ ] Handler accepts `(inputs: Dict, context: Dict)` signature
- [ ] Handler validates required parameters
- [ ] Handler uses context (profile, trace_id)
- [ ] Handler returns structured result
- [ ] Tool registered in registry
- [ ] Tool selected by planner (run test goal)
- [ ] Tool executes successfully (check result.output)
- [ ] Observability events emitted (check console for JSON events)

---

## 🧪 Testing Your Tool (5 min)

Create `tests/unit/test_my_tool.py`:

```python
"""
Tests for my_tool handler.
"""
import pytest
from cuga.modular.tools import ToolSpec
from cuga.modular.tools.my_tool import my_tool_handler


class TestMyTool:
    """Tests for my_tool handler."""
    
    def test_handler_processes_query(self):
        """Tool should process query correctly."""
        tool = ToolSpec(
            name="my_tool",
            description="Test",
            handler=my_tool_handler,
        )
        
        inputs = {"query": "Python"}
        context = {"profile": "test", "trace_id": "test-123"}
        
        result = tool.handler(inputs, context)
        
        assert result["query"] == "Python"
        assert "results" in result
        assert result["count"] > 0
        assert result["trace_id"] == "test-123"
    
    def test_handler_validates_required_params(self):
        """Tool should require query parameter."""
        tool = ToolSpec(
            name="my_tool",
            description="Test",
            handler=my_tool_handler,
        )
        
        # Missing query
        with pytest.raises(ValueError, match="Missing required parameter: query"):
            tool.handler({}, {})
    
    def test_handler_respects_max_results(self):
        """Tool should respect max_results parameter."""
        tool = ToolSpec(
            name="my_tool",
            description="Test",
            handler=my_tool_handler,
        )
        
        inputs = {"query": "test", "max_results": 1}
        result = tool.handler(inputs, {})
        
        assert result["count"] == 1
        assert len(result["results"]) == 1
    
    def test_handler_uses_defaults(self):
        """Tool should use default max_results when not provided."""
        tool = ToolSpec(
            name="my_tool",
            description="Test",
            handler=my_tool_handler,
        )
        
        inputs = {"query": "test"}  # No max_results
        result = tool.handler(inputs, {})
        
        assert result["count"] <= 10  # Default max_results


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**Run tests:**
```bash
pytest tests/unit/test_my_tool.py -v
```

**Expected output:**
```
tests/unit/test_my_tool.py::TestMyTool::test_handler_processes_query PASSED
tests/unit/test_my_tool.py::TestMyTool::test_handler_validates_required_params PASSED
tests/unit/test_my_tool.py::TestMyTool::test_handler_respects_max_results PASSED
tests/unit/test_my_tool.py::TestMyTool::test_handler_uses_defaults PASSED

==== 4 passed in 0.05s ====
```

---

## 🎯 Common Patterns

### **1. API Integration Tool**

```python
def api_tool_handler(inputs: Dict, context: Dict) -> Dict:
    """Call external API (use SafeClient for HTTP)."""
    from cuga.security.http_client import SafeClient
    
    query = inputs["query"]
    client = SafeClient(timeout=10.0)
    
    response = client.get(f"https://api.example.com/search?q={query}")
    return response.json()
```

### **2. File Processing Tool**

```python
def file_tool_handler(inputs: Dict, context: Dict) -> Dict:
    """Process files (respect sandbox boundaries)."""
    file_path = inputs["path"]
    profile = context.get("profile", "default")
    
    # Validate path is in allowed directory
    if not file_path.startswith(f"/workdir/{profile}/"):
        raise ValueError("Path outside allowed directory")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    return {"path": file_path, "content": content, "lines": len(content.split('\n'))}
```

### **3. Memory-Augmented Tool**

```python
def memory_tool_handler(inputs: Dict, context: Dict) -> Dict:
    """Use memory for context-aware processing."""
    from cuga.modular.memory import VectorMemory
    
    query = inputs["query"]
    profile = context.get("profile", "default")
    
    memory = VectorMemory(profile=profile)
    context_results = memory.search(query, top_k=5)
    
    # Use context to enhance results
    enhanced_query = f"{query} (context: {[r.text for r in context_results]})"
    
    return {"query": query, "context_used": len(context_results), "enhanced": True}
```

### **4. Budget-Aware Tool**

```python
def expensive_tool_handler(inputs: Dict, context: Dict) -> Dict:
    """Tool with cost tracking."""
    from cuga.backend.guardrails.policy import budget_guard
    
    query = inputs["query"]
    estimated_cost = len(query) * 0.01  # $0.01 per character
    
    # Check budget before execution
    budget_guard(
        action="expensive_tool",
        cost=estimated_cost,
        metadata={"query_length": len(query)},
    )
    
    # Execute expensive operation
    result = expensive_operation(query)
    
    return {"result": result, "cost": estimated_cost}
```

---

## 📚 Resources

### **Example Tools**
- `src/cuga/modular/tools/echo.py` - Simple echo tool
- `tests/unit/test_tool_handlers.py` - 20+ test patterns

### **Integration Examples**
- `tests/integration/test_memory_agent_integration_real.py` - Agent-tool-memory integration
- `examples/multi_agent_dispatch.py` - Multi-agent tool usage

### **Handler Patterns**
- **Signature:** `(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any`
- **Validation:** Raise `ValueError` for missing/invalid params
- **Context:** Always use `context.get("trace_id")` and `context.get("profile")`
- **Returns:** Prefer `Dict` for structured results (easier testing)

---

## 🚨 Common Pitfalls

### ❌ **Wrong Signature**
```python
# WRONG
def bad_handler(query: str) -> str:
    return f"Result: {query}"
```

### ✅ **Correct Signature**
```python
# CORRECT
def good_handler(inputs: Dict[str, Any], context: Dict[str, Any]) -> str:
    query = inputs.get("query", "")
    return f"Result: {query}"
```

---

### ❌ **No Validation**
```python
# WRONG - Will crash on missing param
def bad_handler(inputs: Dict, context: Dict) -> str:
    return inputs["query"]  # KeyError if missing!
```

### ✅ **Explicit Validation**
```python
# CORRECT - Clear error message
def good_handler(inputs: Dict, context: Dict) -> str:
    if "query" not in inputs:
        raise ValueError("Missing required parameter: query")
    return inputs["query"]
```

---

### ❌ **Ignoring Context**
```python
# WRONG - No trace propagation
def bad_handler(inputs: Dict, context: Dict) -> Dict:
    return {"result": process(inputs["query"])}
```

### ✅ **Using Context**
```python
# CORRECT - Propagates trace_id, uses profile
def good_handler(inputs: Dict, context: Dict) -> Dict:
    query = inputs["query"]
    profile = context.get("profile", "default")
    trace_id = context.get("trace_id")
    
    result = process(query, profile=profile)
    return {"result": result, "trace_id": trace_id, "profile": profile}
```

---

## 🎉 You're Ready!

With this guide, you can:
- ✅ Add your first tool in 5 minutes
- ✅ Integrate with agents seamlessly
- ✅ Test thoroughly with provided patterns
- ✅ Avoid common pitfalls

**Start building and let the agents do the rest!** 🚀
