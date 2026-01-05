"""
Local interactive CLI commands for simplified single-process usage.
"""

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
import subprocess
import sys
from pathlib import Path

app = typer.Typer(help="Local development commands for simplified single-process mode")
console = Console()


@app.command()
def ui():
    """
    Launch the local Streamlit UI (single-process mode).
    
    This starts a simple web UI that combines the agent orchestration
    and user interface in one process - no separate backend needed.
    """
    console.print(Panel.fit(
        "[bold green]Starting CUGAr-SALES Local UI[/bold green]\n\n"
        "✅ Single process (no separate backend)\n"
        "✅ Built-in Streamlit interface\n"
        "✅ Perfect for local development/demos\n\n"
        "Press Ctrl+C to stop",
        title="🎯 CUGAr Local Mode"
    ))
    
    # Check if streamlit is installed
    try:
        import streamlit
    except ImportError:
        console.print("\n[yellow]Streamlit not installed. Installing...[/yellow]")
        subprocess.run([sys.executable, "-m", "pip", "install", "streamlit"], check=True)
    
    # Launch Streamlit
    local_ui_path = Path(__file__).parent / "local_ui.py"
    subprocess.run(["streamlit", "run", str(local_ui_path)])


@app.command()
def chat():
    """
    Interactive CLI chat mode (no UI, pure terminal).
    
    Chat directly with the agent in your terminal without
    any web interface or separate processes.
    """
    from cuga.modular.agents import (
        CoordinatorAgent, PlannerAgent, WorkerAgent, build_default_registry
    )
    from cuga.modular.config import AgentConfig
    from cuga.modular.memory import VectorMemory
    import uuid
    
    console.print(Panel.fit(
        "[bold cyan]CUGAr-SALES Interactive Chat[/bold cyan]\n\n"
        "Type your questions and press Enter.\n"
        "Commands: /help, /clear, /exit",
        title="💬 Chat Mode"
    ))
    
    # Initialize agent
    console.print("[dim]Initializing agent...[/dim]")
    memory = VectorMemory(backend_name="local", profile="default")
    registry = build_default_registry()
    planner = PlannerAgent(registry=registry, memory=memory, config=AgentConfig())
    worker = WorkerAgent(registry=registry, memory=memory)
    coordinator = CoordinatorAgent(planner=planner, workers=[worker], memory=memory)
    
    console.print("[green]✓[/green] Agent initialized\n")
    
    # Chat loop
    while True:
        try:
            prompt = Prompt.ask("[bold blue]You[/bold blue]")
            
            if prompt.startswith("/"):
                if prompt == "/exit":
                    console.print("[yellow]Goodbye![/yellow]")
                    break
                elif prompt == "/clear":
                    console.clear()
                    continue
                elif prompt == "/help":
                    console.print("\n[bold]Available Commands:[/bold]")
                    console.print("  /help  - Show this help")
                    console.print("  /clear - Clear screen")
                    console.print("  /exit  - Exit chat\n")
                    continue
            
            # Execute
            console.print("[dim]Thinking...[/dim]")
            trace_id = str(uuid.uuid4())
            result = coordinator.dispatch(prompt, trace_id=trace_id)
            
            console.print(f"\n[bold green]Assistant[/bold green]: {result.output}\n")
            console.print(f"[dim]trace_id: {trace_id}[/dim]\n")
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Use /exit to quit[/yellow]")
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]\n")


@app.command()
def demo():
    """
    Run a quick demo to verify everything works.
    
    Tests the agent with a simple query and shows the results.
    """
    from cuga.modular.agents import (
        CoordinatorAgent, PlannerAgent, WorkerAgent, build_default_registry
    )
    from cuga.modular.config import AgentConfig
    from cuga.modular.memory import VectorMemory
    import uuid
    
    console.print(Panel.fit(
        "[bold magenta]Running CUGAr-SALES Demo[/bold magenta]\n\n"
        "Testing agent orchestration with a sample query...",
        title="🧪 Demo Mode"
    ))
    
    # Initialize
    console.print("\n[cyan]1. Initializing agent...[/cyan]")
    memory = VectorMemory(backend_name="local", profile="default")
    registry = build_default_registry()
    planner = PlannerAgent(registry=registry, memory=memory, config=AgentConfig())
    worker = WorkerAgent(registry=registry, memory=memory)
    coordinator = CoordinatorAgent(planner=planner, workers=[worker], memory=memory)
    console.print("[green]✓[/green] Agent ready")
    
    # Test query
    console.print("\n[cyan]2. Executing test query...[/cyan]")
    test_query = "What sales tools are available?"
    console.print(f"[dim]Query: {test_query}[/dim]")
    
    trace_id = str(uuid.uuid4())
    result = coordinator.dispatch(test_query, trace_id=trace_id)
    
    # Display results
    console.print("\n[cyan]3. Results:[/cyan]")
    console.print(Panel(result.output, title="Agent Response"))
    
    console.print(f"\n[dim]Trace ID: {trace_id}[/dim]")
    console.print(f"[dim]Steps executed: {len(result.trace.get('steps', []))}[/dim]")
    
    console.print("\n[green]✓[/green] Demo complete!\n")
    console.print("[bold]Next steps:[/bold]")
    console.print("  • cuga local ui    - Launch web interface")
    console.print("  • cuga local chat  - Interactive terminal chat")
    console.print("  • ./scripts/start-local.sh - Quick launch script")


@app.command()
def compare():
    """
    Show comparison between local mode vs production mode.
    
    Helps you decide which deployment mode to use.
    """
    table = Table(title="🎯 CUGAr-SALES Deployment Modes")
    
    table.add_column("Feature", style="cyan", no_wrap=True)
    table.add_column("Local Mode", style="green")
    table.add_column("Production Mode", style="blue")
    
    table.add_row(
        "Processes",
        "✅ Single process",
        "⚙️ Backend + Frontend"
    )
    table.add_row(
        "Startup",
        "✅ One command",
        "⚙️ Multi-step (start-dev.sh)"
    )
    table.add_row(
        "Ports",
        "✅ One (8501)",
        "⚙️ 8000 + 3000"
    )
    table.add_row(
        "UI",
        "📊 Streamlit (simple)",
        "🎨 React (full-featured)"
    )
    table.add_row(
        "WebSocket",
        "❌ Not needed",
        "✅ Real-time streaming"
    )
    table.add_row(
        "Use Case",
        "🏠 Local dev, demos, testing",
        "🏢 Production, teams, scale"
    )
    table.add_row(
        "Complexity",
        "✅ Simple",
        "⚙️ Full stack"
    )
    table.add_row(
        "CORS",
        "✅ Not needed",
        "⚙️ Must configure"
    )
    
    console.print(table)
    
    console.print("\n[bold]Recommendations:[/bold]")
    console.print("  • [green]Local Mode[/green]: Solo development, quick demos, learning")
    console.print("  • [blue]Production Mode[/blue]: Team collaboration, enterprise deployment")
    
    console.print("\n[bold]Commands:[/bold]")
    console.print("  [green]cuga local ui[/green]        - Start local mode")
    console.print("  [green]./scripts/start-local.sh[/green]  - Quick launch script")
    console.print("  [blue]./scripts/start-dev.sh[/blue] - Start production mode")


if __name__ == "__main__":
    app()
