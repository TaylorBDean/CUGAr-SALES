"""
Domain 1: Territory & Capacity Planning Capabilities

WHY: Territory design and capacity planning are core sales operations
that MUST be deterministic, auditable, and explainable.

SAFETY: All operations are READ-ONLY or "propose-only" by default.
No territory changes are auto-applied. All proposals require human approval.

OFFLINE-FIRST: Simulations run entirely locally with no external dependencies.
"""

from __future__ import annotations

from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


# Tool handler signature: (inputs: Dict[str, Any], context: Dict[str, Any]) -> Any
# Context includes: profile, trace_id, budget


def simulate_territory_change(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulate territory reassignment impact (READ-ONLY).
    
    WHY: Territory changes have cascading impacts on capacity, coverage,
    and rep performance. Simulation allows "what-if" analysis before committing.
    
    CAPABILITY: Predicts impact of moving accounts between territories.
    VENDOR-NEUTRAL: Works with ANY territory structure.
    OFFLINE: Pure computation, no external calls.
    
    Args:
        inputs: {
            "from_territory": str,
            "to_territory": str,
            "account_ids": List[str],
            "effective_date": str (ISO 8601),
        }
        context: {
            "profile": str,  # Profile isolation
            "trace_id": str,  # Observability
            "budget": dict,  # Budget enforcement
        }
        
    Returns: {
        "simulation_id": str,
        "impact_summary": {
            "from_territory": {
                "current_accounts": int,
                "projected_accounts": int,
                "capacity_utilization": float,  # 0.0 to 1.0
            },
            "to_territory": {
                "current_accounts": int,
                "projected_accounts": int,
                "capacity_utilization": float,
            },
        },
        "recommendations": List[str],
        "requires_approval": bool,  # Always True
        "approval_reason": str,
    }
    
    Raises:
        ValueError: If required fields missing or invalid
    """
    trace_id = context.get("trace_id", "unknown")
    profile = context.get("profile", "default")
    
    # Validate required inputs
    required_fields = ["from_territory", "to_territory", "account_ids"]
    for field in required_fields:
        if field not in inputs:
            raise ValueError(f"Required field missing: {field}")
    
    from_territory = inputs["from_territory"]
    to_territory = inputs["to_territory"]
    account_ids = inputs["account_ids"]
    
    if not isinstance(account_ids, list) or len(account_ids) == 0:
        raise ValueError("account_ids must be a non-empty list")
    
    # Simulate impact (deterministic logic, no external calls)
    # NOTE: In production, this would query territory state from memory/storage
    # For MVP, we use simplified simulation logic
    
    num_accounts_moving = len(account_ids)
    
    # Simplified capacity model (would be enriched in production)
    from_territory_current = 100  # Mock current account count
    to_territory_current = 80
    
    from_territory_projected = from_territory_current - num_accounts_moving
    to_territory_projected = to_territory_current + num_accounts_moving
    
    # Capacity utilization (simplified: 1 rep can handle ~100 accounts)
    from_capacity = from_territory_projected / 100.0
    to_capacity = to_territory_projected / 100.0
    
    # Generate recommendations
    recommendations = []
    if to_capacity > 0.9:
        recommendations.append(
            f"WARNING: {to_territory} will exceed 90% capacity. Consider rep hiring or territory split."
        )
    if from_capacity < 0.5:
        recommendations.append(
            f"INFO: {from_territory} will drop below 50% capacity. Opportunity for consolidation."
        )
    
    result = {
        "simulation_id": f"sim_{trace_id}",
        "impact_summary": {
            "from_territory": {
                "current_accounts": from_territory_current,
                "projected_accounts": from_territory_projected,
                "capacity_utilization": from_capacity,
            },
            "to_territory": {
                "current_accounts": to_territory_current,
                "projected_accounts": to_territory_projected,
                "capacity_utilization": to_capacity,
            },
        },
        "recommendations": recommendations,
        "requires_approval": True,  # ALWAYS True per god-tier principles
        "approval_reason": "Territory changes impact rep assignments and quota distribution",
    }
    
    logger.info(
        f"[{trace_id}] Simulated territory change: "
        f"{num_accounts_moving} accounts from {from_territory} to {to_territory}"
    )
    
    return result


def assess_capacity_coverage(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assess territory capacity and coverage gaps (READ-ONLY).
    
    WHY: Capacity planning ensures reps aren't over/under-loaded and
    identifies white space or coverage gaps.
    
    CAPABILITY: Analyzes current territory state and identifies imbalances.
    VENDOR-NEUTRAL: Works with ANY territory structure.
    OFFLINE: Pure computation based on territory state snapshot.
    
    Args:
        inputs: {
            "territories": List[{
                "territory_id": str,
                "rep_count": int,
                "account_count": int,
                "region": str (optional),
            }],
            "capacity_threshold": float (optional, default: 0.9),
        }
        context: {
            "profile": str,
            "trace_id": str,
        }
        
    Returns: {
        "analysis_id": str,
        "overall_capacity": float,  # Across all territories
        "coverage_gaps": List[{
            "territory_id": str,
            "gap_type": str,  # "overloaded" | "underutilized" | "no_rep"
            "severity": str,  # "low" | "medium" | "high"
            "recommendation": str,
        }],
        "summary": str,
    }
    """
    trace_id = context.get("trace_id", "unknown")
    
    # Validate inputs
    if "territories" not in inputs:
        raise ValueError("Required field missing: territories")
    
    territories = inputs["territories"]
    capacity_threshold = inputs.get("capacity_threshold", 0.9)
    
    if not isinstance(territories, list):
        raise ValueError("territories must be a list")
    
    # Analyze capacity across territories
    coverage_gaps = []
    total_reps = 0
    total_accounts = 0
    
    for territory in territories:
        territory_id = territory.get("territory_id", "unknown")
        rep_count = territory.get("rep_count", 0)
        account_count = territory.get("account_count", 0)
        
        total_reps += rep_count
        total_accounts += account_count
        
        # Capacity analysis (simplified: 1 rep ~= 100 accounts)
        if rep_count == 0:
            coverage_gaps.append({
                "territory_id": territory_id,
                "gap_type": "no_rep",
                "severity": "high",
                "recommendation": f"Assign rep to {territory_id} immediately (orphaned territory)",
            })
        else:
            utilization = account_count / (rep_count * 100.0)
            
            if utilization > capacity_threshold:
                coverage_gaps.append({
                    "territory_id": territory_id,
                    "gap_type": "overloaded",
                    "severity": "high" if utilization > 1.2 else "medium",
                    "recommendation": f"Territory {territory_id} at {utilization:.1%} capacity. Consider hiring or splitting.",
                })
            elif utilization < 0.5:
                coverage_gaps.append({
                    "territory_id": territory_id,
                    "gap_type": "underutilized",
                    "severity": "low",
                    "recommendation": f"Territory {territory_id} at {utilization:.1%} capacity. Opportunity for consolidation.",
                })
    
    # Calculate overall capacity
    overall_capacity = total_accounts / (total_reps * 100.0) if total_reps > 0 else 0.0
    
    summary = (
        f"Analyzed {len(territories)} territories with {total_reps} reps covering {total_accounts} accounts. "
        f"Overall capacity: {overall_capacity:.1%}. Found {len(coverage_gaps)} coverage gaps."
    )
    
    logger.info(f"[{trace_id}] Capacity assessment: {summary}")
    
    return {
        "analysis_id": f"cap_{trace_id}",
        "overall_capacity": overall_capacity,
        "coverage_gaps": coverage_gaps,
        "summary": summary,
    }


SCHEMA_simulate_territory_change = {
    "name": "simulate_territory_change",
    "description": "Simulate territory reassignment impact (READ-ONLY, requires approval)",
    "inputs": {
        "from_territory": {"type": "string", "required": True},
        "to_territory": {"type": "string", "required": True},
        "account_ids": {"type": "array", "items": {"type": "string"}, "required": True},
        "effective_date": {"type": "string", "required": False},
    },
    "outputs": {
        "simulation_id": {"type": "string"},
        "impact_summary": {"type": "object"},
        "recommendations": {"type": "array"},
        "requires_approval": {"type": "boolean"},
    },
}

SCHEMA_assess_capacity_coverage = {
    "name": "assess_capacity_coverage",
    "description": "Assess territory capacity and coverage gaps (READ-ONLY)",
    "inputs": {
        "territories": {
            "type": "array",
            "items": {"type": "object"},
            "required": True,
        },
        "capacity_threshold": {"type": "number", "required": False},
    },
    "outputs": {
        "analysis_id": {"type": "string"},
        "overall_capacity": {"type": "number"},
        "coverage_gaps": {"type": "array"},
        "summary": {"type": "string"},
    },
}
