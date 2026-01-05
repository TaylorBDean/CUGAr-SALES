"""
Unit tests for Domain 5: Qualification & Deal Progression capabilities.

Tests verify:
- BANT/MEDDICC scoring accuracy
- Risk assessment logic
- Deterministic behavior
- Offline execution
- Error handling
"""

import pytest
from cuga.modular.tools.sales.qualification import (
    qualify_opportunity,
    assess_deal_risk,
)


class TestQualifyOpportunity:
    """Test qualify_opportunity capability."""
    
    def test_qualify_full_bant(self):
        """Test qualification with full BANT confirmation."""
        inputs = {
            "opportunity_id": "opp_001",
            "criteria": {
                "budget": True,
                "authority": True,
                "need": True,
                "timing": True,
            },
        }
        context = {"profile": "sales_test", "trace_id": "test-full-bant"}
        
        result = qualify_opportunity(inputs, context)
        
        # Verify structure
        assert "opportunity_id" in result
        assert "qualification_score" in result
        assert "qualified" in result
        assert "framework" in result
        assert "strengths" in result
        assert "gaps" in result
        assert "recommendations" in result
        assert "requires_review" in result
        
        # Full BANT = 0.7 score (70% weight on BANT, 30% on empty MEDDICC)
        assert 0.7 <= result["qualification_score"] <= 0.71
        assert result["qualified"] is True
        assert result["framework"] == "BANT"
        assert len(result["strengths"]) == 4
        assert len(result["gaps"]) == 0
    
    def test_qualify_partial_bant(self):
        """Test qualification with partial BANT."""
        inputs = {
            "opportunity_id": "opp_002",
            "criteria": {
                "budget": True,
                "authority": False,
                "need": True,
                "timing": False,
            },
        }
        context = {"profile": "sales_test", "trace_id": "test-partial-bant"}
        
        result = qualify_opportunity(inputs, context)
        
        # Partial BANT = 0.35 score (2/4 * 0.7 = 0.35)
        assert 0.35 <= result["qualification_score"] <= 0.36
        assert result["qualified"] is False  # < 0.5 threshold
        assert len(result["strengths"]) == 2
        assert len(result["gaps"]) == 2
        
        # Should have recommendations for gaps
        assert len(result["recommendations"]) > 0
        assert any("authority" in r.lower() for r in result["recommendations"])
    
    def test_qualify_no_bant(self):
        """Test qualification with no BANT confirmation."""
        inputs = {
            "opportunity_id": "opp_003",
            "criteria": {
                "budget": False,
                "authority": False,
                "need": False,
                "timing": False,
            },
        }
        context = {"profile": "sales_test", "trace_id": "test-no-bant"}
        
        result = qualify_opportunity(inputs, context)
        
        # No BANT = 0.0 score
        assert result["qualification_score"] == 0.0
        assert result["qualified"] is False
        assert len(result["strengths"]) == 0
        assert len(result["gaps"]) == 4
        
        # Should recommend disqualification
        assert any("CRITICAL" in r or "disqualifying" in r for r in result["recommendations"])
    
    def test_qualify_meddicc(self):
        """Test qualification with MEDDICC framework."""
        inputs = {
            "opportunity_id": "opp_004",
            "criteria": {
                # BANT
                "budget": True,
                "authority": True,
                "need": True,
                "timing": True,
                # MEDDICC
                "metrics": True,
                "economic_buyer": True,
                "decision_criteria": True,
                "decision_process": True,
                "identify_pain": True,
                "champion": True,
                "competition": True,
            },
        }
        context = {"profile": "sales_test", "trace_id": "test-meddicc"}
        
        result = qualify_opportunity(inputs, context)
        
        # Full BANT + MEDDICC = 1.0 score
        assert result["qualification_score"] == 1.0
        assert result["framework"] == "MEDDICC"
        
        # Should have MEDDICC-specific strengths
        meddicc_strengths = [s for s in result["strengths"] if "MEDDICC" in s]
        assert len(meddicc_strengths) == 7
    
    def test_qualify_borderline_score(self):
        """Test that borderline scores require review."""
        inputs = {
            "opportunity_id": "opp_005",
            "criteria": {
                "budget": True,
                "authority": True,
                "need": False,
                "timing": False,
            },
        }
        context = {"profile": "sales_test", "trace_id": "test-borderline"}
        
        result = qualify_opportunity(inputs, context)
        
        # 0.35 score is borderline
        assert 0.35 <= result["qualification_score"] <= 0.36
        assert result["qualified"] is False  # < 0.5 threshold
    
    def test_missing_required_fields(self):
        """Test error handling for missing fields."""
        inputs = {"opportunity_id": "opp_006"}  # Missing criteria
        context = {"profile": "sales_test", "trace_id": "test-missing"}
        
        with pytest.raises(ValueError, match="Required fields missing"):
            qualify_opportunity(inputs, context)


