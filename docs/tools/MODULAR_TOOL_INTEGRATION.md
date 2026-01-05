# Modular Tool Integration Guide

**Version:** 1.3.1  
**Last Updated:** 2026-01-03

## Overview

This guide explains how to integrate new tools into the Cuga agent system using a plugin-style architecture. Tools are modular, sandboxed, budget-tracked, and automatically retried on transient failures.

## Quick Start

### 1. Create Tool Handler

```python
# my_tools/weather.py
from typing import Dict, Any

def get_weather(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get weather for a location.
    
    Args:
        inputs: Tool input parameters (validated against ToolSpec.parameters)
            - location: str (required) - City name or ZIP code
            - units: str (optional) - "metric" or "imperial" (default: metric)
        context: Execution context
            - profile: str - Execution profile (test/dev/prod)
            - trace_id: str - Request trace ID for observability
            
    Returns:
        Weather data dictionary with temperature, conditions, humidity
        
    Raises:
        ValueError: Invalid location or units
        ConnectionError: API unavailable (retryable)
        TimeoutError: Request timeout (retryable)
    """
    location = inputs.get("location")
    units = inputs.get("units", "metric")
    
    if not location:
        raise ValueError("Location is required")
    
    # Your implementation here
    # Use context["trace_id"] for logging
    # Raise ConnectionError/TimeoutError for retryable failures
    
    return {
        "location": location,
        "temperature": 22,
        "conditions": "Partly cloudy",
        "humidity": 65,
        "units": units,
    }
```

### 2. Register Tool in Registry

```python
# Add to registry.yaml or programmatically
from cuga.modular.tools import ToolSpec, ToolRegistry

weather_tool = ToolSpec(
    name="get_weather",
    description="Get current weather for a location",
    handler=get_weather,
    parameters={
        "location": {"type": "string", "required": True, "description": "City or ZIP"},
        "units": {"type": "string", "required": False, "default": "metric"},
    },
    cost=0.1,  # Budget cost per call
    sandbox_profile="py-slim",  # Execution sandbox
    approval_required=False,  # No HITL approval needed
)

registry = ToolRegistry(tools=[weather_tool])
```

### 3. Use Tool in Agent

```python
from cuga.modular.agents import WorkerAgent
from cuga.modular.memory import VectorMemory

worker = WorkerAgent(registry=registry, memory=VectorMemory())

steps = [
    {
        "tool": "get_weather",
        "input": {"location": "San Francisco", "units": "imperial"}
    }
]

result = worker.execute(steps)
print(result.output)  # Weather data
```

That's it! The tool is now:
- ✅ Validated against parameter schema
- ✅ Executed in sandboxed environment
- ✅ Budget-tracked per call
- ✅ Automatically retried on transient failures
- ✅ Traced with observability events

## Tool Handler Contract

### Signature

```python
def tool_handler(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any:
    """
    Standard tool handler signature.
    
    Args:
        inputs: User-provided parameters (validated against ToolSpec.parameters)
        context: Execution context with profile, trace_id, etc.
        
    Returns:
        Tool output (any JSON-serializable type)
        
    Raises:
        ValueError/TypeError: Invalid inputs (not retried)
        ConnectionError: Network errors (retried)
        TimeoutError: Timeouts (retried)
        RuntimeError: General logic errors (not retried by default)
    """
    pass
```

### Input Parameters

The `inputs` dict contains:
- **User-provided values**: Validated against `ToolSpec.parameters` schema
- **Type-checked**: Strings, numbers, booleans, lists, dicts
- **Required fields**: Must be present or have defaults
- **Optional fields**: May be None if not provided

### Context Dictionary

The `context` dict provides:
- `profile` (str): Execution profile ("test", "dev", "prod")
- `trace_id` (str): Unique request trace ID for observability
- Additional metadata from orchestrator (optional)

### Return Values

Tool handlers can return:
- **Primitives**: str, int, float, bool
- **Collections**: list, dict (JSON-serializable)
- **Custom objects**: Implement `to_dict()` or `__dict__`
- **None**: Represents no output

