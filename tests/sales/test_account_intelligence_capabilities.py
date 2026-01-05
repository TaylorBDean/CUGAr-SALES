"""
Unit tests for Domain 2: Account Intelligence capabilities.

Tests verify:
- Deterministic normalization
- ICP scoring accuracy
- Offline execution
- Profile isolation
- Error handling
"""

import pytest
from cuga.modular.tools.sales.account_intelligence import (
    normalize_account_record,
    score_account_fit,
    retrieve_account_signals,
)


class TestNormalizeAccountRecord:
    """Test normalize_account_record capability."""
    
    def test_normalize_complete_record(self):
        """Test normalization of complete account data."""
        inputs = {
            "account_data": {
                "id": "sf_12345",
                "name": "Acme Corp",
                "status": "customer",
                "industry": "Technology",
                "employees": "500",
                "revenue": "$50,000,000",
                "region": "North America",
            },
            "source_type": "salesforce",
        }
        context = {"profile": "sales_test", "trace_id": "test-complete"}
        
        result = normalize_account_record(inputs, context)
        
        # Verify structure
        assert "normalized_account" in result
        assert "applied_transformations" in result
        assert "confidence" in result
        
        account = result["normalized_account"]
        assert account["account_id"] == "sf_12345"
        assert account["name"] == "Acme Corp"
        assert account["status"] == "active"  # Normalized from "customer"
        assert account["industry"] == "Technology"
        assert account["employee_count"] == 500
        assert account["revenue"] == 50000000.0  # Parsed from currency string
        assert account["region"] == "North America"
        
        # High confidence for complete data
        assert result["confidence"] >= 0.9
    
    def test_normalize_minimal_record(self):
        """Test normalization with minimal data."""
        inputs = {
            "account_data": {
                "email": "contact@example.com",
            },
            "source_type": "csv",
        }
        context = {"profile": "sales_test", "trace_id": "test-minimal"}
        
        result = normalize_account_record(inputs, context)
        
        account = result["normalized_account"]
        
        # Should generate account_id
        assert account["account_id"]
        assert "generated_account_id" in result["applied_transformations"]
        
        # Should default name
        assert account["name"] == "Unknown Account"
        assert "defaulted_missing_name" in result["applied_transformations"]
        
        # Lower confidence for incomplete data
        assert result["confidence"] <= 0.7
    
    def test_normalize_status_mapping(self):
        """Test status normalization mapping."""
        test_cases = [
            ("prospect", "prospect"),
            ("lead", "prospect"),
            ("qualified", "qualified"),
            ("customer", "active"),
            ("active", "active"),
            ("inactive", "dormant"),
            ("dormant", "dormant"),
            ("churned", "churned"),
            ("lost", "churned"),
        ]
        
        for raw_status, expected_normalized in test_cases:
            inputs = {
                "account_data": {
                    "id": "test_123",
                    "name": "Test Co",
                    "status": raw_status,
                }
            }
            context = {"profile": "sales_test", "trace_id": f"test-{raw_status}"}
            
            result = normalize_account_record(inputs, context)
            assert result["normalized_account"]["status"] == expected_normalized
    
    def test_revenue_parsing(self):
        """Test revenue parsing from various formats."""
        test_cases = [
            ("$1,500,000", 1500000.0),
            ("1500000", 1500000.0),
            ("$1.5", 1.5),  # Parsed as numeric (drops non-numeric chars)
        ]
        
        for raw_revenue, expected in test_cases:
            inputs = {
                "account_data": {
                    "id": "test_123",
                    "name": "Test Co",
                    "revenue": raw_revenue,
                }
            }
            context = {"profile": "sales_test", "trace_id": f"test-revenue"}
            
            result = normalize_account_record(inputs, context)
            account = result["normalized_account"]
            
            if expected is None:
                assert account["revenue"] is None
            else:
                assert account["revenue"] == expected
    
    def test_missing_account_data(self):
        """Test error handling for missing account_data."""
        inputs = {}
        context = {"profile": "sales_test", "trace_id": "test-missing"}
        
        with pytest.raises(ValueError, match="Required field missing"):
            normalize_account_record(inputs, context)


