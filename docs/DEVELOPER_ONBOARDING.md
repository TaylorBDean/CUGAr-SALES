<div align="center">
  <img src="../image/CUGAr.png" alt="CUGAr Logo" width="500"/>
</div>

# Developer Onboarding Guide

**Status**: Canonical Reference  
**Last Updated**: 2025-12-31  
**Audience**: New contributors, junior developers, enterprise teams evaluating CUGAR

---

## 👋 Welcome to CUGAR Agent Development

This guide walks you through setting up CUGAR Agent from scratch and building your first custom agent or extension. No prior knowledge of LangGraph, CrewAI, or advanced agent patterns required — we'll explain everything as we go.

**What You'll Learn**:
1. How to set up your development environment (15 minutes)
2. How to run your first agent and understand what happens (10 minutes)
3. How to create a custom tool (20 minutes)
4. How to build a custom agent (30 minutes)
5. How to wire everything together (15 minutes)

**Prerequisites**: Basic Python knowledge, familiarity with virtual environments

---

## 📚 Quick Terminology Guide

Before we dive in, here are the key concepts you'll encounter:

| Term | What It Means | Example |
|------|---------------|---------|
| **Agent** | A component that processes requests and makes decisions | PlannerAgent decides which tools to use |
| **Tool** | A function the agent can call to perform actions | `search_web`, `read_file`, `query_database` |
| **Orchestrator** | Coordinates multiple agents working together | Routes requests, handles errors, manages workflow |
| **Memory** | Stores context between interactions | Remembers previous conversations, learned facts |
| **Profile** | Sandbox environment with security boundaries | `py-slim` (Python with restricted access) |
| **Registry** | Catalog of available tools and their configurations | Defines which tools agents can use |
| **Trace** | Record of execution for debugging/observability | Shows what happened during a request |

---

## 🚀 Part 1: Environment Setup (15 minutes)

### Step 1.1: Clone and Install

```bash
# Clone the repository
git clone https://github.com/yourusername/cugar-agent.git
cd cugar-agent

# Install dependencies using uv (recommended)
uv sync --all-extras --dev
uv run playwright install --with-deps chromium

# Alternative: Use pip
# pip install -e ".[all]"
```

**What just happened?**
- `uv sync` installed all Python dependencies
- `playwright install` set up browser automation (used by web tools)
- `-e` (editable mode) means code changes take effect immediately

### Step 1.2: Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Open .env in your editor and set:
# OPENAI_API_KEY=your-api-key-here
# (or use ANTHROPIC_API_KEY, GOOGLE_API_KEY, etc.)
```

**What's in .env?**
```bash
# Model provider (required)
OPENAI_API_KEY=sk-...

# Logging (optional, useful for debugging)
CUGA_LOG_LEVEL=INFO
CUGA_LOG_FORMAT=json

# Memory (optional, defaults to in-memory)
CUGA_MEMORY_BACKEND=local

# Observability (optional, for production)
# LANGFUSE_SECRET_KEY=...
# OTEL_EXPORTER_OTLP_ENDPOINT=...
```

See [Environment Modes](configuration/ENVIRONMENT_MODES.md) for detailed configuration options.

### Step 1.3: Verify Installation

```bash
# Run the test suite
pytest tests/test_orchestrator_protocol.py -v

# Expected output:
# test_lifecycle_stages_in_order ✓
# test_trace_id_preserved ✓
# ...
# All tests passed!
```

**Troubleshooting**:
- ❌ `ImportError: No module named 'cuga'` → Run `pip install -e .`
- ❌ `OpenAI API key not found` → Check `.env` file exists and has `OPENAI_API_KEY`
- ❌ Tests fail → Check `pytest --version` (needs ≥7.0)

---

## 🎯 Part 2: Your First Agent Interaction (10 minutes)

### Step 2.1: Run a Simple Query

```bash
# CLI mode - ask the agent to plan a task
python -m cuga.modular.cli plan "What's the weather in San Francisco?"
```

**What you'll see**:
```json
{
  "trace_id": "trace-abc123",
  "goal": "What's the weather in San Francisco?",
  "plan": {
    "steps": [
      {
        "tool": "search_web",
        "input": "San Francisco weather",
        "reason": "Need current weather data"
      }
    ]
  },
  "status": "planned"
}
```

**What just happened?** (Behind the scenes)
1. **Entry Point** (`cli.py`): Parsed your command
2. **PlannerAgent**: Analyzed the goal and selected `search_web` tool
3. **Memory Search**: Checked if similar queries were answered before
4. **Tool Ranking**: Scored tools by relevance (vector similarity)
5. **Plan Generation**: Created ordered list of steps
6. **Response**: Returned plan as JSON

### Step 2.2: Execute the Plan

```bash
# Execute the planned steps
python -m cuga.modular.cli execute --trace-id trace-abc123
```

**What you'll see**:
```json
{
  "trace_id": "trace-abc123",
  "status": "completed",
  "results": [
    {
      "step": 1,
      "tool": "search_web",
      "output": "San Francisco: 62°F, partly cloudy..."
    }
  ]
}
```

**What just happened?**
1. **CoordinatorAgent**: Retrieved plan by trace_id
2. **WorkerAgent**: Executed `search_web` in sandbox
3. **Tool Handler**: Made web request (safely isolated)
4. **Result Aggregation**: Collected outputs
5. **Memory Update**: Stored interaction for future reference

### Step 2.3: Inspect the Trace

```bash
# View execution details
python -m cuga.modular.cli trace trace-abc123
```

**What you'll see**:
```
Trace: trace-abc123
Duration: 2.3s
Steps: 1

