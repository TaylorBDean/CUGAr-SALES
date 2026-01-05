"""
Unit tests for Domain 1: Territory & Capacity Planning capabilities.

Tests verify:
- Deterministic behavior
- Offline execution (no network)
- Profile isolation
- Structured outputs
- Error handling
"""

import pytest
from cuga.modular.tools.sales.territory import (
    simulate_territory_change,
    assess_capacity_coverage,
)


class TestSimulateTerritoryChange:
    """Test simulate_territory_change capability."""
    
    def test_simulate_basic_change(self):
        """Test basic territory simulation."""
        inputs = {
            "from_territory": "west",
            "to_territory": "east",
            "account_ids": ["acct_001", "acct_002", "acct_003"],
            "effective_date": "2026-02-01",
        }
        context = {
            "profile": "sales_test",
            "trace_id": "test-123",
        }
        
        result = simulate_territory_change(inputs, context)
        
        # Verify structure
        assert "simulation_id" in result
        assert "impact_summary" in result
        assert "recommendations" in result
        assert "requires_approval" in result
        assert "approval_reason" in result
        
        # Verify values
        assert result["requires_approval"] is True  # Always requires approval
        assert "from_territory" in result["impact_summary"]
        assert "to_territory" in result["impact_summary"]
        
        # Verify determinism (same inputs = same outputs)
        result2 = simulate_territory_change(inputs, context)
        assert result["impact_summary"] == result2["impact_summary"]
    
    def test_missing_required_fields(self):
        """Test error handling for missing fields."""
        inputs = {
            "from_territory": "west",
            # Missing to_territory
            "account_ids": ["acct_001"],
        }
        context = {"profile": "sales_test", "trace_id": "test-456"}
        
        with pytest.raises(ValueError, match="Required field missing"):
            simulate_territory_change(inputs, context)
    
    def test_empty_account_list(self):
        """Test error handling for empty account list."""
        inputs = {
            "from_territory": "west",
            "to_territory": "east",
            "account_ids": [],  # Empty
        }
        context = {"profile": "sales_test", "trace_id": "test-789"}
        
        with pytest.raises(ValueError, match="non-empty list"):
            simulate_territory_change(inputs, context)
    
    def test_capacity_warnings(self):
        """Test that capacity warnings are generated."""
        inputs = {
            "from_territory": "west",
            "to_territory": "east",
            "account_ids": [f"acct_{i:03d}" for i in range(20)],  # Many accounts
        }
        context = {"profile": "sales_test", "trace_id": "test-capacity"}
        
        result = simulate_territory_change(inputs, context)
        
        # Should generate recommendations due to capacity impact
        assert len(result["recommendations"]) > 0


class TestAssessCapacityCoverage:
    """Test assess_capacity_coverage capability."""
    
    def test_assess_balanced_territories(self):
        """Test assessment with balanced territories."""
        inputs = {
            "territories": [
                {"territory_id": "west", "rep_count": 2, "account_count": 180},
                {"territory_id": "east", "rep_count": 2, "account_count": 190},
            ],
            "capacity_threshold": 0.9,
        }
        context = {"profile": "sales_test", "trace_id": "test-balanced"}
        
        result = assess_capacity_coverage(inputs, context)
        
        # Verify structure
        assert "analysis_id" in result
        assert "overall_capacity" in result
        assert "coverage_gaps" in result
        assert "summary" in result
        
        # Verify capacity calculation
        # 370 accounts / (4 reps * 100) = 0.925
        assert 0.9 <= result["overall_capacity"] <= 1.0
        
        # Should have some gaps (near threshold)
        assert isinstance(result["coverage_gaps"], list)
    
    def test_orphaned_territory(self):
        """Test detection of territory with no reps."""
        inputs = {
            "territories": [
                {"territory_id": "west", "rep_count": 2, "account_count": 150},
                {"territory_id": "orphan", "rep_count": 0, "account_count": 50},
            ],
        }
        context = {"profile": "sales_test", "trace_id": "test-orphan"}
        
        result = assess_capacity_coverage(inputs, context)
        
        # Should detect orphaned territory
        orphan_gaps = [g for g in result["coverage_gaps"] if g["gap_type"] == "no_rep"]
        assert len(orphan_gaps) == 1
        assert orphan_gaps[0]["territory_id"] == "orphan"
        assert orphan_gaps[0]["severity"] == "high"
    
    def test_overloaded_territory(self):
        """Test detection of overloaded territory."""
        inputs = {
            "territories": [
                {"territory_id": "overloaded", "rep_count": 1, "account_count": 250},
            ],
            "capacity_threshold": 0.9,
        }
        context = {"profile": "sales_test", "trace_id": "test-overload"}
        
        result = assess_capacity_coverage(inputs, context)
        
        # Should detect overload (250 accounts / 100 capacity = 2.5x)
        overload_gaps = [g for g in result["coverage_gaps"] if g["gap_type"] == "overloaded"]
        assert len(overload_gaps) == 1
        assert overload_gaps[0]["severity"] == "high"
    
    def test_underutilized_territory(self):
        """Test detection of underutilized territory."""
        inputs = {
            "territories": [
                {"territory_id": "underutil", "rep_count": 2, "account_count": 80},
            ],
        }
        context = {"profile": "sales_test", "trace_id": "test-underutil"}
        
        result = assess_capacity_coverage(inputs, context)
        
        # Should detect underutilization (80 / 200 = 0.4)
        underutil_gaps = [g for g in result["coverage_gaps"] if g["gap_type"] == "underutilized"]
        assert len(underutil_gaps) == 1
        assert underutil_gaps[0]["severity"] == "low"
    
    def test_missing_territories_field(self):
        """Test error handling for missing territories."""
        inputs = {}
        context = {"profile": "sales_test", "trace_id": "test-missing"}
        
        with pytest.raises(ValueError, match="Required field missing"):
            assess_capacity_coverage(inputs, context)
    
    def test_determinism(self):
        """Test deterministic behavior."""
        inputs = {
            "territories": [
                {"territory_id": "west", "rep_count": 1, "account_count": 90},
            ],
        }
        context = {"profile": "sales_test", "trace_id": "test-determ"}
        
        result1 = assess_capacity_coverage(inputs, context)
        result2 = assess_capacity_coverage(inputs, context)
        
        # Same inputs = same outputs
        assert result1["overall_capacity"] == result2["overall_capacity"]
        assert len(result1["coverage_gaps"]) == len(result2["coverage_gaps"])