class TestAssessDealRisk:
    """Test assess_deal_risk capability."""
    
    def test_assess_low_risk_deal(self):
        """Test assessment of low-risk deal."""
        inputs = {
            "opportunity": {
                "opportunity_id": "opp_001",
                "stage": "proposal",
                "amount": 50000,
            },
            "risk_factors": {
                "no_champion": False,
                "no_budget_confirmed": False,
                "multiple_stakeholders": False,
                "competitive_pressure": False,
                "long_sales_cycle": False,
                "unclear_timeline": False,
            },
            "days_in_stage": 5,
        }
        context = {"profile": "sales_test", "trace_id": "test-low-risk"}
        
        result = assess_deal_risk(inputs, context)
        
        # Verify structure
        assert "opportunity_id" in result
        assert "risk_score" in result
        assert "risk_level" in result
        assert "risk_factors" in result
        assert "close_probability" in result
        assert "recommendations" in result
        
        # Low risk
        assert result["risk_score"] < 0.3
        assert result["risk_level"] == "low"
        assert result["close_probability"] > 0.7
        assert len(result["risk_factors"]) == 0
    
    def test_assess_high_risk_deal(self):
        """Test assessment of high-risk deal."""
        inputs = {
            "opportunity": {
                "opportunity_id": "opp_002",
                "stage": "qualification",
                "amount": 100000,
            },
            "risk_factors": {
                "no_champion": True,  # +0.25
                "no_budget_confirmed": True,  # +0.20
                "multiple_stakeholders": True,  # +0.15
                "competitive_pressure": True,  # +0.15
                "unclear_timeline": True,  # +0.15
            },
            "days_in_stage": 45,  # Stalled: +0.20
        }
        context = {"profile": "sales_test", "trace_id": "test-high-risk"}
        
        result = assess_deal_risk(inputs, context)
        
        # High risk (clamped at 1.0)
        assert result["risk_score"] >= 0.6
        assert result["risk_level"] == "high"
        assert result["close_probability"] <= 0.4
        assert len(result["risk_factors"]) > 3
        
        # Should recommend pause/re-qualification
        assert any("HIGH RISK" in r for r in result["recommendations"])
    
    def test_assess_medium_risk_deal(self):
        """Test assessment of medium-risk deal."""
        inputs = {
            "opportunity": {
                "opportunity_id": "opp_003",
                "stage": "proposal",
                "amount": 75000,
            },
            "risk_factors": {
                "multiple_stakeholders": True,
                "competitive_pressure": True,
            },
            "days_in_stage": 10,
        }
        context = {"profile": "sales_test", "trace_id": "test-medium-risk"}
        
        result = assess_deal_risk(inputs, context)
        
        # Medium risk (0.15 + 0.15 = 0.3)
        assert 0.3 <= result["risk_score"] < 0.6
        assert result["risk_level"] == "medium"
    
    def test_stalled_deal_detection(self):
        """Test detection of stalled deals."""
        inputs = {
            "opportunity": {
                "opportunity_id": "opp_004",
                "stage": "discovery",  # Threshold: 30 days
                "amount": 25000,
            },
            "risk_factors": {},
            "days_in_stage": 45,  # Over threshold
        }
        context = {"profile": "sales_test", "trace_id": "test-stalled"}
        
        result = assess_deal_risk(inputs, context)
        
        # Should identify stalled risk
        stalled_risks = [r for r in result["risk_factors"] if r["factor"] == "stalled_in_stage"]
        assert len(stalled_risks) == 1
        assert stalled_risks[0]["severity"] == "high"
    
    def test_risk_factor_severity(self):
        """Test risk factor severity classification."""
        inputs = {
            "opportunity": {
                "opportunity_id": "opp_005",
                "stage": "proposal",
            },
            "risk_factors": {
                "no_champion": True,  # High severity
                "no_budget_confirmed": True,  # High severity
                "long_sales_cycle": True,  # Low severity
            },
        }
        context = {"profile": "sales_test", "trace_id": "test-severity"}
        
        result = assess_deal_risk(inputs, context)
        
        # Verify severity classifications
        high_severity = [r for r in result["risk_factors"] if r["severity"] == "high"]
        low_severity = [r for r in result["risk_factors"] if r["severity"] == "low"]
        
        assert len(high_severity) == 2  # no_champion, no_budget_confirmed
        assert len(low_severity) == 1  # long_sales_cycle
    
    def test_missing_opportunity_field(self):
        """Test error handling for missing opportunity."""
        inputs = {}
        context = {"profile": "sales_test", "trace_id": "test-missing"}
        
        with pytest.raises(ValueError, match="Required field missing"):
            assess_deal_risk(inputs, context)
    
    def test_determinism(self):
        """Test deterministic behavior."""
        inputs = {
            "opportunity": {
                "opportunity_id": "opp_006",
                "stage": "proposal",
            },
            "risk_factors": {
                "competitive_pressure": True,
            },
        }
        context = {"profile": "sales_test", "trace_id": "test-determ"}
        
        result1 = assess_deal_risk(inputs, context)
        result2 = assess_deal_risk(inputs, context)
        
        # Same inputs = same outputs
        assert result1["risk_score"] == result2["risk_score"]
        assert result1["risk_level"] == result2["risk_level"]
        assert len(result1["risk_factors"]) == len(result2["risk_factors"])
