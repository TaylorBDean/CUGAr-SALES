"""
Domain 4: Intelligence & Optimization Capabilities

WHY: Sales teams need to learn from past deals to improve future performance.
Win/loss analysis identifies patterns in successful vs failed deals.
ICP refinement ensures targeting improves over time.

SAFETY: Analysis-only, no automated decisions. Human reviews recommendations.
Pattern extraction is deterministic and explainable.

OFFLINE-FIRST: Analysis works on historical deal data (no external calls).
Signal adapter integration is opt-in for enrichment.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, Counter
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DealOutcome(str, Enum):
    """Deal outcomes for win/loss analysis."""
    WON = "won"
    LOST = "lost"
    ACTIVE = "active"  # Still in pipeline


class LossReason(str, Enum):
    """Common reasons for deal loss."""
    PRICE = "price"
    TIMING = "timing"
    NO_BUDGET = "no_budget"
    COMPETITOR = "competitor"
    NO_DECISION = "no_decision"
    POOR_FIT = "poor_fit"
    CHAMPION_LEFT = "champion_left"
    OTHER = "other"


class WinFactor(str, Enum):
    """Common factors in won deals."""
    STRONG_CHAMPION = "strong_champion"
    URGENT_NEED = "urgent_need"
    BUDGET_APPROVED = "budget_approved"
    GOOD_FIT = "good_fit"
    COMPETITIVE_PRICE = "competitive_price"
    FAST_SALES_CYCLE = "fast_sales_cycle"
    EXECUTIVE_SPONSORSHIP = "executive_sponsorship"
    OTHER = "other"


def analyze_win_loss_patterns(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze historical deals to identify win/loss patterns and improvement opportunities.
    
    WHY: Sales teams repeat mistakes without learning from past deals.
    Pattern analysis identifies what works and what doesn't.
    
    CAPABILITY: Statistical analysis of deal outcomes with actionable insights.
    OFFLINE: Works on historical deal data (no external calls).
    EXPLAINABLE: Every pattern includes supporting data and confidence scores.
    
    Args:
        inputs:
            deals: List[Dict] - Historical deal records
                {
                    deal_id: str,
                    outcome: DealOutcome (won/lost/active),
                    account: Dict (name, industry, revenue, employee_count),
                    deal_value: float,
                    sales_cycle_days: int,
                    close_date: str (ISO format),
                    loss_reason: Optional[LossReason],
                    win_factors: Optional[List[WinFactor]],
                    qualification_score: Optional[float] (0-1),
                }
            min_deals_for_pattern: int (default 3) - Minimum deals to identify pattern
            time_period_days: Optional[int] - Only analyze recent deals
        context:
            trace_id: Request trace ID
            profile: Execution profile
    
    Returns:
        {
            summary: {
                total_deals: int,
                won_count: int,
                lost_count: int,
                win_rate: float (0-1),
                avg_deal_value_won: float,
                avg_deal_value_lost: float,
                avg_sales_cycle_won: int (days),
                avg_sales_cycle_lost: int (days),
            },
            win_patterns: [
                {
                    pattern_type: str (e.g., "industry"),
                    pattern_value: str (e.g., "Technology"),
                    win_rate: float (0-1),
                    deal_count: int,
                    avg_deal_value: float,
                    confidence: float (0-1),
                    recommendation: str,
                }
            ],
            loss_patterns: [
                {
                    loss_reason: LossReason,
                    count: int,
                    percentage: float (0-1),
                    common_attributes: [str],
                    recommendation: str,
                }
            ],
            icp_recommendations: [
                {
                    attribute: str (e.g., "revenue_range"),
                    current: str,
                    recommended: str,
                    rationale: str,
                    confidence: float (0-1),
                }
            ],
            qualification_insights: {
                optimal_threshold: float (0-1),
                false_positives: int,  # Qualified but lost
                false_negatives: int,  # Not qualified but won
                accuracy: float (0-1),
            },
        }
    
    Example:
        >>> result = analyze_win_loss_patterns(
        ...     inputs={
        ...         "deals": [
        ...             {
        ...                 "deal_id": "001",
        ...                 "outcome": "won",
        ...                 "account": {"name": "Acme", "industry": "Technology", "revenue": 50000000},
        ...                 "deal_value": 100000,
        ...                 "sales_cycle_days": 45,
        ...                 "qualification_score": 0.85,
        ...             },
        ...             # ... more deals
        ...         ],
        ...         "min_deals_for_pattern": 3,
        ...     },
        ...     context={"trace_id": "analysis-001", "profile": "sales"}
        ... )
        >>> result["summary"]["win_rate"]
        0.65  # 65% win rate
    """
    trace_id = context.get("trace_id", "unknown")
    
    # Extract inputs
    deals = inputs.get("deals", [])
    min_deals_for_pattern = inputs.get("min_deals_for_pattern", 3)
    time_period_days = inputs.get("time_period_days")
    
    logger.info(f"[{trace_id}] Analyzing {len(deals)} deals for win/loss patterns")
    
    # Validate inputs
    if not deals:
        return {
            "status": "error",
            "error": "No deals provided for analysis",
        }
    
    # Filter by time period if specified
    if time_period_days:
        cutoff_date = datetime.now()
        from datetime import timedelta
        cutoff_date = cutoff_date - timedelta(days=time_period_days)
        
        filtered_deals = []
        for deal in deals:
            close_date_str = deal.get("close_date")
            if close_date_str:
                try:
                    close_date = datetime.fromisoformat(close_date_str.replace("Z", "+00:00"))
                    if close_date >= cutoff_date:
                        filtered_deals.append(deal)
                except (ValueError, AttributeError):
                    # Skip deals with invalid dates
                    pass
        
        deals = filtered_deals
        logger.info(f"[{trace_id}] Filtered to {len(deals)} deals in last {time_period_days} days")
    
    # Separate won/lost deals
    won_deals = [d for d in deals if d.get("outcome") == DealOutcome.WON.value]
    lost_deals = [d for d in deals if d.get("outcome") == DealOutcome.LOST.value]
    
    total_deals = len(won_deals) + len(lost_deals)
    if total_deals == 0:
        return {
            "status": "error",
            "error": "No won or lost deals found (only active deals)",
        }
    
    # Calculate summary statistics
    win_rate = len(won_deals) / total_deals if total_deals > 0 else 0.0
    
    avg_deal_value_won = sum(d.get("deal_value", 0) for d in won_deals) / len(won_deals) if won_deals else 0.0
    avg_deal_value_lost = sum(d.get("deal_value", 0) for d in lost_deals) / len(lost_deals) if lost_deals else 0.0
    
    avg_sales_cycle_won = sum(d.get("sales_cycle_days", 0) for d in won_deals) / len(won_deals) if won_deals else 0
    avg_sales_cycle_lost = sum(d.get("sales_cycle_days", 0) for d in lost_deals) / len(lost_deals) if lost_deals else 0
    
    # Identify win patterns by industry
    win_patterns = []
    
    # Pattern 1: Industry analysis
    industry_stats = {}
    for deal in won_deals + lost_deals:
        industry = deal.get("account", {}).get("industry", "Unknown")
        if industry not in industry_stats:
            industry_stats[industry] = {"won": 0, "lost": 0, "total_value": 0.0}
        
        if deal.get("outcome") == DealOutcome.WON.value:
            industry_stats[industry]["won"] += 1
            industry_stats[industry]["total_value"] += deal.get("deal_value", 0)
        else:
            industry_stats[industry]["lost"] += 1
    
    for industry, stats in industry_stats.items():
        total_deals_in_industry = stats["won"] + stats["lost"]
        if total_deals_in_industry >= min_deals_for_pattern:
            industry_win_rate = stats["won"] / total_deals_in_industry
            avg_value = stats["total_value"] / stats["won"] if stats["won"] > 0 else 0.0
            
            # Confidence based on sample size
            confidence = min(1.0, total_deals_in_industry / (min_deals_for_pattern * 3))
            
            recommendation = ""
            if industry_win_rate >= 0.7:
                recommendation = f"Strong fit: Target more {industry} accounts"
            elif industry_win_rate <= 0.3:
                recommendation = f"Poor fit: Reduce focus on {industry} accounts"
            else:
                recommendation = f"Moderate fit: Continue testing {industry} segment"
            
            win_patterns.append({
                "pattern_type": "industry",
                "pattern_value": industry,
                "win_rate": round(industry_win_rate, 2),
                "deal_count": total_deals_in_industry,
                "avg_deal_value": round(avg_value, 2),
                "confidence": round(confidence, 2),
                "recommendation": recommendation,
            })
    
    # Pattern 2: Company size (revenue) analysis
    revenue_buckets = {
        "0-10M": (0, 10_000_000),
        "10-50M": (10_000_000, 50_000_000),
        "50-100M": (50_000_000, 100_000_000),
        "100M+": (100_000_000, float('inf')),
    }
    
    revenue_stats = {bucket: {"won": 0, "lost": 0, "total_value": 0.0} for bucket in revenue_buckets}
    
    for deal in won_deals + lost_deals:
        revenue = deal.get("account", {}).get("revenue", 0)
        for bucket_name, (min_rev, max_rev) in revenue_buckets.items():
            if min_rev <= revenue < max_rev:
                if deal.get("outcome") == DealOutcome.WON.value:
                    revenue_stats[bucket_name]["won"] += 1
                    revenue_stats[bucket_name]["total_value"] += deal.get("deal_value", 0)
                else:
                    revenue_stats[bucket_name]["lost"] += 1
                break
    
    for bucket, stats in revenue_stats.items():
        total_deals_in_bucket = stats["won"] + stats["lost"]
        if total_deals_in_bucket >= min_deals_for_pattern:
            bucket_win_rate = stats["won"] / total_deals_in_bucket
            avg_value = stats["total_value"] / stats["won"] if stats["won"] > 0 else 0.0
            confidence = min(1.0, total_deals_in_bucket / (min_deals_for_pattern * 3))
            
            recommendation = ""
            if bucket_win_rate >= 0.7:
                recommendation = f"Sweet spot: Focus on ${bucket} revenue range"
            elif bucket_win_rate <= 0.3:
                recommendation = f"Poor fit: Avoid ${bucket} revenue range"
            else:
                recommendation = f"Moderate: Continue testing ${bucket} segment"
            
            win_patterns.append({
                "pattern_type": "revenue_range",
                "pattern_value": bucket,
                "win_rate": round(bucket_win_rate, 2),
                "deal_count": total_deals_in_bucket,
                "avg_deal_value": round(avg_value, 2),
                "confidence": round(confidence, 2),
                "recommendation": recommendation,
            })
    
    # Analyze loss reasons
    loss_patterns = []
    loss_reason_counts = {}
    
    for deal in lost_deals:
        reason = deal.get("loss_reason", LossReason.OTHER.value)
        if reason not in loss_reason_counts:
            loss_reason_counts[reason] = {"count": 0, "industries": [], "revenue_ranges": []}
        
        loss_reason_counts[reason]["count"] += 1
        industry = deal.get("account", {}).get("industry", "Unknown")
        loss_reason_counts[reason]["industries"].append(industry)
        
        revenue = deal.get("account", {}).get("revenue", 0)
        for bucket_name, (min_rev, max_rev) in revenue_buckets.items():
            if min_rev <= revenue < max_rev:
                loss_reason_counts[reason]["revenue_ranges"].append(bucket_name)
                break
    
    total_losses = len(lost_deals)
    for reason, data in loss_reason_counts.items():
        count = data["count"]
        percentage = count / total_losses if total_losses > 0 else 0.0
        
        # Find common attributes (most frequent industry/revenue range for this loss reason)
        from collections import Counter
        industry_counter = Counter(data["industries"])
        revenue_counter = Counter(data["revenue_ranges"])
        
        common_attrs = []
        if industry_counter:
            most_common_industry = industry_counter.most_common(1)[0]
            if most_common_industry[1] >= 2:  # At least 2 occurrences
                common_attrs.append(f"Industry: {most_common_industry[0]}")
        
        if revenue_counter:
            most_common_revenue = revenue_counter.most_common(1)[0]
            if most_common_revenue[1] >= 2:
                common_attrs.append(f"Revenue: {most_common_revenue[0]}")
        
        # Generate recommendation based on loss reason
        recommendations = {
            LossReason.PRICE.value: "Consider value-based pricing or early price anchoring",
            LossReason.TIMING.value: "Improve timing qualification in discovery calls",
            LossReason.NO_BUDGET.value: "Qualify budget earlier in sales cycle",
            LossReason.COMPETITOR.value: "Strengthen competitive differentiation messaging",
            LossReason.NO_DECISION.value: "Build stronger urgency and champion support",
            LossReason.POOR_FIT.value: "Tighten ICP criteria to avoid poor-fit prospects",
            LossReason.CHAMPION_LEFT.value: "Multi-thread relationships earlier in cycle",
        }
        
        recommendation = recommendations.get(reason, "Review and document loss reason details")
        
        loss_patterns.append({
            "loss_reason": reason,
            "count": count,
            "percentage": round(percentage, 2),
            "common_attributes": common_attrs,
            "recommendation": recommendation,
        })
    
    # Sort loss patterns by frequency
    loss_patterns.sort(key=lambda x: x["count"], reverse=True)
    
    # Generate ICP recommendations based on win patterns
    icp_recommendations = []
    
    # Recommend industries with high win rates
    high_win_industries = [p for p in win_patterns if p["pattern_type"] == "industry" and p["win_rate"] >= 0.6]
    if high_win_industries:
        industries = [p["pattern_value"] for p in high_win_industries]
        icp_recommendations.append({
            "attribute": "target_industries",
            "current": "Unknown",
            "recommended": ", ".join(industries),
            "rationale": f"These industries show {high_win_industries[0]['win_rate']:.0%}+ win rates",
            "confidence": round(sum(p["confidence"] for p in high_win_industries) / len(high_win_industries), 2),
        })
    
    # Recommend revenue ranges with high win rates
    high_win_revenue = [p for p in win_patterns if p["pattern_type"] == "revenue_range" and p["win_rate"] >= 0.6]
    if high_win_revenue:
        ranges = [p["pattern_value"] for p in high_win_revenue]
        icp_recommendations.append({
            "attribute": "revenue_range",
            "current": "Unknown",
            "recommended": ", ".join(ranges),
            "rationale": f"These revenue ranges show {high_win_revenue[0]['win_rate']:.0%}+ win rates",
            "confidence": round(sum(p["confidence"] for p in high_win_revenue) / len(high_win_revenue), 2),
        })
    
    # Analyze qualification score accuracy
    qualification_insights = _analyze_qualification_accuracy(won_deals, lost_deals)
    
    logger.info(
        f"[{trace_id}] Analysis complete: {win_rate:.0%} win rate, "
        f"{len(win_patterns)} win patterns, {len(loss_patterns)} loss patterns"
    )
    
    return {
        "summary": {
            "total_deals": total_deals,
            "won_count": len(won_deals),
            "lost_count": len(lost_deals),
            "win_rate": round(win_rate, 2),
            "avg_deal_value_won": round(avg_deal_value_won, 2),
            "avg_deal_value_lost": round(avg_deal_value_lost, 2),
            "avg_sales_cycle_won": round(avg_sales_cycle_won),
            "avg_sales_cycle_lost": round(avg_sales_cycle_lost),
        },
        "win_patterns": win_patterns,
        "loss_patterns": loss_patterns,
        "icp_recommendations": icp_recommendations,
        "qualification_insights": qualification_insights,
    }