### Exception Handling

**Retryable Exceptions** (transient failures):
- `ConnectionError`: Network/API unavailable
- `TimeoutError`: Request timeout
- Custom errors with "timeout"/"network" in message

**Non-Retryable Exceptions** (permanent failures):
- `ValueError`: Invalid input validation
- `TypeError`: Type mismatch
- `RuntimeError`: Logic errors (default)
- Custom errors with "validation"/"invalid" in message

**Terminal Exceptions** (stop execution):
- `PermissionError`: Security/permission denied
- Errors with "forbidden"/"security" in message

See [Retry Policy Integration](../orchestrator/RETRY_POLICY_INTEGRATION.md) for full FailureMode taxonomy.

## ToolSpec Configuration

### Basic ToolSpec

```python
from cuga.modular.tools import ToolSpec

tool = ToolSpec(
    name="my_tool",                    # Unique identifier
    description="What this tool does", # Used by planner for selection
    handler=my_handler_function,      # Callable matching signature
)
```

### Complete ToolSpec

```python
tool = ToolSpec(
    # Identity
    name="advanced_search",
    description="Search with advanced filters and pagination",
    
    # Handler
    handler=advanced_search_handler,
    
    # Parameters (JSON Schema-like)
    parameters={
        "query": {
            "type": "string",
            "required": True,
            "description": "Search query",
            "minLength": 1,
            "maxLength": 500,
        },
        "filters": {
            "type": "object",
            "required": False,
            "default": {},
            "properties": {
                "category": {"type": "string"},
                "date_range": {"type": "array", "items": {"type": "string"}},
            },
        },
        "page": {
            "type": "integer",
            "required": False,
            "default": 1,
            "minimum": 1,
            "maximum": 100,
        },
    },
    
    # Budget & Cost
    cost=0.5,              # Budget units per call
    max_tokens=1000,       # Token limit (if applicable)
    
    # Execution Environment
    sandbox_profile="py-full",  # Sandbox: py-slim, py-full, node-slim, node-full
    read_only=True,             # Filesystem read-only
    network_allowed=False,      # Network I/O allowed
    timeout=30.0,               # Execution timeout (seconds)
    
    # Security & Approval
    approval_required=False,    # Human-in-the-loop approval
    allowlist=["requests", "json"],  # Allowed imports
    denylist=[],                # Forbidden imports
    
    # Metadata
    tags=["search", "api", "external"],
    version="1.0.0",
    author="team@example.com",
)
```

### Parameter Schema

Parameters use JSON Schema conventions:

**Types:**
- `string`: Text values
- `integer`/`number`: Numeric values
- `boolean`: True/False
- `array`: Lists
- `object`: Dictionaries
- `null`: None

**Validation:**
- `required` (bool): Must be provided
- `default` (any): Default value if not provided
- `enum` (list): Allowed values
- `minimum`/`maximum` (number): Numeric bounds
- `minLength`/`maxLength` (int): String/array length
- `pattern` (str): Regex pattern for strings
- `properties` (dict): Nested object schema

**Example:**
```python
parameters={
    "email": {
        "type": "string",
        "required": True,
        "pattern": r"^[\w\.-]+@[\w\.-]+\.\w+$",
    },
    "priority": {
        "type": "string",
        "required": False,
        "default": "medium",
        "enum": ["low", "medium", "high", "urgent"],
    },
    "tags": {
        "type": "array",
        "items": {"type": "string"},
        "minLength": 1,
        "maxLength": 10,
    },
}
```

## Budget Configuration

### Per-Tool Costs

Each tool has a `cost` attribute (budget units per call):

```python
# Low-cost tools (local operations)
list_files = ToolSpec(name="list_files", handler=..., cost=0.01)

# Medium-cost tools (API calls)
search_api = ToolSpec(name="search", handler=..., cost=0.5)

# High-cost tools (LLM inference)
generate_text = ToolSpec(name="generate", handler=..., cost=5.0)
```

### Budget Enforcement

WorkerAgent tracks budget across tool calls:

```python
from cuga.modular.agents import WorkerAgent

worker = WorkerAgent(
    registry=registry,
    memory=memory,
    guardrail_policy={"budget_ceiling": 10.0},  # Max 10 units
)

steps = [
    {"tool": "search", "input": {}},      # 0.5 units
    {"tool": "generate", "input": {}},    # 5.0 units (5.5 total)
    {"tool": "generate", "input": {}},    # 5.0 units (10.5 total) → BUDGET_EXCEEDED
]

# Raises: OrchestrationError(mode=FailureMode.POLICY_BUDGET)
worker.execute(steps)
```

### Budget Policies

```python
# Warn on budget approach (80%)
guardrail_policy = {
    "budget_ceiling": 100.0,
    "budget_policy": "warn",  # Log warning, continue
    "budget_warning_threshold": 0.8,  # Warn at 80 units
}

# Block on budget exceeded (default)
guardrail_policy = {
    "budget_ceiling": 100.0,
    "budget_policy": "block",  # Raise error, stop execution
}
```

### Token Budgets

For LLM-based tools, track token usage:

```python
llm_tool = ToolSpec(
    name="chat",
    handler=chat_handler,
    cost=0.1,  # Per-call cost
    max_tokens=2000,  # Token limit per call
)

# Handler implementation
def chat_handler(inputs, context):
    response = llm.generate(
        inputs["prompt"],
        max_tokens=min(inputs.get("max_tokens", 1000), 2000)  # Enforce limit
    )
    return {
        "text": response.text,
        "tokens_used": response.usage.total_tokens,
    }
```

## Sandbox Profiles

### Available Profiles

**Python Sandboxes:**
- `py-slim`: Minimal Python (stdlib only, no network, read-only)
- `py-full`: Full Python (pip packages, network allowed, write access)

**Node.js Sandboxes:**
- `node-slim`: Minimal Node.js (core modules, no network, read-only)
- `node-full`: Full Node.js (npm packages, network allowed, write access)

**Orchestrator Sandbox:**
- `orchestrator`: High-privilege for system operations (use sparingly)

### Sandbox Configuration

```python
# Minimal sandbox (recommended for most tools)
tool = ToolSpec(
    name="process_data",
    handler=...,
    sandbox_profile="py-slim",
    read_only=True,
    network_allowed=False,
    timeout=10.0,
)

# Full sandbox (for external API calls)
tool = ToolSpec(
    name="fetch_api",
    handler=...,
    sandbox_profile="py-full",
    read_only=False,  # May cache responses
    network_allowed=True,
    timeout=30.0,
    allowlist=["requests", "httpx"],  # Allowed imports
)
```

### Import Allowlists

Control which modules tools can import:

```python
tool = ToolSpec(
    name="data_analysis",
    handler=...,
    sandbox_profile="py-full",
    allowlist=[
        "pandas",
        "numpy",
        "matplotlib",
        "seaborn",
    ],
    denylist=[
        "subprocess",  # No shell commands
        "os",          # No OS operations
    ],
)
```

### Filesystem Access

```python
# Read-only access to /workdir
tool = ToolSpec(
    name="read_config",
    handler=lambda inputs, ctx: open("/workdir/config.json").read(),
    sandbox_profile="py-slim",
    read_only=True,
)

# Write access for caching
tool = ToolSpec(
    name="cache_data",
    handler=lambda inputs, ctx: write_cache("/workdir/cache/", inputs["data"]),
    sandbox_profile="py-full",
    read_only=False,
)
```

## Approval Policies (HITL)

### Approval-Required Tools

Mark sensitive tools for human approval:

```python
tool = ToolSpec(
    name="delete_database",
    description="Permanently delete database records",
    handler=delete_handler,
    approval_required=True,  # Requires approval
    approval_timeout=300.0,  # Wait up to 5 minutes
)
```

### Approval Flow

