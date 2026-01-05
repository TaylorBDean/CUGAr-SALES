"""
Tests for Domain 4: Intelligence & Optimization capabilities.

Coverage:
- analyze_win_loss_patterns: Historical deal analysis, pattern extraction, ICP recommendations
- extract_buyer_personas: Persona identification from won deals
"""

import pytest
from cuga.modular.tools.sales.intelligence import (
    analyze_win_loss_patterns,
    extract_buyer_personas,
    DealOutcome,
    LossReason,
    WinFactor,
)


# Test Context
CONTEXT = {"trace_id": "test-trace-123", "profile": "sales"}


class TestAnalyzeWinLossPatterns:
    """Test win/loss pattern analysis and ICP recommendations."""
    
    def test_basic_win_loss_analysis(self):
        """Should calculate win rate and summary statistics."""
        deals = [
            {
                "deal_id": "001",
                "outcome": "won",
                "account": {"name": "Acme", "industry": "Technology", "revenue": 50_000_000},
                "deal_value": 100_000,
                "sales_cycle_days": 45,
                "qualification_score": 0.85,
            },
            {
                "deal_id": "002",
                "outcome": "won",
                "account": {"name": "TechCorp", "industry": "Technology", "revenue": 75_000_000},
                "deal_value": 150_000,
                "sales_cycle_days": 30,
                "qualification_score": 0.90,
            },
            {
                "deal_id": "003",
                "outcome": "lost",
                "account": {"name": "OldCo", "industry": "Manufacturing", "revenue": 20_000_000},
                "deal_value": 50_000,
                "sales_cycle_days": 60,
                "qualification_score": 0.50,
                "loss_reason": "price",
            },
        ]
        
        result = analyze_win_loss_patterns(
            inputs={"deals": deals, "min_deals_for_pattern": 2},
            context=CONTEXT,
        )
        
        assert result["summary"]["total_deals"] == 3
        assert result["summary"]["won_count"] == 2
        assert result["summary"]["lost_count"] == 1
        assert result["summary"]["win_rate"] == 0.67  # 2/3 = 0.67
        assert result["summary"]["avg_deal_value_won"] == 125_000.0  # (100k + 150k) / 2
        assert result["summary"]["avg_sales_cycle_won"] == 38  # (45 + 30) / 2
    
    def test_industry_pattern_detection(self):
        """Should identify high-performing industries."""
        deals = []
        
        # Technology: 4 won, 1 lost (80% win rate)
        for i in range(4):
            deals.append({
                "deal_id": f"tech-{i}",
                "outcome": "won",
                "account": {"name": f"Tech{i}", "industry": "Technology", "revenue": 50_000_000},
                "deal_value": 100_000,
                "sales_cycle_days": 45,
            })
        deals.append({
            "deal_id": "tech-lost",
            "outcome": "lost",
            "account": {"name": "TechLost", "industry": "Technology", "revenue": 30_000_000},
            "deal_value": 80_000,
            "sales_cycle_days": 60,
            "loss_reason": "timing",
        })
        
        # Manufacturing: 1 won, 4 lost (20% win rate)
        deals.append({
            "deal_id": "mfg-won",
            "outcome": "won",
            "account": {"name": "MfgWon", "industry": "Manufacturing", "revenue": 40_000_000},
            "deal_value": 90_000,
            "sales_cycle_days": 50,
        })
        for i in range(4):
            deals.append({
                "deal_id": f"mfg-{i}",
                "outcome": "lost",
                "account": {"name": f"Mfg{i}", "industry": "Manufacturing", "revenue": 25_000_000},
                "deal_value": 70_000,
                "sales_cycle_days": 70,
                "loss_reason": "poor_fit",
            })
        
        result = analyze_win_loss_patterns(
            inputs={"deals": deals, "min_deals_for_pattern": 3},
            context=CONTEXT,
        )
        
        # Find Technology pattern
        tech_pattern = next((p for p in result["win_patterns"] if p["pattern_value"] == "Technology"), None)
        assert tech_pattern is not None
        assert tech_pattern["win_rate"] == 0.8  # 4/5
        assert tech_pattern["deal_count"] == 5
        assert "Strong fit" in tech_pattern["recommendation"]
        
        # Find Manufacturing pattern
        mfg_pattern = next((p for p in result["win_patterns"] if p["pattern_value"] == "Manufacturing"), None)
        assert mfg_pattern is not None
        assert mfg_pattern["win_rate"] == 0.2  # 1/5
        assert mfg_pattern["deal_count"] == 5
        assert "Poor fit" in mfg_pattern["recommendation"]
    
    def test_revenue_range_pattern_detection(self):
        """Should identify optimal revenue ranges."""
        deals = []
        
        # 10-50M range: 3 won, 1 lost (75% win rate)
        for i in range(3):
            deals.append({
                "deal_id": f"mid-{i}",
                "outcome": "won",
                "account": {"name": f"Mid{i}", "industry": "Technology", "revenue": 30_000_000 + i * 5_000_000},
                "deal_value": 100_000,
                "sales_cycle_days": 40,
            })
        deals.append({
            "deal_id": "mid-lost",
            "outcome": "lost",
            "account": {"name": "MidLost", "industry": "Technology", "revenue": 35_000_000},
            "deal_value": 90_000,
            "sales_cycle_days": 50,
            "loss_reason": "price",
        })
        
        # 0-10M range: 1 won, 3 lost (25% win rate)
        deals.append({
            "deal_id": "small-won",
            "outcome": "won",
            "account": {"name": "SmallWon", "industry": "Technology", "revenue": 5_000_000},
            "deal_value": 50_000,
            "sales_cycle_days": 35,
        })
        for i in range(3):
            deals.append({
                "deal_id": f"small-{i}",
                "outcome": "lost",
                "account": {"name": f"Small{i}", "industry": "Technology", "revenue": 3_000_000 + i * 1_000_000},
                "deal_value": 40_000,
                "sales_cycle_days": 55,
                "loss_reason": "no_budget",
            })
        
        result = analyze_win_loss_patterns(
            inputs={"deals": deals, "min_deals_for_pattern": 3},
            context=CONTEXT,
        )
        
        # Find 10-50M pattern
        mid_pattern = next((p for p in result["win_patterns"] if p["pattern_value"] == "10-50M"), None)
        assert mid_pattern is not None
        assert mid_pattern["win_rate"] == 0.75  # 3/4
        assert mid_pattern["deal_count"] == 4
        assert "Sweet spot" in mid_pattern["recommendation"]
        
        # Find 0-10M pattern
        small_pattern = next((p for p in result["win_patterns"] if p["pattern_value"] == "0-10M"), None)
        assert small_pattern is not None
        assert small_pattern["win_rate"] == 0.25  # 1/4
        assert small_pattern["deal_count"] == 4
        assert "Poor fit" in small_pattern["recommendation"]
    
    def test_loss_reason_analysis(self):
        """Should identify most common loss reasons."""
        deals = [
            {"deal_id": "001", "outcome": "lost", "account": {"name": "A", "industry": "Tech", "revenue": 50_000_000}, "deal_value": 100_000, "sales_cycle_days": 45, "loss_reason": "price"},
            {"deal_id": "002", "outcome": "lost", "account": {"name": "B", "industry": "Tech", "revenue": 60_000_000}, "deal_value": 110_000, "sales_cycle_days": 50, "loss_reason": "price"},
            {"deal_id": "003", "outcome": "lost", "account": {"name": "C", "industry": "Tech", "revenue": 55_000_000}, "deal_value": 105_000, "sales_cycle_days": 48, "loss_reason": "price"},
            {"deal_id": "004", "outcome": "lost", "account": {"name": "D", "industry": "Mfg", "revenue": 30_000_000}, "deal_value": 80_000, "sales_cycle_days": 60, "loss_reason": "timing"},
            {"deal_id": "005", "outcome": "lost", "account": {"name": "E", "industry": "Mfg", "revenue": 35_000_000}, "deal_value": 85_000, "sales_cycle_days": 65, "loss_reason": "timing"},
            # Add one won deal to make analysis valid
            {"deal_id": "006", "outcome": "won", "account": {"name": "F", "industry": "Tech", "revenue": 70_000_000}, "deal_value": 120_000, "sales_cycle_days": 40},
        ]
        
        result = analyze_win_loss_patterns(
            inputs={"deals": deals, "min_deals_for_pattern": 2},
            context=CONTEXT,
        )
        
        # Should identify price as most common loss reason
        loss_patterns = result["loss_patterns"]
        assert len(loss_patterns) > 0
        
        price_pattern = next((p for p in loss_patterns if p["loss_reason"] == "price"), None)
        assert price_pattern is not None
        assert price_pattern["count"] == 3
        assert price_pattern["percentage"] == 0.6  # 3/5 losses
        assert "pricing" in price_pattern["recommendation"].lower()
        
        timing_pattern = next((p for p in loss_patterns if p["loss_reason"] == "timing"), None)
        assert timing_pattern is not None
        assert timing_pattern["count"] == 2
        assert timing_pattern["percentage"] == 0.4  # 2/5 losses
    
    def test_icp_recommendations(self):
        """Should generate ICP recommendations based on win patterns."""
        deals = []
        
        # High win rate in Technology + 10-50M revenue
        for i in range(5):
            deals.append({
                "deal_id": f"tech-{i}",
                "outcome": "won",
                "account": {"name": f"Tech{i}", "industry": "Technology", "revenue": 30_000_000 + i * 3_000_000},
                "deal_value": 100_000,
                "sales_cycle_days": 40,
            })
        
        # Low win rate in Manufacturing + 0-10M revenue
        for i in range(3):
            deals.append({
                "deal_id": f"mfg-{i}",
                "outcome": "lost",
                "account": {"name": f"Mfg{i}", "industry": "Manufacturing", "revenue": 5_000_000 + i * 1_000_000},
                "deal_value": 50_000,
                "sales_cycle_days": 60,
                "loss_reason": "poor_fit",
            })
        
        result = analyze_win_loss_patterns(
            inputs={"deals": deals, "min_deals_for_pattern": 3},
            context=CONTEXT,
        )
        
        # Should recommend Technology as target industry
        icp_recs = result["icp_recommendations"]
        assert len(icp_recs) > 0
        
        industry_rec = next((r for r in icp_recs if r["attribute"] == "target_industries"), None)
        assert industry_rec is not None
        assert "Technology" in industry_rec["recommended"]
        assert "win rate" in industry_rec["rationale"].lower()
        assert industry_rec["confidence"] > 0.0
        
        revenue_rec = next((r for r in icp_recs if r["attribute"] == "revenue_range"), None)
        assert revenue_rec is not None
        assert "10-50M" in revenue_rec["recommended"]
    
    def test_qualification_accuracy_analysis(self):
        """Should analyze qualification score accuracy."""
        deals = [
            # High score, won (true positive)
            {"deal_id": "001", "outcome": "won", "account": {"name": "A", "industry": "Tech", "revenue": 50_000_000}, "deal_value": 100_000, "sales_cycle_days": 40, "qualification_score": 0.85},
            {"deal_id": "002", "outcome": "won", "account": {"name": "B", "industry": "Tech", "revenue": 60_000_000}, "deal_value": 110_000, "sales_cycle_days": 35, "qualification_score": 0.90},
            
            # Low score, lost (true negative)
            {"deal_id": "003", "outcome": "lost", "account": {"name": "C", "industry": "Mfg", "revenue": 20_000_000}, "deal_value": 50_000, "sales_cycle_days": 60, "qualification_score": 0.40, "loss_reason": "poor_fit"},
            {"deal_id": "004", "outcome": "lost", "account": {"name": "D", "industry": "Mfg", "revenue": 25_000_000}, "deal_value": 55_000, "sales_cycle_days": 65, "qualification_score": 0.45, "loss_reason": "no_budget"},
            
            # High score, lost (false positive)
            {"deal_id": "005", "outcome": "lost", "account": {"name": "E", "industry": "Tech", "revenue": 55_000_000}, "deal_value": 105_000, "sales_cycle_days": 50, "qualification_score": 0.80, "loss_reason": "timing"},
            
            # Low score, won (false negative)
            {"deal_id": "006", "outcome": "won", "account": {"name": "F", "industry": "Tech", "revenue": 45_000_000}, "deal_value": 95_000, "sales_cycle_days": 45, "qualification_score": 0.55},
        ]
        
        result = analyze_win_loss_patterns(
            inputs={"deals": deals, "min_deals_for_pattern": 2},
            context=CONTEXT,
        )
        
        insights = result["qualification_insights"]
        assert "optimal_threshold" in insights
        assert 0.5 <= insights["optimal_threshold"] <= 0.9
        assert insights["false_positives"] >= 0  # High score but lost
        assert insights["false_negatives"] >= 0  # Low score but won
        assert 0.0 <= insights["accuracy"] <= 1.0
    
    def test_empty_deals_error(self):
        """Should return error for empty deal list."""
        result = analyze_win_loss_patterns(
            inputs={"deals": []},
            context=CONTEXT,
        )
        
        assert result["status"] == "error"
        assert "no deals" in result["error"].lower()
    
    def test_no_won_or_lost_deals(self):
        """Should return error when only active deals provided."""
        deals = [
            {"deal_id": "001", "outcome": "active", "account": {"name": "A"}, "deal_value": 100_000, "sales_cycle_days": 30},
        ]
        
        result = analyze_win_loss_patterns(
            inputs={"deals": deals},
            context=CONTEXT,
        )
        
        assert result["status"] == "error"
        assert "no won or lost" in result["error"].lower()
    
    def test_min_deals_for_pattern_threshold(self):
        """Should only identify patterns meeting minimum threshold."""
        deals = [
            # Technology: 2 won (below threshold of 3)
            {"deal_id": "001", "outcome": "won", "account": {"name": "A", "industry": "Technology", "revenue": 50_000_000}, "deal_value": 100_000, "sales_cycle_days": 40},
            {"deal_id": "002", "outcome": "won", "account": {"name": "B", "industry": "Technology", "revenue": 60_000_000}, "deal_value": 110_000, "sales_cycle_days": 35},
            
            # Manufacturing: 3 lost (meets threshold)
            {"deal_id": "003", "outcome": "lost", "account": {"name": "C", "industry": "Manufacturing", "revenue": 30_000_000}, "deal_value": 80_000, "sales_cycle_days": 60, "loss_reason": "price"},
            {"deal_id": "004", "outcome": "lost", "account": {"name": "D", "industry": "Manufacturing", "revenue": 35_000_000}, "deal_value": 85_000, "sales_cycle_days": 65, "loss_reason": "timing"},
            {"deal_id": "005", "outcome": "lost", "account": {"name": "E", "industry": "Manufacturing", "revenue": 40_000_000}, "deal_value": 90_000, "sales_cycle_days": 70, "loss_reason": "competitor"},
        ]
        
        result = analyze_win_loss_patterns(
            inputs={"deals": deals, "min_deals_for_pattern": 3},
            context=CONTEXT,
        )
        
        # Technology should not appear (only 2 deals)
        tech_pattern = next((p for p in result["win_patterns"] if p["pattern_value"] == "Technology"), None)
        assert tech_pattern is None
        
        # Manufacturing should appear (3 deals)
        mfg_pattern = next((p for p in result["win_patterns"] if p["pattern_value"] == "Manufacturing"), None)
        assert mfg_pattern is not None
        assert mfg_pattern["deal_count"] == 3