def _analyze_qualification_accuracy(won_deals: List[Dict], lost_deals: List[Dict]) -> Dict[str, Any]:
    """
    Analyze qualification score accuracy (internal helper).
    
    Calculates false positives (qualified but lost) and false negatives (not qualified but won)
    to recommend optimal qualification threshold.
    """
    # Default threshold is 0.7 (70%)
    thresholds_to_test = [0.5, 0.6, 0.7, 0.8, 0.9]
    
    best_threshold = 0.7
    best_accuracy = 0.0
    
    for threshold in thresholds_to_test:
        # Count correct predictions
        correct = 0
        total = 0
        
        for deal in won_deals:
            score = deal.get("qualification_score")
            if score is not None:
                total += 1
                if score >= threshold:  # Predicted win
                    correct += 1
        
        for deal in lost_deals:
            score = deal.get("qualification_score")
            if score is not None:
                total += 1
                if score < threshold:  # Predicted loss
                    correct += 1
        
        if total > 0:
            accuracy = correct / total
            if accuracy > best_accuracy:
                best_accuracy = accuracy
                best_threshold = threshold
    
    # Calculate false positives/negatives at optimal threshold
    false_positives = 0  # Qualified (score >= threshold) but lost
    false_negatives = 0  # Not qualified (score < threshold) but won
    
    for deal in lost_deals:
        score = deal.get("qualification_score")
        if score is not None and score >= best_threshold:
            false_positives += 1
    
    for deal in won_deals:
        score = deal.get("qualification_score")
        if score is not None and score < best_threshold:
            false_negatives += 1
    
    return {
        "optimal_threshold": round(best_threshold, 2),
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "accuracy": round(best_accuracy, 2),
    }


