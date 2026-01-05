# Tool Creation Guide

**Quick tutorial for creating new tools in Cuga**

## 5-Minute Quick Start

### 1. Write Handler Function

```python
# my_tool.py
def greet_user(inputs, context):
    """Say hello to a user."""
    name = inputs.get("name", "World")
    return f"Hello, {name}!"
```

### 2. Create ToolSpec

```python
from cuga.modular.tools import ToolSpec

greet_tool = ToolSpec(
    name="greet",
    description="Greet a user by name",
    handler=greet_user,
    parameters={
        "name": {"type": "string", "required": False, "default": "World"},
    },
)
```

### 3. Register & Use

```python
from cuga.modular.tools import ToolRegistry
from cuga.modular.agents import WorkerAgent
from cuga.modular.memory import VectorMemory

registry = ToolRegistry(tools=[greet_tool])
worker = WorkerAgent(registry=registry, memory=VectorMemory())

result = worker.execute([
    {"tool": "greet", "input": {"name": "Alice"}}
])

print(result.output)  # "Hello, Alice!"
```

Done! Your tool is now registered, validated, sandboxed, and observable.

---

## Complete Tutorial: Weather Tool

Let's build a real-world tool that fetches weather data.

### Step 1: Plan the Tool

**What it does:** Fetch current weather for a location  
**Inputs:** Location (required), units (optional)  
**Outputs:** Temperature, conditions, humidity  
**Errors:** Invalid location → ValueError, Network issues → ConnectionError

### Step 2: Implement Handler

```python
# weather_tool.py
from typing import Dict, Any
import requests

def get_weather(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch current weather for a location.
    
    Args:
        inputs: Tool parameters
            - location (str, required): City name or ZIP code
            - units (str, optional): "metric" or "imperial"
        context: Execution context
            - profile (str): Execution profile
            - trace_id (str): Request trace ID
    
    Returns:
        Weather data with temperature, conditions, humidity
    
    Raises:
        ValueError: Invalid location or units
        ConnectionError: API unavailable (retryable)
    """
    # Extract inputs
    location = inputs.get("location")
    units = inputs.get("units", "metric")
    
    # Validate
    if not location:
        raise ValueError("Location is required")
    if units not in ["metric", "imperial"]:
        raise ValueError(f"Invalid units: {units}. Must be 'metric' or 'imperial'")
    
    # Call weather API
    try:
        api_key = "YOUR_API_KEY"  # In production, use os.getenv("WEATHER_API_KEY")
        url = f"https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": location,
            "appid": api_key,
            "units": units,
        }
        
        response = requests.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        
        return {
            "location": data["name"],
            "temperature": data["main"]["temp"],
            "conditions": data["weather"][0]["description"],
            "humidity": data["main"]["humidity"],
            "units": units,
        }
    
    except requests.ConnectionError as e:
        # Retryable error
        raise ConnectionError(f"Weather API unavailable: {e}")
    except requests.Timeout as e:
        # Retryable error
        raise TimeoutError(f"Weather API timeout: {e}")
    except requests.HTTPError as e:
        # Non-retryable error (e.g., 404 for invalid location)
        if e.response.status_code == 404:
            raise ValueError(f"Location not found: {location}")
        raise RuntimeError(f"Weather API error: {e}")
```

### Step 3: Define ToolSpec

```python
# weather_tool.py (continued)
from cuga.modular.tools import ToolSpec

WEATHER_TOOL = ToolSpec(
    # Identity
    name="get_weather",
    description="Get current weather conditions for any location worldwide",
    
    # Handler
    handler=get_weather,
    
    # Parameters
    parameters={
        "location": {
            "type": "string",
            "required": True,
            "description": "City name (e.g., 'London') or ZIP code (e.g., '10001')",
            "minLength": 2,
            "maxLength": 100,
        },
        "units": {
            "type": "string",
            "required": False,
            "default": "metric",
            "enum": ["metric", "imperial"],
            "description": "Temperature units (metric=Celsius, imperial=Fahrenheit)",
        },
    },
    
    # Budget
    cost=0.5,  # Medium cost (external API call)
    
    # Sandbox
    sandbox_profile="py-full",  # Need network access
    network_allowed=True,       # External API
    read_only=True,             # No file writes
    timeout=15.0,               # 15 second timeout
    allowlist=["requests"],     # Allow requests library
    
    # Metadata
    tags=["weather", "api", "external"],
    version="1.0.0",
)
```