```python
from cuga.orchestrator.approval import ApprovalPolicy, ApprovalRequest

# Define approval policy
approval_policy = ApprovalPolicy(
    auto_approve_tools=["list_files", "read_config"],  # Safe tools
    require_approval_tools=["delete_*", "modify_*"],   # Patterns
    approval_timeout=300.0,
)

# Integrate with worker
worker = WorkerAgent(
    registry=registry,
    memory=memory,
    approval_policy=approval_policy,
)

# Execute with approval callback
def approval_callback(request: ApprovalRequest) -> bool:
    """
    Handle approval request.
    
    Args:
        request: ApprovalRequest with tool_name, inputs, reason
        
    Returns:
        True to approve, False to deny
    """
    print(f"Approve {request.tool_name} with {request.inputs}? (y/n)")
    return input().lower() == 'y'

worker.approval_callback = approval_callback
result = worker.execute(steps)  # Pauses for approval
```

### Approval Events

Observability events emitted:
- `approval_requested`: Before waiting for approval
- `approval_received`: After approval granted
- `approval_denied`: After approval denied
- `approval_timeout`: After timeout expires

**Note:** Full approval implementation is pending (Task #6). This section describes planned functionality.

## Testing Requirements

### Unit Tests

Every tool handler must have unit tests:

```python
# tests/tools/test_weather.py
import pytest
from my_tools.weather import get_weather

def test_get_weather_success():
    """Test successful weather fetch."""
    inputs = {"location": "San Francisco", "units": "imperial"}
    context = {"profile": "test", "trace_id": "test-123"}
    
    result = get_weather(inputs, context)
    
    assert result["location"] == "San Francisco"
    assert result["units"] == "imperial"
    assert "temperature" in result

def test_get_weather_missing_location():
    """Test validation error for missing location."""
    inputs = {}
    context = {"profile": "test", "trace_id": "test-123"}
    
    with pytest.raises(ValueError, match="Location is required"):
        get_weather(inputs, context)

def test_get_weather_network_error():
    """Test retryable network error."""
    inputs = {"location": "InvalidCity"}
    context = {"profile": "test", "trace_id": "test-123"}
    
    # Mock network failure
    with pytest.raises(ConnectionError):
        get_weather(inputs, context)
```

### Integration Tests

Test tool within agent execution:

```python
# tests/integration/test_weather_integration.py
from cuga.modular.agents import WorkerAgent
from cuga.modular.tools import ToolRegistry, ToolSpec
from cuga.modular.memory import VectorMemory
from my_tools.weather import get_weather

def test_weather_tool_integration():
    """Test weather tool in WorkerAgent."""
    tool = ToolSpec(
        name="get_weather",
        handler=get_weather,
        parameters={
            "location": {"type": "string", "required": True},
        },
    )
    registry = ToolRegistry(tools=[tool])
    worker = WorkerAgent(registry=registry, memory=VectorMemory())
    
    steps = [{"tool": "get_weather", "input": {"location": "NYC"}}]
    result = worker.execute(steps)
    
    assert result.status == "success"
    assert "temperature" in result.output
```

### Retry Tests

Test transient failure handling:

```python
def test_weather_retries_on_network_error():
    """Test automatic retry on network errors."""
    call_count = {"value": 0}
    
    def flaky_handler(inputs, context):
        call_count["value"] += 1
        if call_count["value"] == 1:
            raise ConnectionError("Network unavailable")
        return {"temperature": 20}
    
    tool = ToolSpec(name="weather", handler=flaky_handler)
    registry = ToolRegistry(tools=[tool])
    worker = WorkerAgent(registry=registry, memory=VectorMemory())
    
    result = worker.execute([{"tool": "weather", "input": {}}])
    
    assert result.status == "success"
    assert call_count["value"] == 2  # Retried once
```

### Test Coverage Requirements

- **Unit tests:** 100% of handler logic
- **Integration tests:** At least 1 per tool
- **Retry tests:** For tools with external dependencies
- **Validation tests:** All parameter combinations

## Step-by-Step Example: Adding a New Tool

Let's add a complete tool from scratch:

### 1. Implement Handler

```python
# src/cuga/modular/tools/database_query.py
"""Database query tool for read-only SQL queries."""
from typing import Dict, Any
import sqlite3

def query_database(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute read-only SQL query against SQLite database.
    
    Args:
        inputs:
            - query: str (required) - SELECT query
            - database: str (required) - Database file path
            - limit: int (optional) - Row limit (default: 100)
        context:
            - profile: Execution profile
            - trace_id: Trace ID
            
    Returns:
        Query results with columns and rows
        
    Raises:
        ValueError: Invalid query (not SELECT)
        TimeoutError: Query timeout
    """
    query = inputs.get("query", "").strip()
    database = inputs.get("database")
    limit = inputs.get("limit", 100)
    
    # Validation
    if not query:
        raise ValueError("Query is required")
    if not database:
        raise ValueError("Database path is required")
    if not query.upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries allowed")
    
    # Add LIMIT clause
    if "LIMIT" not in query.upper():
        query = f"{query} LIMIT {limit}"
    
    # Execute query
    try:
        conn = sqlite3.connect(database, timeout=10.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query)
        
        # Fetch results
        columns = [desc[0] for desc in cursor.description]
        rows = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        }
    except sqlite3.OperationalError as e:
        if "timeout" in str(e).lower():
            raise TimeoutError(f"Query timeout: {e}")
        raise RuntimeError(f"Query error: {e}")
```

### 2. Create ToolSpec

```python
# src/cuga/modular/tools/__init__.py
from .database_query import query_database

DATABASE_QUERY_TOOL = ToolSpec(
    name="query_database",
    description="Execute read-only SQL SELECT queries against SQLite database",
    handler=query_database,
    parameters={
        "query": {
            "type": "string",
            "required": True,
            "description": "SELECT query to execute",
            "pattern": r"^\s*SELECT\s+",  # Must start with SELECT
        },
        "database": {
            "type": "string",
            "required": True,
            "description": "Path to SQLite database file",
        },
        "limit": {
            "type": "integer",
            "required": False,
            "default": 100,
            "minimum": 1,
            "maximum": 1000,
            "description": "Maximum rows to return",
        },
    },
    cost=0.2,  # Low cost (local operation)
    sandbox_profile="py-slim",
    read_only=True,
    network_allowed=False,
    timeout=30.0,
    allowlist=["sqlite3"],
    tags=["database", "sql", "query"],
    version="1.0.0",
)
```

### 3. Add to Registry

```yaml
# registry.yaml
tools:
  - name: query_database
    module: cuga.modular.tools
    spec: DATABASE_QUERY_TOOL
    enabled: true
    tier: 1
```

Or programmatically:

```python
from cuga.modular.tools import ToolRegistry, DATABASE_QUERY_TOOL

registry = ToolRegistry(tools=[DATABASE_QUERY_TOOL])
```

### 4. Write Tests

```python
# tests/tools/test_database_query.py
import pytest
import sqlite3
import tempfile
from cuga.modular.tools.database_query import query_database

@pytest.fixture
def test_db():
    """Create temporary test database."""
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    conn = sqlite3.connect(db.name)
    conn.execute("CREATE TABLE users (id INTEGER, name TEXT, email TEXT)")
    conn.execute("INSERT INTO users VALUES (1, 'Alice', 'alice@example.com')")
    conn.execute("INSERT INTO users VALUES (2, 'Bob', 'bob@example.com')")
    conn.commit()
    conn.close()
    yield db.name
    import os
    os.unlink(db.name)

def test_query_database_success(test_db):
    """Test successful query execution."""
    inputs = {
        "query": "SELECT * FROM users",
        "database": test_db,
    }
    context = {"profile": "test", "trace_id": "test-123"}
    
    result = query_database(inputs, context)
    
    assert result["row_count"] == 2
    assert result["columns"] == ["id", "name", "email"]
    assert result["rows"][0]["name"] == "Alice"

def test_query_database_limit(test_db):
    """Test query with row limit."""
    inputs = {
        "query": "SELECT * FROM users",
        "database": test_db,
        "limit": 1,
    }
    context = {"profile": "test", "trace_id": "test-123"}
    
    result = query_database(inputs, context)
    
    assert result["row_count"] == 1

def test_query_database_missing_query():
    """Test validation error for missing query."""
    inputs = {"database": "test.db"}
    context = {"profile": "test", "trace_id": "test-123"}
    
    with pytest.raises(ValueError, match="Query is required"):
        query_database(inputs, context)

def test_query_database_non_select(test_db):
    """Test rejection of non-SELECT queries."""
    inputs = {
        "query": "DELETE FROM users",
        "database": test_db,
    }
    context = {"profile": "test", "trace_id": "test-123"}
    
    with pytest.raises(ValueError, match="Only SELECT queries allowed"):
        query_database(inputs, context)

def test_query_database_integration():
    """Test tool in WorkerAgent."""
    from cuga.modular.agents import WorkerAgent
    from cuga.modular.tools import ToolRegistry, ToolSpec
    from cuga.modular.memory import VectorMemory
    
    # Create test database
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    conn = sqlite3.connect(db.name)
    conn.execute("CREATE TABLE items (id INTEGER, value TEXT)")
    conn.execute("INSERT INTO items VALUES (1, 'test')")
    conn.commit()
    conn.close()
    
    # Create tool and worker
    tool = ToolSpec(
        name="query_db",
        handler=query_database,
        parameters={
            "query": {"type": "string", "required": True},
            "database": {"type": "string", "required": True},
        },
    )
    registry = ToolRegistry(tools=[tool])
    worker = WorkerAgent(registry=registry, memory=VectorMemory())
    
    # Execute query
    steps = [{
        "tool": "query_db",
        "input": {
            "query": "SELECT * FROM items",
            "database": db.name,
        },
    }]
    result = worker.execute(steps)
    
    assert result.status == "success"
    assert result.output["row_count"] == 1
    
    # Cleanup
    import os
    os.unlink(db.name)
```

### 5. Run Tests

```bash
# Unit tests
pytest tests/tools/test_database_query.py -v

# Integration tests
pytest tests/integration/ -k database -v

# All tests
pytest tests/ -v
```

### 6. Document Tool

```python
# docs/tools/examples/database_query_example.md
"""
## Database Query Tool

Execute read-only SQL queries against SQLite databases.

### Usage

```python
from cuga.modular.agents import WorkerAgent
from cuga.modular.tools import ToolRegistry, DATABASE_QUERY_TOOL

registry = ToolRegistry(tools=[DATABASE_QUERY_TOOL])
worker = WorkerAgent(registry=registry, memory=memory)

steps = [{
    "tool": "query_database",
    "input": {
        "query": "SELECT name, email FROM users WHERE active = 1",
        "database": "/data/users.db",
        "limit": 50,
    },
}]

result = worker.execute(steps)
print(result.output["rows"])
```

### Parameters

- **query** (string, required): SELECT query to execute
- **database** (string, required): Path to SQLite database file  
- **limit** (integer, optional): Maximum rows (default: 100, max: 1000)

### Returns

```json
{
  "columns": ["name", "email"],
  "rows": [
    {"name": "Alice", "email": "alice@example.com"},
    {"name": "Bob", "email": "bob@example.com"}
  ],
  "row_count": 2
}
```

### Errors

- **ValueError**: Invalid query (not SELECT, missing params)
- **TimeoutError**: Query timeout (retryable)
- **RuntimeError**: Database error (syntax, file not found)
"""
```

### 7. Update Allowlist

Add tool to allowlisted imports:

```python
# src/cuga/security/allowlist.py
ALLOWED_TOOL_MODULES = [
    "cuga.modular.tools.*",
    "cuga.modular.tools.database_query",  # Add new tool
]
```

## Best Practices

### 1. Design Principles

**Single Responsibility:**
```python
# Good: One tool, one task
get_weather = ToolSpec(name="get_weather", handler=...)
forecast_weather = ToolSpec(name="forecast_weather", handler=...)

# Bad: One tool, multiple tasks
weather_operations = ToolSpec(name="weather_ops", handler=...)  # Too broad
```

**Idempotency:**
```python
# Good: Repeated calls same result
def get_user(inputs, context):
    return db.fetch_user(inputs["user_id"])

# Bad: Side effects on read
def get_user_and_increment_views(inputs, context):
    user = db.fetch_user(inputs["user_id"])
    db.increment_views(inputs["user_id"])  # Retry causes extra increments
    return user
```

**Error Messages:**
```python
# Good: Specific, actionable
raise ValueError("Location 'XYZ' not found. Available: NYC, LAX, SFO")

# Bad: Generic, unhelpful
raise ValueError("Invalid input")
```

### 2. Performance Optimization

**Caching:**
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def expensive_operation(key: str) -> dict:
    """Cache expensive computations."""
    return compute_result(key)

def tool_handler(inputs, context):
    return expensive_operation(inputs["key"])
```

**Streaming:**
```python
def stream_results(inputs, context):
    """Stream large results incrementally."""
    for chunk in large_data_source(inputs["query"]):
        yield {"chunk": chunk, "done": False}
    yield {"chunk": None, "done": True}
```

**Pagination:**
```python
def paginated_handler(inputs, context):
    """Support pagination for large result sets."""
    page = inputs.get("page", 1)
    page_size = inputs.get("page_size", 50)
    
    results = fetch_all_results(inputs["query"])
    start = (page - 1) * page_size
    end = start + page_size
    
    return {
        "results": results[start:end],
        "page": page,
        "total_pages": (len(results) + page_size - 1) // page_size,
        "total_results": len(results),
    }
```

### 3. Security Best Practices

**Input Sanitization:**
```python
def safe_handler(inputs, context):
    # Validate and sanitize inputs
    query = inputs["query"].strip()
    if not query:
        raise ValueError("Empty query")
    
    # Escape special characters
    safe_query = escape_sql(query)
    
    # Use parameterized queries
    cursor.execute("SELECT * FROM users WHERE name = ?", (safe_query,))
```

**Secret Management:**
```python
import os

def api_handler(inputs, context):
    # Load secrets from environment
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise RuntimeError("API_KEY not configured")
    
    # Never log secrets
    # logger.debug(f"Using key: {api_key}")  # BAD!
    logger.debug("Using configured API key")  # GOOD
```

**Rate Limiting:**
```python
from time import time

rate_limiter = {"calls": [], "limit": 100, "window": 60}

def rate_limited_handler(inputs, context):
    now = time()
    
    # Remove old calls outside window
    rate_limiter["calls"] = [t for t in rate_limiter["calls"] if now - t < rate_limiter["window"]]
    
    # Check limit
    if len(rate_limiter["calls"]) >= rate_limiter["limit"]:
        raise RuntimeError("Rate limit exceeded. Try again later.")
    
    # Record call
    rate_limiter["calls"].append(now)
    
    # Proceed with operation
    return perform_operation(inputs)
```

### 4. Testing Best Practices

**Mock External Dependencies:**
```python
from unittest.mock import patch

def test_api_handler_success():
    """Test API handler with mocked response."""
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {"status": "ok"}
        
        result = api_handler({"endpoint": "/status"}, {"trace_id": "test"})
        
        assert result["status"] == "ok"
        mock_get.assert_called_once()
```

**Test Error Paths:**
```python
def test_handler_errors():
    """Test all error conditions."""
    # Missing required field
    with pytest.raises(ValueError, match="required"):
        handler({}, {})
    
    # Invalid type
    with pytest.raises(TypeError):
        handler({"count": "invalid"}, {})
    
    # Network error (retryable)
    with patch('requests.get', side_effect=ConnectionError):
        with pytest.raises(ConnectionError):
            handler({"url": "..."}, {})
```

**Test Retry Behavior:**
```python
def test_handler_retries():
    """Test automatic retry on transient errors."""
    call_count = {"value": 0}
    
    def flaky_handler(inputs, context):
        call_count["value"] += 1
        if call_count["value"] < 3:
            raise ConnectionError("Temporary failure")
        return {"success": True}
    
    tool = ToolSpec(name="flaky", handler=flaky_handler)
    registry = ToolRegistry(tools=[tool])
    worker = WorkerAgent(registry=registry, memory=VectorMemory())
    
    result = worker.execute([{"tool": "flaky", "input": {}}])
    
    assert result.status == "success"
    assert call_count["value"] == 3  # Retried twice, succeeded on third
```

## Troubleshooting

### Tool Not Found

**Error:** `ToolNotFoundError: Tool 'my_tool' not registered`

**Solutions:**
1. Check tool name matches ToolSpec.name
2. Verify tool in registry: `print(registry.list_tools())`
3. Check registry.yaml if using file-based registration

### Parameter Validation Failure

**Error:** `ValidationError: Missing required parameter 'location'`

**Solutions:**
1. Check parameter schema matches inputs
2. Verify required fields are provided
3. Check default values for optional fields

### Import Denied

**Error:** `ImportError: Module 'requests' not in allowlist`

**Solutions:**
1. Add module to ToolSpec.allowlist: `allowlist=["requests"]`
2. Use allowed sandbox profile (py-full vs py-slim)
3. Check ALLOWED_TOOL_MODULES in security/allowlist.py

### Budget Exceeded

**Error:** `OrchestrationError: POLICY_BUDGET exceeded`

**Solutions:**
1. Increase budget ceiling: `guardrail_policy={"budget_ceiling": 50.0}`
2. Reduce tool costs: Lower ToolSpec.cost values
3. Optimize plan steps: Fewer tool calls

### Tool Timeout

**Error:** `TimeoutError: Tool execution exceeded 30.0s`

**Solutions:**
1. Increase timeout: `ToolSpec(timeout=60.0)`
2. Optimize handler: Profile slow operations
3. Use streaming: Yield incremental results

### Sandbox Violation

**Error:** `SecurityError: Write access denied in read-only sandbox`

**Solutions:**
1. Use write-enabled profile: `sandbox_profile="py-full"`
2. Set read_only=False: `ToolSpec(read_only=False)`
3. Write to /workdir: Ensure path is within sandbox

## Migration from Legacy Tools

### Old Pattern (Direct Functions)

```python
# Old: Direct function calls
def my_function(arg1, arg2):
    return result

result = my_function("value1", "value2")
```

### New Pattern (ToolSpec)

```python
# New: ToolSpec with handler
def my_handler(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any:
    arg1 = inputs["arg1"]
    arg2 = inputs["arg2"]
    return result

tool = ToolSpec(
    name="my_tool",
    handler=my_handler,
    parameters={
        "arg1": {"type": "string", "required": True},
        "arg2": {"type": "string", "required": True},
    },
)

# Execute via worker
worker.execute([{"tool": "my_tool", "input": {"arg1": "value1", "arg2": "value2"}}])
```

### Migration Checklist

- [ ] Convert function to handler signature (inputs, context)
- [ ] Define parameter schema
- [ ] Add ToolSpec with name, description, handler
- [ ] Register tool in ToolRegistry
- [ ] Update call sites to use worker.execute()
- [ ] Add unit tests for handler
- [ ] Add integration test with WorkerAgent
- [ ] Document tool usage

## Related Documentation

- [Retry Policy Integration](../orchestrator/RETRY_POLICY_INTEGRATION.md) - Automatic retry behavior
- [Tool Creation Guide](TOOL_CREATION_GUIDE.md) - Step-by-step tutorial
- [Sandbox Security](../security/SANDBOXING.md) - Sandbox profiles and isolation
- [Budget Enforcement](../orchestrator/BUDGET_ENFORCEMENT.md) - Cost tracking
- [Approval Gates](../orchestrator/APPROVAL_GATES.md) - HITL approval workflows (planned)

## Support

For questions or issues:
1. Check [FAQ](FAQ.md)
2. Search [GitHub Issues](https://github.com/TylrDn/cugar-agent/issues)
3. Join [Discord](https://discord.gg/cugar-agent)
4. Email: support@cugar-agent.dev
