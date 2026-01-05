"""
Domain 2: Account & Prospect Intelligence Capabilities

WHY: Account intelligence is foundational to sales effectiveness.
Reps need consistent, enriched account data regardless of where it lives.

SAFETY: Data normalization and scoring are READ-ONLY operations.
No CRM writes without explicit approval.

OFFLINE-FIRST: Scoring and normalization work on local data.
External enrichment is opt-in via adapters (Phase 4).
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
import logging
import re
import os

from .schemas import AccountRecord, AccountStatus

logger = logging.getLogger(__name__)

# Lazy-loaded CRM adapter (optional dependency)
_crm_adapter = None


def _get_crm_adapter():
    """
    Lazy-load CRM adapter if configured.
    
    Uses adapter factory to auto-detect configured CRM vendor.
    Tries: HubSpot, Salesforce, Pipedrive (in priority order).
    
    Returns None if no adapter configured (offline mode).
    This allows capabilities to work without adapters.
    """
    global _crm_adapter
    
    if _crm_adapter is None:
        try:
            from cuga.adapters.crm.factory import get_configured_adapter
            _crm_adapter = get_configured_adapter()
            
            if _crm_adapter:
                logger.info(f"Loaded CRM adapter: {_crm_adapter.__class__.__name__}")
            else:
                logger.info("No CRM adapter configured. Operating in offline mode.")
        except Exception as e:
            logger.warning(f"Failed to load CRM adapter: {e}. Operating in offline mode.")
    
    return _crm_adapter


def normalize_account_record(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize account data from ANY source into canonical schema.
    
    WHY: CRM data is messy. Field names vary, formatting is inconsistent,
    required fields are often missing. Normalization creates a single,
    clean representation for downstream capabilities.
    
    CAPABILITY: Data cleaning and schema standardization.
    VENDOR-NEUTRAL: Accepts ANY account dict, outputs canonical AccountRecord.
    OFFLINE: Pure transformation, no external calls.
    
    Args:
        inputs: {
            "account_data": Dict[str, Any],  # Raw account data from any source
            "source_type": str (optional),  # "salesforce" | "hubspot" | "csv" | etc.
        }
        context: {
            "profile": str,
            "trace_id": str,
        }
        
    Returns: {
        "normalized_account": Dict[str, Any],  # Canonical AccountRecord
        "applied_transformations": List[str],  # What was fixed/cleaned
        "confidence": float,  # 0.0 to 1.0 (data completeness)
    }
    """
    trace_id = context.get("trace_id", "unknown")
    
    if "account_data" not in inputs:
        raise ValueError("Required field missing: account_data")
    
    raw_account = inputs["account_data"]
    source_type = inputs.get("source_type", "unknown")
    
    applied_transformations = []
    
    # Extract account_id (try common field names)
    account_id = (
        raw_account.get("account_id") or
        raw_account.get("id") or
        raw_account.get("accountId") or
        raw_account.get("Id") or
        f"acct_{hash(str(raw_account))}"  # Fallback: generate deterministic ID
    )
    
    if "account_id" not in raw_account:
        applied_transformations.append("generated_account_id")
    
    # Extract name (required field)
    name = (
        raw_account.get("name") or
        raw_account.get("Name") or
        raw_account.get("company") or
        raw_account.get("Company") or
        "Unknown Account"
    )
    
    if name == "Unknown Account":
        applied_transformations.append("defaulted_missing_name")
    
    # Normalize status
    raw_status = raw_account.get("status", "").lower()
    status_mapping = {
        "prospect": AccountStatus.PROSPECT,
        "lead": AccountStatus.PROSPECT,
        "qualified": AccountStatus.QUALIFIED,
        "active": AccountStatus.ACTIVE,
        "customer": AccountStatus.ACTIVE,
        "dormant": AccountStatus.DORMANT,
        "inactive": AccountStatus.DORMANT,
        "churned": AccountStatus.CHURNED,
        "lost": AccountStatus.CHURNED,
    }
    status = status_mapping.get(raw_status, AccountStatus.PROSPECT)
    
    if raw_status and raw_status not in status_mapping:
        applied_transformations.append(f"mapped_unknown_status_{raw_status}_to_prospect")
    
    # Normalize industry
    industry = (
        raw_account.get("industry") or
        raw_account.get("Industry") or
        raw_account.get("sector")
    )
    
    # Normalize employee count
    employee_count = None
    raw_employees = raw_account.get("employee_count") or raw_account.get("employees")
    if raw_employees:
        try:
            employee_count = int(raw_employees)
        except (ValueError, TypeError):
            applied_transformations.append("failed_to_parse_employee_count")
    
    # Normalize revenue
    revenue = None
    raw_revenue = raw_account.get("revenue") or raw_account.get("annual_revenue")
    if raw_revenue:
        try:
            # Handle currency strings like "$1,500,000"
            cleaned_revenue = re.sub(r'[^\d.]', '', str(raw_revenue))
            revenue = float(cleaned_revenue) if cleaned_revenue else None
        except (ValueError, TypeError):
            applied_transformations.append("failed_to_parse_revenue")
    
    # Normalize region
    region = (
        raw_account.get("region") or
        raw_account.get("territory") or
        raw_account.get("state") or
        raw_account.get("country")
    )
    
    # Build canonical record
    normalized = AccountRecord(
        account_id=str(account_id),
        name=name,
        status=status,
        industry=industry,
        employee_count=employee_count,
        revenue=revenue,
        region=region,
        metadata={
            "source_type": source_type,
            "original_fields": list(raw_account.keys()),
        },
    )
    
    # Calculate data completeness confidence
    required_fields = [normalized.account_id, normalized.name]
    optional_fields = [normalized.industry, normalized.employee_count, normalized.revenue, normalized.region]
    
    completeness = (
        len([f for f in required_fields if f]) / len(required_fields) * 0.7 +
        len([f for f in optional_fields if f]) / len(optional_fields) * 0.3
    )
    
    logger.info(
        f"[{trace_id}] Normalized account {account_id} from {source_type}. "
        f"Confidence: {completeness:.2f}, Transformations: {len(applied_transformations)}"
    )
    
    return {
        "normalized_account": normalized.to_dict(),
        "applied_transformations": applied_transformations,
        "confidence": round(completeness, 2),
    }