def extract_buyer_personas(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract common buyer personas from won deals.
    
    WHY: Understanding who buys helps target similar prospects.
    Buyer personas guide messaging, channels, and qualification.
    
    CAPABILITY: Pattern extraction from won deal contacts/roles.
    OFFLINE: Works on historical deal data.
    
    Args:
        inputs:
            deals: List[Dict] - Historical won deals with contact data
                {
                    deal_id: str,
                    outcome: "won",
                    contacts: [
                        {
                            name: str,
                            title: str,
                            department: str,
                            role: str (e.g., "champion", "decision_maker", "influencer"),
                            seniority: str (e.g., "C-level", "VP", "Director", "Manager"),
                        }
                    ],
                }
            min_occurrences: int (default 3) - Minimum occurrences to identify persona
        context:
            trace_id: Request trace ID
            profile: Execution profile
    
    Returns:
        {
            personas: [
                {
                    title_pattern: str (e.g., "VP Sales", "CTO"),
                    department: str (e.g., "Sales", "Engineering"),
                    seniority: str (e.g., "VP", "C-level"),
                    occurrence_count: int,
                    typical_roles: [str] (champion, decision_maker, influencer),
                    recommendation: str,
                }
            ],
            decision_maker_patterns: {
                most_common_title: str,
                most_common_seniority: str,
                recommendation: str,
            },
        }
    
    Example:
        >>> result = extract_buyer_personas(
        ...     inputs={
        ...         "deals": [
        ...             {
        ...                 "deal_id": "001",
        ...                 "outcome": "won",
        ...                 "contacts": [
        ...                     {"title": "VP Sales", "department": "Sales", "role": "champion", "seniority": "VP"},
        ...                     {"title": "CFO", "department": "Finance", "role": "decision_maker", "seniority": "C-level"},
        ...                 ]
        ...             },
        ...             # ... more deals
        ...         ],
        ...         "min_occurrences": 3,
        ...     },
        ...     context={"trace_id": "persona-001", "profile": "sales"}
        ... )
    """
    trace_id = context.get("trace_id", "unknown")
    
    deals = inputs.get("deals", [])
    min_occurrences = inputs.get("min_occurrences", 3)
    
    logger.info(f"[{trace_id}] Extracting buyer personas from {len(deals)} won deals")
    
    if not deals:
        return {
            "status": "error",
            "error": "No deals provided for persona extraction",
        }
    
    # Only analyze won deals
    won_deals = [d for d in deals if d.get("outcome") == DealOutcome.WON.value]
    
    if not won_deals:
        return {
            "status": "error",
            "error": "No won deals found for persona extraction",
        }
    
    # Count title/department/seniority combinations
    from collections import Counter
    title_counts = Counter()
    department_counts = Counter()
    seniority_counts = Counter()
    role_by_title = {}
    decision_maker_titles = []
    decision_maker_seniority = []
    
    for deal in won_deals:
        contacts = deal.get("contacts", [])
        for contact in contacts:
            title = contact.get("title", "Unknown")
            department = contact.get("department", "Unknown")
            seniority = contact.get("seniority", "Unknown")
            role = contact.get("role", "unknown")
            
            if title != "Unknown":
                title_counts[title] += 1
                
                if title not in role_by_title:
                    role_by_title[title] = []
                role_by_title[title].append(role)
            
            if department != "Unknown":
                department_counts[department] += 1
            
            if seniority != "Unknown":
                seniority_counts[seniority] += 1
            
            if role == "decision_maker":
                decision_maker_titles.append(title)
                decision_maker_seniority.append(seniority)
    
    # Build personas from common titles
    personas = []
    for title, count in title_counts.most_common():
        if count >= min_occurrences:
            # Find most common department for this title
            # (Would need more sophisticated logic in production)
            typical_roles = list(set(role_by_title.get(title, [])))
            
            recommendation = ""
            if "decision_maker" in typical_roles:
                recommendation = f"Target {title}s as primary decision makers"
            elif "champion" in typical_roles:
                recommendation = f"Target {title}s as champions, multi-thread to decision makers"
            else:
                recommendation = f"Target {title}s as influencers in buying process"
            
            personas.append({
                "title_pattern": title,
                "department": "Unknown",  # Would extract from contact data
                "seniority": "Unknown",  # Would extract from title parsing
                "occurrence_count": count,
                "typical_roles": typical_roles,
                "recommendation": recommendation,
            })
    
    # Decision maker patterns
    decision_maker_title_counter = Counter(decision_maker_titles)
    decision_maker_seniority_counter = Counter(decision_maker_seniority)
    
    most_common_dm_title = decision_maker_title_counter.most_common(1)[0][0] if decision_maker_title_counter else "Unknown"
    most_common_dm_seniority = decision_maker_seniority_counter.most_common(1)[0][0] if decision_maker_seniority_counter else "Unknown"
    
    dm_recommendation = f"Focus on reaching {most_common_dm_seniority} level ({most_common_dm_title}) for final approvals"
    
    logger.info(f"[{trace_id}] Extracted {len(personas)} buyer personas from {len(won_deals)} won deals")
    
    return {
        "personas": personas,
        "decision_maker_patterns": {
            "most_common_title": most_common_dm_title,
            "most_common_seniority": most_common_dm_seniority,
            "recommendation": dm_recommendation,
        },
    }