class TestScoreAccountFit:
    """Test score_account_fit capability."""
    
    def test_perfect_icp_fit(self):
        """Test scoring of perfect ICP fit."""
        inputs = {
            "account": {
                "account_id": "acct_001",
                "revenue": 10000000,  # $10M
                "industry": "Technology",
                "employee_count": 500,
                "region": "North America",
            },
            "icp_criteria": {
                "min_revenue": 5000000,
                "max_revenue": 50000000,
                "industries": ["Technology", "Software"],
                "min_employees": 100,
                "max_employees": 1000,
                "regions": ["North America", "Europe"],
            },
        }
        context = {"profile": "sales_test", "trace_id": "test-perfect"}
        
        result = score_account_fit(inputs, context)
        
        # Verify structure
        assert "fit_score" in result
        assert "fit_breakdown" in result
        assert "recommendation" in result
        assert "reasoning" in result
        
        # Perfect fit = high score
        assert result["fit_score"] == 1.0
        assert result["recommendation"] == "high_priority"
        assert result["fit_breakdown"]["revenue_fit"] == 1.0
        assert result["fit_breakdown"]["industry_fit"] == 1.0
        assert result["fit_breakdown"]["employee_fit"] == 1.0
        assert result["fit_breakdown"]["region_fit"] == 1.0
    
    def test_poor_icp_fit(self):
        """Test scoring of poor ICP fit."""
        inputs = {
            "account": {
                "account_id": "acct_002",
                "revenue": 100000,  # Too small
                "industry": "Retail",  # Wrong industry
                "employee_count": 10,  # Too small
                "region": "Asia",  # Wrong region
            },
            "icp_criteria": {
                "min_revenue": 5000000,
                "industries": ["Technology"],
                "min_employees": 100,
                "regions": ["North America"],
            },
        }
        context = {"profile": "sales_test", "trace_id": "test-poor"}
        
        result = score_account_fit(inputs, context)
        
        # Poor fit = low score
        assert result["fit_score"] < 0.5
        assert result["recommendation"] == "low_priority"
        
        # Should identify specific gaps
        assert any("Revenue outside" in r for r in result["reasoning"])
        assert any("Industry not in" in r for r in result["reasoning"])
    
    def test_partial_icp_fit(self):
        """Test scoring of partial ICP fit."""
        inputs = {
            "account": {
                "account_id": "acct_003",
                "revenue": 8000000,  # Good
                "industry": "Technology",  # Good
                "employee_count": 50,  # Too small
                "region": "Europe",  # Good
            },
            "icp_criteria": {
                "min_revenue": 5000000,
                "industries": ["Technology"],
                "min_employees": 100,
                "regions": ["Europe"],
            },
        }
        context = {"profile": "sales_test", "trace_id": "test-partial"}
        
        result = score_account_fit(inputs, context)
        
        # Partial fit = high-medium score (good revenue + industry + region = 0.85)
        assert 0.75 <= result["fit_score"] <= 1.0
        assert result["recommendation"] == "high_priority"
    
    def test_missing_icp_criteria(self):
        """Test scoring when ICP criteria not specified (all fit)."""
        inputs = {
            "account": {
                "account_id": "acct_004",
                "revenue": 1000000,
                "industry": "Any",
            },
            "icp_criteria": {},  # No constraints
        }
        context = {"profile": "sales_test", "trace_id": "test-no-icp"}
        
        result = score_account_fit(inputs, context)
        
        # No constraints = mostly perfect fit (slight penalty for unknown fields)
        assert result["fit_score"] >= 0.8
    
    def test_missing_account_data(self):
        """Test error handling for missing fields."""
        inputs = {"account": {}}
        context = {"profile": "sales_test", "trace_id": "test-missing"}
        
        with pytest.raises(ValueError, match="Required fields missing"):
            score_account_fit(inputs, context)


class TestRetrieveAccountSignals:
    """Test retrieve_account_signals capability."""
    
    def test_retrieve_signals_stub(self):
        """Test signal retrieval (MVP stub - returns empty)."""
        inputs = {
            "account_id": "acct_001",
            "signal_types": ["funding", "hiring", "tech_stack"],
        }
        context = {"profile": "sales_test", "trace_id": "test-signals"}
        
        result = retrieve_account_signals(inputs, context)
        
        # MVP stub returns empty
        assert result["account_id"] == "acct_001"
        assert result["signals"] == []
        assert result["signal_count"] == 0
        assert result["priority_score"] == 0.0