def score_account_fit(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score account fit against Ideal Customer Profile (ICP).
    
    WHY: Not all accounts are equal. ICP scoring helps reps prioritize
    high-value, high-fit prospects.
    
    CAPABILITY: Account qualification and prioritization.
    VENDOR-NEUTRAL: Works with canonical AccountRecord.
    OFFLINE: Rule-based scoring (no external calls).
    
    Args:
        inputs: {
            "account": Dict[str, Any],  # Normalized AccountRecord
            "icp_criteria": Dict[str, Any],  # {
            #     "min_revenue": float (optional),
            #     "max_revenue": float (optional),
            #     "industries": List[str] (optional),
            #     "min_employees": int (optional),
            #     "max_employees": int (optional),
            #     "regions": List[str] (optional),
            # }
        }
        context: {
            "profile": str,
            "trace_id": str,
        }
        
    Returns: {
        "account_id": str,
        "fit_score": float,  # 0.0 to 1.0
        "fit_breakdown": {
            "revenue_fit": float,
            "industry_fit": float,
            "employee_fit": float,
            "region_fit": float,
        },
        "recommendation": str,  # "high_priority" | "medium_priority" | "low_priority"
        "reasoning": List[str],
    }
    """
    trace_id = context.get("trace_id", "unknown")
    
    if "account" not in inputs or "icp_criteria" not in inputs:
        raise ValueError("Required fields missing: account, icp_criteria")
    
    account = inputs["account"]
    icp = inputs["icp_criteria"]
    
    # Score components (each 0.0 to 1.0)
    revenue_fit = _score_revenue_fit(account.get("revenue"), icp)
    industry_fit = _score_industry_fit(account.get("industry"), icp)
    employee_fit = _score_employee_fit(account.get("employee_count"), icp)
    region_fit = _score_region_fit(account.get("region"), icp)
    
    # Weighted average (revenue and industry weighted higher)
    fit_score = (
        revenue_fit * 0.35 +
        industry_fit * 0.35 +
        employee_fit * 0.15 +
        region_fit * 0.15
    )
    
    # Generate recommendation
    if fit_score >= 0.75:
        recommendation = "high_priority"
        reasoning = ["Strong ICP alignment across multiple dimensions"]
    elif fit_score >= 0.5:
        recommendation = "medium_priority"
        reasoning = ["Moderate ICP alignment, assess other factors"]
    else:
        recommendation = "low_priority"
        reasoning = ["Weak ICP alignment, consider deprioritizing"]
    
    # Add specific reasoning
    if revenue_fit < 0.5:
        reasoning.append("Revenue outside ICP range")
    if industry_fit == 0.0:
        reasoning.append("Industry not in ICP target list")
    if employee_fit < 0.5:
        reasoning.append("Employee count outside ICP range")
    
    logger.info(
        f"[{trace_id}] Scored account {account.get('account_id')}: "
        f"fit={fit_score:.2f}, recommendation={recommendation}"
    )
    
    return {
        "account_id": account.get("account_id"),
        "fit_score": round(fit_score, 2),
        "fit_breakdown": {
            "revenue_fit": round(revenue_fit, 2),
            "industry_fit": round(industry_fit, 2),
            "employee_fit": round(employee_fit, 2),
            "region_fit": round(region_fit, 2),
        },
        "recommendation": recommendation,
        "reasoning": reasoning,
    }


def retrieve_account_signals(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieve buying signals for an account.
    
    WHY: Timing is everything in sales. Buying signals (funding, hiring,
    tech stack changes) indicate readiness to buy.
    
    CAPABILITY: Signal aggregation and prioritization.
    VENDOR-NEUTRAL: Returns standardized signal format.
    ADAPTER-AWARE: Uses HubSpot adapter if configured, falls back to empty (offline).
    
    Args:
        inputs: {
            "account_id": str,
            "signal_types": List[str] (optional),  # ["funding", "hiring", "tech_stack", "news"]
            "fetch_from_crm": bool (optional, default: False),  # Whether to fetch from CRM adapter
        }
        context: {
            "profile": str,
            "trace_id": str,
        }
        
    Returns: {
        "account_id": str,
        "signals": List[{
            "signal_type": str,
            "description": str,
            "confidence": float,
            "timestamp": str (ISO 8601),
        }],
        "signal_count": int,
        "priority_score": float,  # 0.0 to 1.0
        "source": str,  # "offline" | "hubspot" | "adapter_unavailable"
    }
    """
    trace_id = context.get("trace_id", "unknown")
    account_id = inputs.get("account_id", "unknown")
    fetch_from_crm = inputs.get("fetch_from_crm", False)
    
    signals = []
    source = "offline"
    
    # If fetch_from_crm requested, try adapter
    if fetch_from_crm:
        adapter = _get_crm_adapter()
        
        if adapter:
            try:
                # Fetch account from CRM for enrichment signals
                account_data = adapter.get_account(account_id, context)
                
                # Extract signals from CRM data (enrichment opportunities)
                if account_data.get("revenue"):
                    signals.append({
                        "signal_type": "financial",
                        "description": f"Revenue: ${account_data['revenue']:,.0f}",
                        "confidence": 1.0,
                        "timestamp": account_data.get("metadata", {}).get("updated_at", ""),
                    })
                
                if account_data.get("industry"):
                    signals.append({
                        "signal_type": "firmographic",
                        "description": f"Industry: {account_data['industry']}",
                        "confidence": 1.0,
                        "timestamp": account_data.get("metadata", {}).get("updated_at", ""),
                    })
                
                source = "hubspot"
                logger.info(f"[{trace_id}] Retrieved {len(signals)} signals from HubSpot for {account_id}")
                
            except Exception as e:
                logger.warning(f"[{trace_id}] Failed to fetch signals from adapter: {e}. Falling back to offline mode.")
                source = "adapter_unavailable"
        else:
            logger.info(f"[{trace_id}] No CRM adapter configured. Operating in offline mode.")
            source = "offline"
    else:
        logger.info(f"[{trace_id}] Signal retrieval for account {account_id} (offline mode - set fetch_from_crm=true to use adapter)")
    
    # Calculate priority score (simplified: based on signal count and confidence)
    priority_score = min(len(signals) * 0.2, 1.0) if signals else 0.0
    
    return {
        "account_id": account_id,
        "signals": signals,
        "signal_count": len(signals),
        "priority_score": priority_score,
        "source": source,
    }


# Helper functions for ICP scoring

def _score_revenue_fit(revenue: Optional[float], icp: Dict[str, Any]) -> float:
    """Score revenue fit (0.0 to 1.0)."""
    if revenue is None:
        return 0.5  # Neutral score if unknown
    
    min_revenue = icp.get("min_revenue")
    max_revenue = icp.get("max_revenue")
    
    if min_revenue is None and max_revenue is None:
        return 1.0  # No constraint = perfect fit
    
    if min_revenue and revenue < min_revenue:
        return 0.0
    if max_revenue and revenue > max_revenue:
        return 0.0
    
    return 1.0


def _score_industry_fit(industry: Optional[str], icp: Dict[str, Any]) -> float:
    """Score industry fit (0.0 or 1.0)."""
    if industry is None:
        return 0.5  # Neutral score if unknown
    
    target_industries = icp.get("industries", [])
    if not target_industries:
        return 1.0  # No constraint = perfect fit
    
    # Case-insensitive match
    industry_lower = industry.lower()
    matches = [t.lower() for t in target_industries if t.lower() in industry_lower]
    
    return 1.0 if matches else 0.0


def _score_employee_fit(employee_count: Optional[int], icp: Dict[str, Any]) -> float:
    """Score employee count fit (0.0 to 1.0)."""
    if employee_count is None:
        return 0.5  # Neutral score if unknown
    
    min_employees = icp.get("min_employees")
    max_employees = icp.get("max_employees")
    
    if min_employees is None and max_employees is None:
        return 1.0  # No constraint = perfect fit
    
    if min_employees and employee_count < min_employees:
        return 0.0
    if max_employees and employee_count > max_employees:
        return 0.0
    
    return 1.0


def _score_region_fit(region: Optional[str], icp: Dict[str, Any]) -> float:
    """Score region fit (0.0 or 1.0)."""
    if region is None:
        return 0.5  # Neutral score if unknown
    
    target_regions = icp.get("regions", [])
    if not target_regions:
        return 1.0  # No constraint = perfect fit
    
    # Case-insensitive match
    region_lower = region.lower()
    matches = [r.lower() for r in target_regions if r.lower() in region_lower]
    
    return 1.0 if matches else 0.0


# Schemas for registry

SCHEMA_normalize_account_record = {
    "name": "normalize_account_record",
    "description": "Normalize account data from any source into canonical schema (READ-ONLY)",
    "inputs": {
        "account_data": {"type": "object", "required": True},
        "source_type": {"type": "string", "required": False},
    },
    "outputs": {
        "normalized_account": {"type": "object"},
        "applied_transformations": {"type": "array"},
        "confidence": {"type": "number"},
    },
}

SCHEMA_score_account_fit = {
    "name": "score_account_fit",
    "description": "Score account fit against Ideal Customer Profile (READ-ONLY)",
    "inputs": {
        "account": {"type": "object", "required": True},
        "icp_criteria": {"type": "object", "required": True},
    },
    "outputs": {
        "account_id": {"type": "string"},
        "fit_score": {"type": "number"},
        "fit_breakdown": {"type": "object"},
        "recommendation": {"type": "string"},
        "reasoning": {"type": "array"},
    },
}

SCHEMA_retrieve_account_signals = {
    "name": "retrieve_account_signals",
    "description": "Retrieve buying signals for account (STUB - adapter integration in Phase 4)",
    "inputs": {
        "account_id": {"type": "string", "required": True},
        "signal_types": {"type": "array", "required": False},
    },
    "outputs": {
        "account_id": {"type": "string"},
        "signals": {"type": "array"},
        "signal_count": {"type": "integer"},
        "priority_score": {"type": "number"},
    },
}