### Step 4: Write Tests

```python
# tests/tools/test_weather_tool.py
import pytest
from unittest.mock import patch, Mock
from weather_tool import get_weather

def test_get_weather_success():
    """Test successful weather fetch."""
    inputs = {"location": "London", "units": "metric"}
    context = {"profile": "test", "trace_id": "test-123"}
    
    # Mock API response
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = {
            "name": "London",
            "main": {
                "temp": 15.5,
                "humidity": 72,
            },
            "weather": [{"description": "cloudy"}],
        }
        mock_get.return_value = mock_response
        
        result = get_weather(inputs, context)
        
        assert result["location"] == "London"
        assert result["temperature"] == 15.5
        assert result["conditions"] == "cloudy"
        assert result["humidity"] == 72
        assert result["units"] == "metric"

def test_get_weather_missing_location():
    """Test validation error for missing location."""
    inputs = {}
    context = {"profile": "test", "trace_id": "test-123"}
    
    with pytest.raises(ValueError, match="Location is required"):
        get_weather(inputs, context)

def test_get_weather_invalid_units():
    """Test validation error for invalid units."""
    inputs = {"location": "London", "units": "kelvin"}
    context = {"profile": "test", "trace_id": "test-123"}
    
    with pytest.raises(ValueError, match="Invalid units"):
        get_weather(inputs, context)

def test_get_weather_connection_error():
    """Test retryable connection error."""
    inputs = {"location": "London"}
    context = {"profile": "test", "trace_id": "test-123"}
    
    with patch('requests.get', side_effect=requests.ConnectionError("Network down")):
        with pytest.raises(ConnectionError, match="API unavailable"):
            get_weather(inputs, context)

def test_get_weather_location_not_found():
    """Test non-retryable 404 error."""
    inputs = {"location": "InvalidCity123"}
    context = {"profile": "test", "trace_id": "test-123"}
    
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            response=Mock(status_code=404)
        )
        mock_get.return_value = mock_response
        
        with pytest.raises(ValueError, match="Location not found"):
            get_weather(inputs, context)

def test_get_weather_integration():
    """Test weather tool in WorkerAgent."""
    from cuga.modular.tools import ToolRegistry
    from cuga.modular.agents import WorkerAgent
    from cuga.modular.memory import VectorMemory
    from weather_tool import WEATHER_TOOL
    
    registry = ToolRegistry(tools=[WEATHER_TOOL])
    worker = WorkerAgent(registry=registry, memory=VectorMemory())
    
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = {
            "name": "Paris",
            "main": {"temp": 18.0, "humidity": 65},
            "weather": [{"description": "sunny"}],
        }
        mock_get.return_value = mock_response
        
        result = worker.execute([
            {"tool": "get_weather", "input": {"location": "Paris"}}
        ])
        
        assert result.status == "success"
        assert result.output["location"] == "Paris"
        assert result.output["temperature"] == 18.0
```

### Step 5: Run Tests

```bash
# Install test dependencies
pip install pytest pytest-cov requests-mock

# Run unit tests
pytest tests/tools/test_weather_tool.py -v

# Run with coverage
pytest tests/tools/test_weather_tool.py --cov=weather_tool --cov-report=term-missing

# Expected output:
# ====== test session starts ======
# tests/tools/test_weather_tool.py::test_get_weather_success PASSED
# tests/tools/test_weather_tool.py::test_get_weather_missing_location PASSED
# tests/tools/test_weather_tool.py::test_get_weather_invalid_units PASSED
# tests/tools/test_weather_tool.py::test_get_weather_connection_error PASSED
# tests/tools/test_weather_tool.py::test_get_weather_location_not_found PASSED
# tests/tools/test_weather_tool.py::test_get_weather_integration PASSED
# ====== 6 passed in 0.23s ======
```