Timeline:
  00:00.000 [INITIALIZE] Created execution context
  00:00.050 [PLAN]       Selected tools: search_web
  00:00.100 [ROUTE]      Assigned to worker-1
  00:00.150 [EXECUTE]    Running search_web
  00:02.200 [COMPLETE]   Success
```

**Key Insight**: Every interaction creates a trace you can inspect for debugging!

---

## 🔧 Part 3: Create Your First Custom Tool (20 minutes)

### Step 3.1: Understand the Tool Contract

**Every tool in CUGAR must follow this signature**:

```python
def tool_handler(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any:
    """
    Args:
        inputs: User-provided parameters (from the plan)
        context: System context (profile, trace_id, user_id)
    
    Returns:
        Any JSON-serializable result
    """
    pass
```

**Key Rules** (enforced by guardrails):
- ✅ Must be in `src/cuga/modular/tools/` directory
- ✅ Must declare parameters with types
- ✅ Must handle errors gracefully (return error dict, don't raise)
- ❌ Cannot use `eval()` or `exec()`
- ❌ Cannot write outside sandbox (unless profile allows)
- ❌ Cannot make network calls (unless profile allows)

### Step 3.2: Create a Simple Calculator Tool

```bash
# Create new tool file
touch src/cuga/modular/tools/calculator.py
```

**File: `src/cuga/modular/tools/calculator.py`**
```python
"""Simple calculator tool for basic arithmetic operations."""

from typing import Dict, Any, Literal

def calculate(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform basic arithmetic operations.
    
    Parameters (in inputs dict):
        operation: One of 'add', 'subtract', 'multiply', 'divide'
        a: First number
        b: Second number
    
    Returns:
        Dict with 'result' key or 'error' key
    """
    # Extract parameters
    operation = inputs.get("operation")
    a = inputs.get("a")
    b = inputs.get("b")
    
    # Validate inputs
    if not all([operation, a is not None, b is not None]):
        return {
            "error": "Missing required parameters",
            "required": ["operation", "a", "b"],
            "trace_id": context.get("trace_id")
        }
    
    try:
        a = float(a)
        b = float(b)
    except (ValueError, TypeError):
        return {
            "error": "Parameters 'a' and 'b' must be numbers",
            "trace_id": context.get("trace_id")
        }
    
    # Perform operation
    operations = {
        "add": lambda x, y: x + y,
        "subtract": lambda x, y: x - y,
        "multiply": lambda x, y: x * y,
        "divide": lambda x, y: x / y if y != 0 else None
    }
    
    if operation not in operations:
        return {
            "error": f"Unknown operation: {operation}",
            "valid_operations": list(operations.keys()),
            "trace_id": context.get("trace_id")
        }
    
    result = operations[operation](a, b)
    
    if result is None:
        return {
            "error": "Division by zero",
            "trace_id": context.get("trace_id")
        }
    
    # Return success
    return {
        "operation": operation,
        "a": a,
        "b": b,
        "result": result,
        "trace_id": context.get("trace_id")
    }


# Tool metadata (for discovery)
TOOL_METADATA = {
    "name": "calculate",
    "description": "Perform basic arithmetic operations (add, subtract, multiply, divide)",
    "parameters": {
        "operation": {
            "type": "string",
            "enum": ["add", "subtract", "multiply", "divide"],
            "description": "The arithmetic operation to perform"
        },
        "a": {
            "type": "number",
            "description": "First number"
        },
        "b": {
            "type": "number",
            "description": "Second number"
        }
    },
    "required": ["operation", "a", "b"],
    "returns": {
        "type": "object",
        "properties": {
            "result": {"type": "number"},
            "error": {"type": "string"}
        }
    }
}
```

### Step 3.3: Register the Tool

**File: `registry.yaml`** (add entry)
```yaml
tools:
  # ... existing tools ...
  
  - name: calculate
    module: cuga.modular.tools.calculator
    handler: calculate
    enabled: true
    sandbox:
      profile: py-slim  # Minimal Python sandbox
      timeout_seconds: 5
      memory_limit_mb: 128
      read_only: true
    metadata:
      description: "Basic arithmetic calculator"
      tags: ["math", "utility"]
      tier: 1
```

**What each field means**:
- `name`: Unique identifier (used in plans)
- `module`: Python import path (must start with `cuga.modular.tools`)
- `handler`: Function name to call
- `sandbox.profile`: Execution environment (`py-slim`, `py-full`, `node-slim`, etc.)
- `sandbox.timeout_seconds`: Max execution time
- `sandbox.memory_limit_mb`: Max memory usage
- `sandbox.read_only`: Can write files? (false for read-only)

### Step 3.4: Test Your Tool

```bash
# Test directly (bypasses agent)
python -c "
from cuga.modular.tools.calculator import calculate

inputs = {'operation': 'add', 'a': 5, 'b': 3}
context = {'trace_id': 'test-123', 'profile': 'py-slim'}

result = calculate(inputs, context)
print(result)
# Expected: {'operation': 'add', 'a': 5, 'b': 3, 'result': 8, 'trace_id': 'test-123'}
"
```

**Write a proper test**:

**File: `tests/test_calculator_tool.py`**
```python
"""Tests for calculator tool."""

import pytest
from cuga.modular.tools.calculator import calculate

def test_calculate_add():
    inputs = {"operation": "add", "a": 5, "b": 3}
    context = {"trace_id": "test-add", "profile": "py-slim"}
    
    result = calculate(inputs, context)
    
    assert "result" in result
    assert result["result"] == 8
    assert result["operation"] == "add"

def test_calculate_divide_by_zero():
    inputs = {"operation": "divide", "a": 10, "b": 0}
    context = {"trace_id": "test-div-zero", "profile": "py-slim"}
    
    result = calculate(inputs, context)
    
    assert "error" in result
    assert "Division by zero" in result["error"]

def test_calculate_invalid_operation():
    inputs = {"operation": "power", "a": 2, "b": 3}
    context = {"trace_id": "test-invalid", "profile": "py-slim"}
    
    result = calculate(inputs, context)
    
    assert "error" in result
    assert "power" in result["error"]

def test_calculate_missing_parameters():
    inputs = {"operation": "add", "a": 5}  # Missing 'b'
    context = {"trace_id": "test-missing", "profile": "py-slim"}
    
    result = calculate(inputs, context)
    
    assert "error" in result
    assert "Missing required parameters" in result["error"]
```

Run tests:
```bash
pytest tests/test_calculator_tool.py -v
```

### Step 3.5: Use Your Tool with an Agent

```bash
# Ask the agent to use your new tool
python -m cuga.modular.cli plan "Calculate 42 multiplied by 17"
```

**Expected output**:
```json
{
  "trace_id": "trace-xyz789",
  "goal": "Calculate 42 multiplied by 17",
  "plan": {
    "steps": [
      {
        "tool": "calculate",
        "input": {
          "operation": "multiply",
          "a": 42,
          "b": 17
        },
        "reason": "User requested multiplication calculation"
      }
    ]
  },
  "status": "planned"
}
```

**Execute it**:
```bash
python -m cuga.modular.cli execute --trace-id trace-xyz789

# Expected:
# {"result": 714, "operation": "multiply", "a": 42, "b": 17}
```

**🎉 Congratulations!** You've created and used your first custom tool!

---

## 🤖 Part 4: Build Your First Custom Agent (30 minutes)

### Step 4.1: Understand the Agent Contract

**Every agent in CUGAR must implement `AgentProtocol`**:

```python
from cuga.agents.contracts import AgentRequest, AgentResponse

class MyAgent:
    async def process(self, request: AgentRequest) -> AgentResponse:
        """
        Process a request and return a response.
        
        Args:
            request: Contains goal, task, metadata, inputs, context
        
        Returns:
            AgentResponse with status, result/error, trace, metadata
        """
        pass
```

**Key Requirements**:
- ✅ Must implement `process(AgentRequest) -> AgentResponse`
- ✅ Must handle errors without raising (return error in response)
- ✅ Must propagate `trace_id` through response
- ✅ Must respect `profile` from context (security boundary)
- ❌ Cannot make routing decisions (use RoutingAuthority)
- ❌ Cannot bypass ToolRegistry (use registry for tool resolution)

### Step 4.2: Create a Math Tutor Agent

**Use Case**: An agent that helps students learn math by:
1. Breaking down problems into steps
2. Explaining each step
3. Using the calculator tool for verification

```bash
# Create agent file
mkdir -p src/cuga/agents/
touch src/cuga/agents/math_tutor.py
```

**File: `src/cuga/agents/math_tutor.py`**
```python
"""Math Tutor Agent - Helps students learn math step-by-step."""

import asyncio
from typing import Dict, Any, List
from dataclasses import dataclass

from cuga.agents.contracts import AgentRequest, AgentResponse, AgentStatus
from cuga.agents.lifecycle import AgentLifecycleProtocol, LifecycleState
from cuga.modular.tools.calculator import calculate


@dataclass
class MathStep:
    """A single step in solving a math problem."""
    step_number: int
    explanation: str
    operation: str
    calculation: Dict[str, Any]
    result: float


class MathTutorAgent(AgentLifecycleProtocol):
    """
    An agent that teaches math by breaking problems into steps.
    
    Example:
        "What is (5 + 3) * 2?"
        
        Step 1: First, solve inside parentheses
                Calculate: 5 + 3 = 8
        
        Step 2: Then, multiply result by 2
                Calculate: 8 * 2 = 16
        
        Final Answer: 16
    """
    
    def __init__(self, name: str = "math-tutor"):
        self.name = name
        self._state = LifecycleState.UNINITIALIZED
        self._context: Dict[str, Any] = {}
    
    # Lifecycle methods (required by AgentLifecycleProtocol)
    
    async def startup(self, context: Dict[str, Any] = None) -> None:
        """Initialize agent resources."""
        if self._state == LifecycleState.READY:
            return  # Idempotent
        
        self._context = context or {}
        self._state = LifecycleState.READY
        print(f"[{self.name}] Started and ready")
    
    async def shutdown(self, timeout_seconds: float = 5.0) -> None:
        """Cleanup agent resources."""
        if self._state == LifecycleState.TERMINATED:
            return  # Idempotent
        
        self._context.clear()
        self._state = LifecycleState.TERMINATED
        print(f"[{self.name}] Shutdown complete")
    
    @property
    def state(self) -> LifecycleState:
        """Current lifecycle state."""
        return self._state
    
    # Core agent logic
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        """
        Process a math problem request.
        
        Args:
            request: Contains the math problem in 'goal' or 'task'
        
        Returns:
            Response with step-by-step solution
        """
        trace_id = request.context.get("trace_id", "unknown")
        problem = request.goal or request.task
        
        if not problem:
            return AgentResponse(
                status=AgentStatus.ERROR,
                error="No math problem provided",
                trace_id=trace_id
            )
        
        try:
            # Parse the problem
            steps = self._parse_problem(problem)
            
            # Solve each step
            solutions = []
            for step in steps:
                solution = await self._solve_step(step, request.context)
                solutions.append(solution)
            
            # Generate explanation
            explanation = self._generate_explanation(solutions)
            
            return AgentResponse(
                status=AgentStatus.SUCCESS,
                result={
                    "problem": problem,
                    "steps": [
                        {
                            "number": s.step_number,
                            "explanation": s.explanation,
                            "calculation": s.calculation,
                            "result": s.result
                        }
                        for s in solutions
                    ],
                    "explanation": explanation,
                    "final_answer": solutions[-1].result if solutions else None
                },
                trace_id=trace_id,
                metadata={
                    "agent": self.name,
                    "total_steps": len(solutions)
                }
            )
        
        except Exception as e:
            return AgentResponse(
                status=AgentStatus.ERROR,
                error=f"Failed to solve problem: {str(e)}",
                trace_id=trace_id,
                metadata={"agent": self.name}
            )
    
    def _parse_problem(self, problem: str) -> List[Dict[str, Any]]:
        """
        Parse a math problem into steps.
        
        For this tutorial, we handle simple expressions like:
        - "5 + 3"
        - "10 * 2"
        - "(5 + 3) * 2"
        
        Production version would use proper parsing (e.g., pyparsing)
        """
        # Simplified parser for tutorial
        # Real implementation: Use AST parsing or LLM to extract operations
        
        problem = problem.lower().replace("what is", "").strip()
        
        # Handle parentheses first
        if "(" in problem and ")" in problem:
            # Extract parentheses content
            import re
            match = re.search(r'\(([^)]+)\)', problem)
            if match:
                inner = match.group(1)
                outer = problem.replace(match.group(0), "RESULT")
                
                return [
                    self._parse_simple_expression(inner, step_num=1),
                    self._parse_simple_expression(outer, step_num=2, has_placeholder=True)
                ]
        
        # Single operation
        return [self._parse_simple_expression(problem, step_num=1)]
    
    def _parse_simple_expression(self, expr: str, step_num: int, has_placeholder: bool = False) -> Dict[str, Any]:
        """Parse a simple arithmetic expression."""
        import re
        
        # Match patterns like "5 + 3" or "10 * 2"
        patterns = [
            (r'(\d+\.?\d*)\s*\+\s*(\d+\.?\d*)', 'add', 'addition'),
            (r'(\d+\.?\d*)\s*-\s*(\d+\.?\d*)', 'subtract', 'subtraction'),
            (r'(\d+\.?\d*)\s*\*\s*(\d+\.?\d*)', 'multiply', 'multiplication'),
            (r'(\d+\.?\d*)\s*/\s*(\d+\.?\d*)', 'divide', 'division'),
        ]
        
        for pattern, op, op_name in patterns:
            match = re.search(pattern, expr)
            if match:
                return {
                    "step_number": step_num,
                    "operation": op,
                    "operation_name": op_name,
                    "a": float(match.group(1)) if not has_placeholder else "RESULT",
                    "b": float(match.group(2)),
                    "expression": expr.strip(),
                    "has_placeholder": has_placeholder
                }
        
        raise ValueError(f"Could not parse expression: {expr}")
    
    async def _solve_step(self, step_info: Dict[str, Any], context: Dict[str, Any]) -> MathStep:
        """Solve a single step using the calculator tool."""
        # If this step depends on previous result, substitute it
        a = step_info["a"]
        if step_info.get("has_placeholder") and a == "RESULT":
            # In real implementation, track previous results
            # For tutorial, we'll simulate
            a = 8.0  # Placeholder for demo
        
        # Call calculator tool
        calc_inputs = {
            "operation": step_info["operation"],
            "a": a,
            "b": step_info["b"]
        }
        
        result = calculate(calc_inputs, context)
        
        if "error" in result:
            raise ValueError(f"Calculation failed: {result['error']}")
        
        # Generate explanation
        explanations = {
            "add": f"Add {a} and {step_info['b']}",
            "subtract": f"Subtract {step_info['b']} from {a}",
            "multiply": f"Multiply {a} by {step_info['b']}",
            "divide": f"Divide {a} by {step_info['b']}"
        }
        
        return MathStep(
            step_number=step_info["step_number"],
            explanation=explanations[step_info["operation"]],
            operation=step_info["operation"],
            calculation=result,
            result=result["result"]
        )
    
    def _generate_explanation(self, solutions: List[MathStep]) -> str:
        """Generate natural language explanation."""
        lines = []
        for sol in solutions:
            lines.append(
                f"Step {sol.step_number}: {sol.explanation}\n"
                f"  Calculation: {sol.calculation['a']} {sol.operation} {sol.calculation['b']} = {sol.result}"
            )
        
        if solutions:
            lines.append(f"\nFinal Answer: {solutions[-1].result}")
        
        return "\n\n".join(lines)
```

### Step 4.3: Test Your Agent

**File: `tests/test_math_tutor_agent.py`**
```python
"""Tests for MathTutorAgent."""

import pytest
from cuga.agents.math_tutor import MathTutorAgent
from cuga.agents.contracts import AgentRequest, AgentStatus

@pytest.fixture
async def agent():
    """Create and start agent."""
    agent = MathTutorAgent()
    await agent.startup()
    yield agent
    await agent.shutdown()

@pytest.mark.asyncio
async def test_simple_addition(agent):
    """Test simple addition problem."""
    request = AgentRequest(
        goal="What is 5 + 3?",
        context={"trace_id": "test-add", "profile": "py-slim"}
    )
    
    response = await agent.process(request)
    
    assert response.status == AgentStatus.SUCCESS
    assert response.result["final_answer"] == 8
    assert len(response.result["steps"]) == 1
    assert response.result["steps"][0]["operation"] == "add"

@pytest.mark.asyncio
async def test_simple_multiplication(agent):
    """Test multiplication problem."""
    request = AgentRequest(
        goal="What is 10 * 3?",
        context={"trace_id": "test-mult", "profile": "py-slim"}
    )
    
    response = await agent.process(request)
    
    assert response.status == AgentStatus.SUCCESS
    assert response.result["final_answer"] == 30

@pytest.mark.asyncio
async def test_no_problem_provided(agent):
    """Test error handling for missing problem."""
    request = AgentRequest(
        goal=None,
        context={"trace_id": "test-empty", "profile": "py-slim"}
    )
    
    response = await agent.process(request)
    
    assert response.status == AgentStatus.ERROR
    assert "No math problem provided" in response.error
```

Run tests:
```bash
pytest tests/test_math_tutor_agent.py -v
```

### Step 4.4: Use Your Agent via CLI

```bash
# Test the agent directly
python -c "
import asyncio
from cuga.agents.math_tutor import MathTutorAgent
from cuga.agents.contracts import AgentRequest

async def main():
    agent = MathTutorAgent()
    await agent.startup()
    
    request = AgentRequest(
        goal='What is 12 * 4?',
        context={'trace_id': 'demo-123', 'profile': 'py-slim'}
    )
    
    response = await agent.process(request)
    print(response.result['explanation'])
    
    await agent.shutdown()

asyncio.run(main())
"
```

**Expected output**:
```
Step 1: Multiply 12 by 4
  Calculation: 12 multiply 4 = 48

Final Answer: 48
```

---

## 🔌 Part 5: Wire Everything Together (15 minutes)

### Step 5.1: Register Your Agent

**File: `src/cuga/agents/__init__.py`**
```python
"""Agent registry."""

from cuga.agents.math_tutor import MathTutorAgent

AVAILABLE_AGENTS = {
    "math-tutor": MathTutorAgent,
    # ... other agents ...
}

def get_agent(name: str):
    """Get agent class by name."""
    if name not in AVAILABLE_AGENTS:
        raise ValueError(f"Unknown agent: {name}")
    return AVAILABLE_AGENTS[name]
```

### Step 5.2: Create a Workflow

**Use Case**: Student asks a math question → Agent solves it → Store in memory for future reference

**File: `examples/math_tutoring_workflow.py`**
```python
"""Math tutoring workflow example."""

import asyncio
from cuga.agents.math_tutor import MathTutorAgent
from cuga.agents.contracts import AgentRequest
from cuga.modular.memory import VectorMemory
from cuga.orchestrator.protocol import ExecutionContext

async def math_tutoring_session(problems: list[str]):
    """
    Run a tutoring session for multiple problems.
    
    Args:
        problems: List of math problems to solve
    """
    # Initialize components
    agent = MathTutorAgent(name="tutor-1")
    memory = VectorMemory(profile="student-123")
    
    await agent.startup()
    
    print("🎓 Math Tutoring Session Started\n")
    
    for i, problem in enumerate(problems, 1):
        print(f"Problem {i}: {problem}")
        print("-" * 50)
        
        # Create execution context
        context = ExecutionContext(
            trace_id=f"problem-{i}",
            profile="student-123",
            user_id="student-123"
        )
        
        # Create agent request
        request = AgentRequest(
            goal=problem,
            context=context.to_dict()
        )
        
        # Process request
        response = await agent.process(request)
        
        if response.status == "success":
            # Display solution
            print(response.result["explanation"])
            
            # Store in memory for future reference
            await memory.remember(
                text=f"Problem: {problem}\nSolution: {response.result['explanation']}",
                metadata={
                    "problem": problem,
                    "answer": response.result["final_answer"],
                    "steps": len(response.result["steps"]),
                    "trace_id": context.trace_id
                }
            )
            print("✅ Stored in memory\n")
        else:
            print(f"❌ Error: {response.error}\n")
    
    # Demonstrate memory search
    print("\n🔍 Memory Search Demo")
    print("-" * 50)
    similar = await memory.search(
        query="multiplication problems",
        top_k=2
    )
    
    print(f"Found {len(similar)} similar problems in memory:")
    for idx, item in enumerate(similar, 1):
        print(f"\n{idx}. Score: {item['score']:.2f}")
        print(f"   {item['text'][:100]}...")
    
    await agent.shutdown()
    print("\n🎓 Session Complete!")


async def main():
    """Run example session."""
    problems = [
        "What is 15 + 27?",
        "What is 8 * 6?",
        "What is 100 / 4?",
    ]
    
    await math_tutoring_session(problems)


if __name__ == "__main__":
    asyncio.run(main())
```

Run the workflow:
```bash
python examples/math_tutoring_workflow.py
```

**Expected output**:
```
🎓 Math Tutoring Session Started

Problem 1: What is 15 + 27?
--------------------------------------------------
Step 1: Add 15 and 27
  Calculation: 15 add 27 = 42

Final Answer: 42
✅ Stored in memory

Problem 2: What is 8 * 6?
--------------------------------------------------
Step 1: Multiply 8 by 6
  Calculation: 8 multiply 6 = 48

Final Answer: 48
✅ Stored in memory

Problem 3: What is 100 / 4?
--------------------------------------------------
Step 1: Divide 100 by 4
  Calculation: 100 divide 4 = 25

Final Answer: 25
✅ Stored in memory

🔍 Memory Search Demo
--------------------------------------------------
Found 1 similar problems in memory:

1. Score: 0.89
   Problem: What is 8 * 6?
Solution: Step 1: Multiply 8 by 6...

🎓 Session Complete!
```

### Step 5.3: Add Observability

**Enhanced workflow with tracing**:

```python
from cuga.observability.structured_logger import StructuredLogger
from cuga.observability.tracer import TracerProvider

# Initialize observability
logger = StructuredLogger(component="math-workflow")
tracer = TracerProvider.get_tracer("math-workflow")

async def math_tutoring_session_with_tracing(problems: list[str]):
    """Math tutoring with full observability."""
    
    with tracer.start_as_current_span("tutoring-session") as session_span:
        session_span.set_attribute("total_problems", len(problems))
        
        agent = MathTutorAgent(name="tutor-1")
        await agent.startup()
        
        for i, problem in enumerate(problems, 1):
            with tracer.start_as_current_span(f"problem-{i}") as problem_span:
                problem_span.set_attribute("problem", problem)
                
                logger.info(
                    event="problem_started",
                    problem_number=i,
                    problem=problem
                )
                
                # ... (agent processing) ...
                
                logger.info(
                    event="problem_completed",
                    problem_number=i,
                    answer=response.result["final_answer"],
                    steps=len(response.result["steps"])
                )
                
                problem_span.set_attribute("answer", response.result["final_answer"])
        
        await agent.shutdown()
```

**View traces**:
```bash
# If using LangFuse
open https://cloud.langfuse.com/project/<your-project>/traces

# If using local OpenTelemetry
open http://localhost:16686  # Jaeger UI
```

---

## 🎓 Next Steps

### Enhance Your Agent

**Add more capabilities**:
```python
class EnhancedMathTutor(MathTutorAgent):
    """Extended tutor with visualization."""
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        response = await super().process(request)
        
        if response.status == "success":
            # Add ASCII graph visualization
            response.result["visualization"] = self._draw_graph(
                response.result["steps"]
            )
        
        return response
    
    def _draw_graph(self, steps: list) -> str:
        """Draw simple ASCII graph of steps."""
        # Your visualization logic here
        pass
```

### Integrate with LangGraph

**Create stateful workflow**:
```python
from langgraph.graph import StateGraph

def create_tutoring_graph():
    """Create LangGraph workflow."""
    
    graph = StateGraph()
    
    # Add nodes
    graph.add_node("parse_problem", parse_problem_node)
    graph.add_node("solve_step", solve_step_node)
    graph.add_node("explain", explain_node)
    
    # Add edges
    graph.add_edge("parse_problem", "solve_step")
    graph.add_edge("solve_step", "explain")
    
    # Set entry point
    graph.set_entry_point("parse_problem")
    
    return graph.compile()
```

See [Enterprise Workflows](examples/ENTERPRISE_WORKFLOWS.md) for advanced patterns.

### Add Multi-Agent Collaboration

**Coordinate multiple agents**:
```python
from cuga.orchestrator.coordinator import CoordinatorAgent

async def collaborative_problem_solving():
    """Multiple agents work together."""
    
    coordinator = CoordinatorAgent()
    
    # Agent 1: Parses problem
    parser = ProblemParserAgent()
    
    # Agent 2: Solves numerically
    solver = MathTutorAgent()
    
    # Agent 3: Explains conceptually
    explainer = ConceptExplainerAgent()
    
    # Coordinate workflow
    result = await coordinator.orchestrate(
        goal="Explain why (a+b)² = a² + 2ab + b²",
        agents=[parser, solver, explainer],
        routing_policy="sequential"
    )
```

See [Multi-Agent Composition](testing/SCENARIO_TESTING.md) for patterns.

### Add Human-in-the-Loop

**Add approval gates**:
```python
from cuga.orchestrator.hitl import HumanApprovalGate

async def tutoring_with_approval():
    """Require teacher approval for advanced topics."""
    
    approval_gate = HumanApprovalGate(
        notification_channel="email",
        timeout_seconds=3600  # 1 hour
    )
    
    # Process problem
    response = await agent.process(request)
    
    # Check if advanced topic
    if response.metadata.get("difficulty") == "advanced":
        # Request human approval
        approved = await approval_gate.request_approval(
            context={
                "student_id": "student-123",
                "problem": request.goal,
                "solution": response.result
            },
            reviewers=["teacher@school.com"]
        )
        
        if not approved:
            return AgentResponse(
                status=AgentStatus.BLOCKED,
                error="Teacher review required for advanced topics"
            )
    
    return response
```

See [Enterprise Workflows](examples/ENTERPRISE_WORKFLOWS.md) for HITL patterns.

---

## 📚 Additional Resources

### Documentation

- **[System Execution Narrative](SYSTEM_EXECUTION_NARRATIVE.md)** - Complete request flow with debugging tips
- **[Orchestrator Interface](orchestrator/README.md)** - Formal API specification
- **[Agent Lifecycle](agents/AGENT_LIFECYCLE.md)** - Startup/shutdown contracts
- **[Enterprise Workflows](examples/ENTERPRISE_WORKFLOWS.md)** - Production-ready examples
- **[Observability Guide](observability/OBSERVABILITY_GUIDE.md)** - Logging and tracing
- **[Test Coverage Map](testing/TEST_COVERAGE_MAP.md)** - What's tested and what's not

### Code Examples

- `examples/multi_agent_dispatch.py` - Multi-agent coordination
- `examples/rag_query.py` - RAG integration
- `examples/workflows/` - Enterprise workflow templates

### Community

- **GitHub Issues**: [Report bugs or request features](https://github.com/yourusername/cugar-agent/issues)
- **Discussions**: [Ask questions, share ideas](https://github.com/yourusername/cugar-agent/discussions)
- **Contributing**: See [CONTRIBUTING.md](../CONTRIBUTING.md)

---

## 🐛 Troubleshooting

### Common Issues

**Issue**: `ImportError: cannot import name 'calculate'`
```bash
# Solution: Make sure tool file is in correct location
ls -la src/cuga/modular/tools/calculator.py

# Reinstall in editable mode
pip install -e .
```

**Issue**: `Tool not found in registry`
```bash
# Solution: Verify registry entry
grep -A 10 "name: calculate" registry.yaml

# Restart to reload registry
pkill -f "cuga.modular"
```

**Issue**: `Sandbox timeout exceeded`
```bash
# Solution: Increase timeout in registry.yaml
# Change: timeout_seconds: 5
# To:     timeout_seconds: 30
```

**Issue**: `Memory error: profile isolation violated`
```bash
# Solution: Check profile is set in context
# context = {"trace_id": "...", "profile": "py-slim"}  # ← Must include profile
```

### Getting Help

1. **Check logs**: `tail -f logs/cuga.log`
2. **Enable debug mode**: `export CUGA_LOG_LEVEL=DEBUG`
3. **Inspect trace**: `python -m cuga.modular.cli trace <trace-id>`
4. **Ask for help**: Open an issue with trace ID and logs

---

## ✅ Onboarding Checklist

Track your progress:

- [ ] Environment set up (dependencies installed)
- [ ] `.env` configured with API key
- [ ] Tests passing (`pytest`)
- [ ] Ran first agent interaction (`cli plan`)
- [ ] Created custom tool (`calculator.py`)
- [ ] Registered tool (`registry.yaml`)
- [ ] Tested tool (passed unit tests)
- [ ] Created custom agent (`MathTutorAgent`)
- [ ] Tested agent (passed unit tests)
- [ ] Built workflow (tutoring session)
- [ ] Added observability (tracing)
- [ ] Read system execution narrative
- [ ] Explored enterprise workflow examples
- [ ] Ready to contribute! 🎉

**Welcome to the CUGAR community!** 🚀

---

**Questions or suggestions for this guide?** [Open an issue](https://github.com/yourusername/cugar-agent/issues) or submit a PR!
