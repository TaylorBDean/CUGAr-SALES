"""
Domain 5: Qualification & Deal Progression Capabilities

WHY: Qualification is where deals are won or lost. Bad qualification
wastes reps' time on unwinnable deals. Good qualification focuses effort.

SAFETY: Qualification assessments are advisory only. No auto-disqualification.
Human judgment is final.

OFFLINE-FIRST: BANT/MEDDICC scoring runs locally with no external dependencies.
"""

from __future__ import annotations

from typing import Dict, Any, List
import logging

from .schemas import QualificationCriteria, DealStage, OpportunityRecord

logger = logging.getLogger(__name__)


def qualify_opportunity(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Qualify opportunity using BANT/MEDDICC framework.
    
    WHY: Structured qualification (Budget, Authority, Need, Timing + MEDDICC)
    prevents wasted effort on poor-fit deals.
    
    CAPABILITY: Opportunity assessment and scoring.
    VENDOR-NEUTRAL: Works with any opportunity data.
    OFFLINE: Rule-based scoring, no external calls.
    
    Args:
        inputs: {
            "opportunity_id": str,
            "criteria": {
                "budget": bool (optional),
                "authority": bool (optional),
                "need": bool (optional),
                "timing": bool (optional),
                # MEDDICC extensions
                "metrics": bool (optional),
                "economic_buyer": bool (optional),
                "decision_criteria": bool (optional),
                "decision_process": bool (optional),
                "identify_pain": bool (optional),
                "champion": bool (optional),
                "competition": bool (optional),
            },
            "notes": str (optional),
        }
        context: {
            "profile": str,
            "trace_id": str,
        }
        
    Returns: {
        "opportunity_id": str,
        "qualification_score": float,  # 0.0 to 1.0
        "qualified": bool,  # True if score >= 0.5
        "framework": str,  # "BANT" | "MEDDICC"
        "strengths": List[str],
        "gaps": List[str],
        "recommendations": List[str],
        "requires_review": bool,  # True if borderline score (0.4-0.6)
    }
    """
    trace_id = context.get("trace_id", "unknown")
    
    if "opportunity_id" not in inputs or "criteria" not in inputs:
        raise ValueError("Required fields missing: opportunity_id, criteria")
    
    opportunity_id = inputs["opportunity_id"]
    criteria_dict = inputs["criteria"]
    
    # Build QualificationCriteria object
    criteria = QualificationCriteria(
        budget=criteria_dict.get("budget"),
        authority=criteria_dict.get("authority"),
        need=criteria_dict.get("need"),
        timing=criteria_dict.get("timing"),
        metrics=criteria_dict.get("metrics"),
        economic_buyer=criteria_dict.get("economic_buyer"),
        decision_criteria=criteria_dict.get("decision_criteria"),
        decision_process=criteria_dict.get("decision_process"),
        identify_pain=criteria_dict.get("identify_pain"),
        champion=criteria_dict.get("champion"),
        competition=criteria_dict.get("competition"),
    )
    
    # Calculate qualification score
    qualification_score = criteria.score()
    qualified = qualification_score >= 0.5
    
    # Determine framework used
    has_meddicc = any([
        criteria.metrics, criteria.economic_buyer, criteria.decision_criteria,
        criteria.decision_process, criteria.identify_pain, criteria.champion,
        criteria.competition
    ])
    framework = "MEDDICC" if has_meddicc else "BANT"
    
    # Analyze strengths and gaps
    strengths = []
    gaps = []
    
    bant_fields = {
        "budget": criteria.budget,
        "authority": criteria.authority,
        "need": criteria.need,
        "timing": criteria.timing,
    }
    for field, value in bant_fields.items():
        if value:
            strengths.append(f"{field.upper()} confirmed")
        elif value is False:
            gaps.append(f"{field.upper()} not confirmed")
    
    if has_meddicc:
        meddicc_fields = {
            "metrics": criteria.metrics,
            "economic_buyer": criteria.economic_buyer,
            "decision_criteria": criteria.decision_criteria,
            "decision_process": criteria.decision_process,
            "identify_pain": criteria.identify_pain,
            "champion": criteria.champion,
            "competition": criteria.competition,
        }
        for field, value in meddicc_fields.items():
            if value:
                strengths.append(f"MEDDICC: {field.replace('_', ' ')} identified")
            elif value is False:
                gaps.append(f"MEDDICC: {field.replace('_', ' ')} missing")
    
    # Generate recommendations
    recommendations = []
    if not criteria.authority:
        recommendations.append("Schedule discovery call with decision-maker to confirm authority")
    if not criteria.budget:
        recommendations.append("Qualify budget availability and approval process")
    if not criteria.need:
        recommendations.append("Conduct needs analysis to confirm pain points")
    if not criteria.timing:
        recommendations.append("Establish clear timeline and decision deadlines")
    
    if qualification_score < 0.3:
        recommendations.append("CRITICAL: Consider disqualifying or moving to long-term nurture")
    elif qualification_score < 0.5:
        recommendations.append("WARNING: Address qualification gaps before advancing to proposal")
    
    # Determine if human review required
    requires_review = 0.4 <= qualification_score <= 0.6  # Borderline scores need human judgment
    
    logger.info(
        f"[{trace_id}] Qualified opportunity {opportunity_id}: "
        f"score={qualification_score:.2f}, qualified={qualified}, framework={framework}"
    )
    
    return {
        "opportunity_id": opportunity_id,
        "qualification_score": round(qualification_score, 2),
        "qualified": qualified,
        "framework": framework,
        "strengths": strengths,
        "gaps": gaps,
        "recommendations": recommendations,
        "requires_review": requires_review,
    }


def assess_deal_risk(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assess deal risk factors (close probability, blockers, timeline).
    
    WHY: Deals don't fail randomly. Common risk factors (no champion,
    no budget, competing priorities) are predictable and addressable.
    
    CAPABILITY: Deal risk analysis and mitigation planning.
    VENDOR-NEUTRAL: Works with any deal data.
    OFFLINE: Rule-based risk assessment.
    
    Args:
        inputs: {
            "opportunity": Dict[str, Any],  # OpportunityRecord
            "risk_factors": {
                "no_champion": bool (optional),
                "no_budget_confirmed": bool (optional),
                "multiple_stakeholders": bool (optional),
                "competitive_pressure": bool (optional),
                "long_sales_cycle": bool (optional),
                "unclear_timeline": bool (optional),
            },
            "days_in_stage": int (optional),
        }
        context: {
            "profile": str,
            "trace_id": str,
        }
        
    Returns: {
        "opportunity_id": str,
        "risk_score": float,  # 0.0 (low risk) to 1.0 (high risk)
        "risk_level": str,  # "low" | "medium" | "high"
        "risk_factors": List[{
            "factor": str,
            "severity": str,  # "low" | "medium" | "high"
            "mitigation": str,
        }],
        "close_probability": float,  # 0.0 to 1.0
        "recommendations": List[str],
    }
    """
    trace_id = context.get("trace_id", "unknown")
    
    if "opportunity" not in inputs:
        raise ValueError("Required field missing: opportunity")
    
    opportunity = inputs["opportunity"]
    opportunity_id = opportunity.get("opportunity_id", "unknown")
    risk_factors_input = inputs.get("risk_factors", {})
    days_in_stage = inputs.get("days_in_stage", 0)
    
    # Calculate risk score
    risk_score = 0.0
    identified_risks = []
    
    # Risk factor: No champion
    if risk_factors_input.get("no_champion"):
        risk_score += 0.25
        identified_risks.append({
            "factor": "no_champion",
            "severity": "high",
            "mitigation": "Identify and cultivate internal champion who will advocate for solution",
        })
    
    # Risk factor: Budget not confirmed
    if risk_factors_input.get("no_budget_confirmed"):
        risk_score += 0.20
        identified_risks.append({
            "factor": "no_budget_confirmed",
            "severity": "high",
            "mitigation": "Qualify budget availability and approval process with economic buyer",
        })
    
    # Risk factor: Multiple stakeholders
    if risk_factors_input.get("multiple_stakeholders"):
        risk_score += 0.15
        identified_risks.append({
            "factor": "multiple_stakeholders",
            "severity": "medium",
            "mitigation": "Map decision-making unit and ensure all stakeholders aligned",
        })
    
    # Risk factor: Competitive pressure
    if risk_factors_input.get("competitive_pressure"):
        risk_score += 0.15
        identified_risks.append({
            "factor": "competitive_pressure",
            "severity": "medium",
            "mitigation": "Conduct competitive analysis and differentiate value proposition",
        })
    
    # Risk factor: Long sales cycle
    if risk_factors_input.get("long_sales_cycle"):
        risk_score += 0.10
        identified_risks.append({
            "factor": "long_sales_cycle",
            "severity": "low",
            "mitigation": "Establish clear milestones and maintain consistent engagement",
        })
    
    # Risk factor: Unclear timeline
    if risk_factors_input.get("unclear_timeline"):
        risk_score += 0.15
        identified_risks.append({
            "factor": "unclear_timeline",
            "severity": "medium",
            "mitigation": "Work with stakeholders to define decision timeline and deadlines",
        })
    
    # Risk factor: Stalled in stage
    stage_thresholds = {
        DealStage.DISCOVERY: 30,
        DealStage.QUALIFICATION: 21,
        DealStage.PROPOSAL: 14,
        DealStage.NEGOTIATION: 7,
    }
    
    current_stage_str = opportunity.get("stage", "discovery")
    try:
        current_stage = DealStage(current_stage_str)
        threshold = stage_thresholds.get(current_stage, 30)
        
        if days_in_stage > threshold:
            risk_score += 0.20
            identified_risks.append({
                "factor": "stalled_in_stage",
                "severity": "high",
                "mitigation": f"Deal stalled {days_in_stage} days in {current_stage.value}. Escalate or re-qualify.",
            })
    except ValueError:
        pass  # Invalid stage, skip threshold check
    
    # Clamp risk score to 0.0-1.0
    risk_score = min(risk_score, 1.0)
    
    # Determine risk level
    if risk_score < 0.3:
        risk_level = "low"
    elif risk_score < 0.6:
        risk_level = "medium"
    else:
        risk_level = "high"
    
    # Calculate close probability (inverse of risk)
    close_probability = round(1.0 - risk_score, 2)
    
    # Generate recommendations
    recommendations = []
    if risk_level == "high":
        recommendations.append("HIGH RISK: Consider pause or re-qualification before investing more resources")
    if len(identified_risks) > 3:
        recommendations.append("Multiple risk factors present. Address highest severity issues first")
    if risk_level == "low":
        recommendations.append("Low risk deal. Focus on execution and timeline management")
    
    logger.info(
        f"[{trace_id}] Assessed risk for opportunity {opportunity_id}: "
        f"risk_score={risk_score:.2f}, risk_level={risk_level}, close_probability={close_probability}"
    )
    
    return {
        "opportunity_id": opportunity_id,
        "risk_score": round(risk_score, 2),
        "risk_level": risk_level,
        "risk_factors": identified_risks,
        "close_probability": close_probability,
        "recommendations": recommendations,
    }


# Schemas for registry

SCHEMA_qualify_opportunity = {
    "name": "qualify_opportunity",
    "description": "Qualify opportunity using BANT/MEDDICC framework (advisory only)",
    "inputs": {
        "opportunity_id": {"type": "string", "required": True},
        "criteria": {"type": "object", "required": True},
        "notes": {"type": "string", "required": False},
    },
    "outputs": {
        "opportunity_id": {"type": "string"},
        "qualification_score": {"type": "number"},
        "qualified": {"type": "boolean"},
        "framework": {"type": "string"},
        "strengths": {"type": "array"},
        "gaps": {"type": "array"},
        "recommendations": {"type": "array"},
        "requires_review": {"type": "boolean"},
    },
}

SCHEMA_assess_deal_risk = {
    "name": "assess_deal_risk",
    "description": "Assess deal risk factors and close probability (advisory only)",
    "inputs": {
        "opportunity": {"type": "object", "required": True},
        "risk_factors": {"type": "object", "required": False},
        "days_in_stage": {"type": "integer", "required": False},
    },
    "outputs": {
        "opportunity_id": {"type": "string"},
        "risk_score": {"type": "number"},
        "risk_level": {"type": "string"},
        "risk_factors": {"type": "array"},
        "close_probability": {"type": "number"},
        "recommendations": {"type": "array"},
    },
}