### Step 6: Register in Registry

Option A - Programmatic:

```python
# main.py
from cuga.modular.tools import ToolRegistry
from weather_tool import WEATHER_TOOL

registry = ToolRegistry(tools=[WEATHER_TOOL])
```

Option B - File-based (registry.yaml):

```yaml
# registry.yaml
tools:
  - name: get_weather
    module: weather_tool
    spec: WEATHER_TOOL
    enabled: true
    tier: 1
    cost: 0.5
    sandbox_profile: py-full
```

### Step 7: Use in Production

```python
# app.py
from cuga.modular.tools import ToolRegistry
from cuga.modular.agents import WorkerAgent, CoordinatorAgent, PlannerAgent
from cuga.modular.memory import VectorMemory
from weather_tool import WEATHER_TOOL

# Setup
registry = ToolRegistry(tools=[WEATHER_TOOL])
memory = VectorMemory()
planner = PlannerAgent(registry=registry, memory=memory)
worker = WorkerAgent(registry=registry, memory=memory)
coordinator = CoordinatorAgent(
    planner=planner,
    workers=[worker],
    memory=memory,
)

# Execute
goal = "What's the weather in Tokyo?"
result = coordinator.process(goal)

print(result.output)
# Output: "The current weather in Tokyo is 22°C with partly cloudy conditions and 60% humidity."
```

---

## Common Patterns

### Pattern 1: API Client Tool

```python
def api_client_handler(inputs, context):
    """Generic API client pattern."""
    import requests
    
    # Input validation
    endpoint = inputs.get("endpoint")
    if not endpoint:
        raise ValueError("Endpoint is required")
    
    # Build request
    method = inputs.get("method", "GET")
    headers = inputs.get("headers", {})
    params = inputs.get("params", {})
    data = inputs.get("data")
    
    # Make request with retry on network errors
    try:
        response = requests.request(
            method=method,
            url=endpoint,
            headers=headers,
            params=params,
            json=data,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
    
    except requests.ConnectionError as e:
        raise ConnectionError(f"API unavailable: {e}")
    except requests.Timeout as e:
        raise TimeoutError(f"Request timeout: {e}")
    except requests.HTTPError as e:
        if e.response.status_code >= 500:
            raise ConnectionError(f"Server error: {e}")  # Retryable
        raise RuntimeError(f"Client error: {e}")  # Not retryable
```

### Pattern 2: Database Tool

```python
def database_handler(inputs, context):
    """Database query pattern."""
    import sqlite3
    
    # Input validation
    query = inputs.get("query", "").strip()
    if not query.upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries allowed")
    
    database = inputs.get("database")
    if not database:
        raise ValueError("Database path is required")
    
    # Execute with timeout
    try:
        conn = sqlite3.connect(database, timeout=10.0)
        cursor = conn.execute(query)
        results = cursor.fetchall()
        conn.close()
        
        return {"results": results, "row_count": len(results)}
    
    except sqlite3.OperationalError as e:
        if "timeout" in str(e).lower():
            raise TimeoutError(f"Query timeout: {e}")
        raise RuntimeError(f"Database error: {e}")
```

### Pattern 3: File Processing Tool

```python
def file_processor_handler(inputs, context):
    """File processing pattern."""
    import os
    
    # Input validation
    file_path = inputs.get("file_path")
    if not file_path:
        raise ValueError("File path is required")
    
    # Security: Ensure path is within workdir
    workdir = "/workdir"
    abs_path = os.path.abspath(os.path.join(workdir, file_path))
    if not abs_path.startswith(workdir):
        raise ValueError("File path must be within /workdir")
    
    # Check file exists
    if not os.path.exists(abs_path):
        raise ValueError(f"File not found: {file_path}")
    
    # Process file
    try:
        with open(abs_path, 'r') as f:
            content = f.read()
        
        # Your processing logic
        lines = content.split('\n')
        
        return {
            "file": file_path,
            "lines": len(lines),
            "chars": len(content),
        }
    
    except IOError as e:
        raise RuntimeError(f"File error: {e}")
```

