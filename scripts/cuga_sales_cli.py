#!/usr/bin/env python3
"""
Sales CLI - User-friendly commands for sales operations.

Usage:
    cuga-sales assess-capacity --territory <id>
    cuga-sales score-account --account-id <id>
    cuga-sales qualify --opportunity <id>
"""

import sys
import json
import click
from pathlib import Path
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cuga.sales_registry import create_sales_registry


@click.group()
def cli():
    """CUGAr Sales Agent CLI"""
    pass


@cli.command()
@click.option("--territories", required=True, help="JSON array of territories with rep_count and account_count")
@click.option("--threshold", default=0.85, help="Capacity threshold (0.0-1.0)")
@click.option("--trace-id", default="cli-001", help="Trace ID for observability")
def assess_capacity(territories, threshold, trace_id):
    """
    Assess territory capacity and coverage gaps.
    
    Example:
        cuga-sales assess-capacity --territories '[{"territory_id": "west-1", "rep_count": 5, "account_count": 450}]'
    """
    try:
        # Parse territories JSON
        territories_data = json.loads(territories)
        
        # Load registry and call tool
        registry = create_sales_registry()
        
        result = registry.call_tool(
            "sales.assess_capacity_coverage",
            inputs={
                "territories": territories_data,
                "capacity_threshold": threshold,
            },
            context={"trace_id": trace_id, "profile": "sales"}
        )
        
        # Pretty print results
        click.echo(click.style("\n✓ Capacity Assessment Complete", fg="green", bold=True))
        click.echo(f"\nAnalysis ID: {result['analysis_id']}")
        click.echo(f"Overall Capacity: {result['overall_capacity']:.1%}")
        
        if result['coverage_gaps']:
            click.echo(click.style(f"\n⚠ Coverage Gaps Found: {len(result['coverage_gaps'])}", fg="yellow"))
            for gap in result['coverage_gaps']:
                click.echo(f"\n  Territory: {gap['territory_id']}")
                click.echo(f"  Gap Type: {gap['gap_type']}")
                click.echo(f"  Severity: {gap['severity']}")
                click.echo(f"  Recommendation: {gap['recommendation']}")
        else:
            click.echo(click.style("\n✓ No coverage gaps detected", fg="green"))
        
    except json.JSONDecodeError as e:
        click.echo(click.style(f"✗ Invalid JSON: {e}", fg="red"), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg="red"), err=True)
        sys.exit(1)


@cli.command()
@click.option("--account", required=True, help="JSON object with account data (revenue, industry, etc.)")
@click.option("--icp", required=True, help="JSON object with ICP criteria (min_revenue, target_industries, etc.)")
@click.option("--trace-id", default="cli-002", help="Trace ID for observability")
def score_account(account, icp, trace_id):
    """
    Score account fit against Ideal Customer Profile.
    
    Example:
        cuga-sales score-account \\
            --account '{"account_id": "acme", "revenue": 50000000, "industry": "technology"}' \\
            --icp '{"min_revenue": 10000000, "target_industries": ["technology"]}'
    """
    try:
        # Parse JSON inputs
        account_data = json.loads(account)
        icp_data = json.loads(icp)
        
        # Load registry and call tool
        registry = create_sales_registry()
        
        result = registry.call_tool(
            "sales.score_account_fit",
            inputs={
                "account": account_data,
                "icp_criteria": icp_data,
            },
            context={"trace_id": trace_id, "profile": "sales"}
        )
        
        # Pretty print results
        click.echo(click.style("\n✓ Account Scoring Complete", fg="green", bold=True))
        click.echo(f"\nAccount: {result['account_id']}")
        click.echo(f"Fit Score: {result['fit_score']:.1%}")
        click.echo(f"Recommendation: {result['recommendation']}")
        
        # Show fit breakdown
        if "fit_breakdown" in result:
            click.echo(click.style("\nFit Breakdown:", bold=True))
            for dimension, score in result['fit_breakdown'].items():
                bar = "█" * int(score * 20)
                click.echo(f"  {dimension:20} {bar} {score:.1%}")
        
        # Show reasoning
        if "reasoning" in result:
            click.echo(click.style("\nReasoning:", bold=True))
            for reason in result['reasoning']:
                click.echo(f"  • {reason}")
        
    except json.JSONDecodeError as e:
        click.echo(click.style(f"✗ Invalid JSON: {e}", fg="red"), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg="red"), err=True)
        sys.exit(1)


@cli.command()
@click.option("--opportunity", required=True, help="Opportunity ID")
@click.option("--budget", is_flag=True, help="Budget confirmed")
@click.option("--authority", is_flag=True, help="Authority identified")
@click.option("--need", is_flag=True, help="Need validated")
@click.option("--timing", is_flag=True, help="Timing confirmed")
@click.option("--trace-id", default="cli-003", help="Trace ID for observability")
def qualify(opportunity, budget, authority, need, timing, trace_id):
    """
    Qualify opportunity using BANT framework.
    
    Example:
        cuga-sales qualify --opportunity opp-123 --budget --authority --need
    """
    try:
        # Load registry and call tool
        registry = create_sales_registry()
        
        result = registry.call_tool(
            "sales.qualify_opportunity",
            inputs={
                "opportunity_id": opportunity,
                "criteria": {
                    "budget": budget,
                    "authority": authority,
                    "need": need,
                    "timing": timing,
                },
            },
            context={"trace_id": trace_id, "profile": "sales"}
        )
        
        # Pretty print results
        click.echo(click.style("\n✓ Qualification Complete", fg="green", bold=True))
        click.echo(f"\nOpportunity: {result['opportunity_id']}")
        click.echo(f"Qualification Score: {result['qualification_score']:.1%}")
        
        if result['qualified']:
            click.echo(click.style("Status: QUALIFIED ✓", fg="green", bold=True))
        else:
            click.echo(click.style("Status: NOT QUALIFIED ✗", fg="red", bold=True))
        
        click.echo(f"Framework: {result['framework']}")
        
        # Show strengths
        if result.get('strengths'):
            click.echo(click.style("\nStrengths:", fg="green"))
            for strength in result['strengths']:
                click.echo(f"  ✓ {strength}")
        
        # Show gaps
        if result.get('gaps'):
            click.echo(click.style("\nGaps:", fg="yellow"))
            for gap in result['gaps']:
                click.echo(f"  ⚠ {gap}")
        
        # Show recommendations
        if result.get('recommendations'):
            click.echo(click.style("\nRecommendations:", bold=True))
            for rec in result['recommendations']:
                click.echo(f"  • {rec}")
        
    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg="red"), err=True)
        sys.exit(1)


@cli.command()
def list_tools():
    """List all available sales tools."""
    try:
        registry = create_sales_registry()
        
        click.echo(click.style("\nAvailable Sales Tools:", bold=True))
        click.echo("=" * 60)
        
        for tool_id in registry.list_tools():
            metadata = registry.get_metadata(tool_id)
            
            click.echo(f"\n{click.style(tool_id, fg='cyan', bold=True)}")
            click.echo(f"  Name: {metadata['name']}")
            click.echo(f"  Description: {metadata['description']}")
            click.echo(f"  Requires Approval: {metadata.get('requires_approval', False)}")
            click.echo(f"  Cost: {metadata.get('cost', 'N/A')}")
        
        click.echo()
        
    except Exception as e:
        click.echo(click.style(f"✗ Error: {e}", fg="red"), err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
