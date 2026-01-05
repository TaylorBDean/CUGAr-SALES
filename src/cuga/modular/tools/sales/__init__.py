"""
Sales capability tools for CUGAr-SALES.

All tools follow AGENTS.md guardrails:
- Capability-first (not vendor-specific)
- Offline-first (no network by default)
- Deterministic inputs/outputs
- Structured schemas
- Trace-ID propagation
- Observability events
- Budget enforcement

Organized by canonical core domain:
1. Territory & Capacity Planning
2. Account & Prospect Intelligence  
3. Product & Knowledge Enablement
4. Outreach & Engagement
5. Qualification & Deal Progression
6. Analytics, Learning & Governance
"""

# Domain 1: Territory & Capacity
from .territory import (
    simulate_territory_change,
    assess_capacity_coverage,
)

# Domain 2: Account Intelligence
from .account_intelligence import (
    normalize_account_record,
    score_account_fit,
    retrieve_account_signals,
)

# Domain 5: Qualification
from .qualification import (
    qualify_opportunity,
    assess_deal_risk,
)

# Domain 6: Analytics & Governance
from .intelligence import (
    analyze_win_loss_patterns,
    extract_buyer_personas,
)

# Domain 4: Outreach
from .outreach import (
    draft_outbound_message,
    assess_message_quality,
)

__all__ = [
    # Domain 1: Territory & Capacity
    "simulate_territory_change",
    "assess_capacity_coverage",
    
    # Domain 2: Account Intelligence
    "normalize_account_record",
    "score_account_fit",
    "retrieve_account_signals",
    
    # Domain 4: Outreach
    "draft_outbound_message",
    "assess_message_quality",
    
    # Domain 5: Qualification
    "qualify_opportunity",
    "assess_deal_risk",
    
    # Domain 6: Analytics & Governance
    "analyze_win_loss_patterns",
    "extract_buyer_personas",
]