### Pattern 4: Batch Processing Tool

```python
def batch_processor_handler(inputs, context):
    """Batch processing pattern."""
    items = inputs.get("items", [])
    if not items:
        raise ValueError("Items list is required")
    
    batch_size = inputs.get("batch_size", 10)
    
    results = []
    errors = []
    
    # Process in batches
    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        
        for item in batch:
            try:
                result = process_item(item)
                results.append(result)
            except Exception as e:
                errors.append({"item": item, "error": str(e)})
    
    return {
        "processed": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }
```

### Pattern 5: Cached Tool

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_lookup(key: str) -> dict:
    """Expensive operation with caching."""
    # Simulate expensive computation
    import time
    time.sleep(1.0)
    return {"key": key, "value": f"result_{key}"}

def cached_handler(inputs, context):
    """Tool with result caching."""
    key = inputs.get("key")
    if not key:
        raise ValueError("Key is required")
    
    # Use cached function
    result = cached_lookup(key)
    
    return result
```

---

## Troubleshooting

### Problem: "Tool not found"

```python
# Check registered tools
registry = ToolRegistry(tools=[...])
print(registry.list_tools())

# Verify tool name matches
tool = ToolSpec(name="my_tool", ...)  # Must match exactly in execute()
worker.execute([{"tool": "my_tool", ...}])  # Case-sensitive!
```

### Problem: "Parameter validation failed"

```python
# Check parameter schema
tool = ToolSpec(
    parameters={
        "name": {"type": "string", "required": True},  # Must provide!
    }
)

# Provide all required parameters
worker.execute([
    {"tool": "my_tool", "input": {"name": "value"}}  # ✓
])
```

### Problem: "Tool always retries even on validation errors"

```python
# Use correct exception types
def handler(inputs, context):
    if not inputs.get("value"):
        # Wrong: ConnectionError (retryable)
        # raise ConnectionError("Missing value")
        
        # Correct: ValueError (not retryable)
        raise ValueError("Value is required")
```

### Problem: "Import denied in sandbox"

```python
# Add module to allowlist
tool = ToolSpec(
    sandbox_profile="py-full",
    allowlist=["requests", "json", "datetime"],  # Explicitly allow
)
```

### Problem: "Budget exceeded"

```python
# Option 1: Increase budget
worker = WorkerAgent(
    guardrail_policy={"budget_ceiling": 100.0}  # Increase limit
)

# Option 2: Reduce tool costs
tool = ToolSpec(cost=0.1)  # Lower cost

# Option 3: Optimize plan (fewer steps)
```

---

## Next Steps

1. **Read Full Guide:** [Modular Tool Integration](MODULAR_TOOL_INTEGRATION.md)
2. **Explore Examples:** `docs/tools/examples/`
3. **Check Best Practices:** Security, performance, testing patterns
4. **Join Community:** Discord, GitHub discussions

## Quick Reference

### Handler Signature
```python
def handler(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any
```

### ToolSpec Essentials
```python
ToolSpec(
    name="tool_name",
    description="What it does",
    handler=handler_function,
    parameters={...},
    cost=0.5,
)
```

### Retryable Errors
- `ConnectionError` - Network failures
- `TimeoutError` - Request timeouts
- Errors with "network"/"timeout" in message

### Non-Retryable Errors
- `ValueError` - Invalid inputs
- `TypeError` - Type mismatches
- `RuntimeError` - Logic errors

### Testing
```bash
pytest tests/tools/test_my_tool.py -v
```

Happy tooling! 🛠️