class TestExtractBuyerPersonas:
    """Test buyer persona extraction from won deals."""
    
    def test_basic_persona_extraction(self):
        """Should identify common buyer personas."""
        deals = [
            {
                "deal_id": "001",
                "outcome": "won",
                "contacts": [
                    {"title": "VP Sales", "department": "Sales", "role": "champion", "seniority": "VP"},
                    {"title": "CFO", "department": "Finance", "role": "decision_maker", "seniority": "C-level"},
                ]
            },
            {
                "deal_id": "002",
                "outcome": "won",
                "contacts": [
                    {"title": "VP Sales", "department": "Sales", "role": "champion", "seniority": "VP"},
                    {"title": "CEO", "department": "Executive", "role": "decision_maker", "seniority": "C-level"},
                ]
            },
            {
                "deal_id": "003",
                "outcome": "won",
                "contacts": [
                    {"title": "VP Sales", "department": "Sales", "role": "champion", "seniority": "VP"},
                    {"title": "CFO", "department": "Finance", "role": "decision_maker", "seniority": "C-level"},
                ]
            },
        ]
        
        result = extract_buyer_personas(
            inputs={"deals": deals, "min_occurrences": 3},
            context=CONTEXT,
        )
        
        # VP Sales should be identified (appears 3 times)
        personas = result["personas"]
        vp_sales = next((p for p in personas if p["title_pattern"] == "VP Sales"), None)
        assert vp_sales is not None
        assert vp_sales["occurrence_count"] == 3
        assert "champion" in vp_sales["typical_roles"]
        assert "champion" in vp_sales["recommendation"].lower()
    
    def test_decision_maker_patterns(self):
        """Should identify most common decision maker titles."""
        deals = [
            {
                "deal_id": "001",
                "outcome": "won",
                "contacts": [
                    {"title": "CFO", "department": "Finance", "role": "decision_maker", "seniority": "C-level"},
                ]
            },
            {
                "deal_id": "002",
                "outcome": "won",
                "contacts": [
                    {"title": "CFO", "department": "Finance", "role": "decision_maker", "seniority": "C-level"},
                ]
            },
            {
                "deal_id": "003",
                "outcome": "won",
                "contacts": [
                    {"title": "CEO", "department": "Executive", "role": "decision_maker", "seniority": "C-level"},
                ]
            },
        ]
        
        result = extract_buyer_personas(
            inputs={"deals": deals, "min_occurrences": 2},
            context=CONTEXT,
        )
        
        dm_patterns = result["decision_maker_patterns"]
        assert dm_patterns["most_common_title"] == "CFO"  # Appears 2/3 times
        assert dm_patterns["most_common_seniority"] == "C-level"
        assert "C-level" in dm_patterns["recommendation"]
    
    def test_empty_deals_error(self):
        """Should return error for empty deal list."""
        result = extract_buyer_personas(
            inputs={"deals": []},
            context=CONTEXT,
        )
        
        assert result["status"] == "error"
        assert "no deals" in result["error"].lower()
    
    def test_no_won_deals_error(self):
        """Should return error when no won deals provided."""
        deals = [
            {"deal_id": "001", "outcome": "lost", "contacts": []},
        ]
        
        result = extract_buyer_personas(
            inputs={"deals": deals},
            context=CONTEXT,
        )
        
        assert result["status"] == "error"
        assert "no won deals" in result["error"].lower()
    
    def test_min_occurrences_threshold(self):
        """Should only identify personas meeting minimum threshold."""
        deals = [
            {
                "deal_id": "001",
                "outcome": "won",
                "contacts": [
                    {"title": "VP Sales", "department": "Sales", "role": "champion", "seniority": "VP"},
                ]
            },
            {
                "deal_id": "002",
                "outcome": "won",
                "contacts": [
                    {"title": "VP Sales", "department": "Sales", "role": "champion", "seniority": "VP"},
                ]
            },
            {
                "deal_id": "003",
                "outcome": "won",
                "contacts": [
                    {"title": "Director Marketing", "department": "Marketing", "role": "influencer", "seniority": "Director"},
                ]
            },
        ]
        
        result = extract_buyer_personas(
            inputs={"deals": deals, "min_occurrences": 3},
            context=CONTEXT,
        )
        
        # VP Sales should not appear (only 2 occurrences, threshold is 3)
        personas = result["personas"]
        assert len(personas) == 0  # No personas meet threshold
        
        # Lower threshold
        result2 = extract_buyer_personas(
            inputs={"deals": deals, "min_occurrences": 2},
            context=CONTEXT,
        )
        
        personas2 = result2["personas"]
        vp_sales = next((p for p in personas2 if p["title_pattern"] == "VP Sales"), None)
        assert vp_sales is not None
        assert vp_sales["occurrence_count"] == 2
