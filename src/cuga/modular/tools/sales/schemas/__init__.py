"""
Canonical data schemas for sales capabilities.

All schemas are vendor-neutral and follow AGENTS.md contracts.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum


class AccountStatus(Enum):
    """Account lifecycle status."""
    PROSPECT = "prospect"
    QUALIFIED = "qualified"
    ACTIVE = "active"
    DORMANT = "dormant"
    CHURNED = "churned"


class DealStage(Enum):
    """Opportunity progression stages."""
    DISCOVERY = "discovery"
    QUALIFICATION = "qualification"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class MessageChannel(Enum):
    """Outreach channels."""
    EMAIL = "email"
    LINKEDIN = "linkedin"
    PHONE = "phone"
    MEETING = "meeting"


@dataclass
class AccountRecord:
    """
    Vendor-neutral account representation.
    
    This schema is designed to be mappable from ANY CRM system.
    It captures capability needs, not infrastructure specifics.
    """
    account_id: str
    name: str
    status: AccountStatus = AccountStatus.PROSPECT
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    revenue: Optional[float] = None
    region: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict (profile-safe, no PII leakage)."""
        return {
            "account_id": self.account_id,
            "name": self.name,
            "status": self.status.value,
            "industry": self.industry,
            "employee_count": self.employee_count,
            "revenue": self.revenue,
            "region": self.region,
            "metadata": self.metadata,
        }


@dataclass
class OpportunityRecord:
    """Vendor-neutral opportunity/deal representation."""
    opportunity_id: str
    account_id: str
    stage: DealStage
    amount: Optional[float] = None
    close_date: Optional[str] = None  # ISO 8601
    probability: Optional[float] = None  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "account_id": self.account_id,
            "stage": self.stage.value,
            "amount": self.amount,
            "close_date": self.close_date,
            "probability": self.probability,
            "metadata": self.metadata,
        }


@dataclass
class OutreachMessage:
    """Vendor-neutral outreach message representation."""
    message_id: str
    channel: MessageChannel
    subject: Optional[str] = None
    body: Optional[str] = None
    recipient: Optional[str] = None  # Email or identifier
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "channel": self.channel.value,
            "subject": self.subject,
            "body": self.body,
            "recipient": self.recipient,
            "metadata": self.metadata,
        }


@dataclass
class QualificationCriteria:
    """BANT/MEDDICC-style qualification criteria."""
    budget: Optional[bool] = None
    authority: Optional[bool] = None
    need: Optional[bool] = None
    timing: Optional[bool] = None
    # MEDDICC extensions
    metrics: Optional[bool] = None
    economic_buyer: Optional[bool] = None
    decision_criteria: Optional[bool] = None
    decision_process: Optional[bool] = None
    identify_pain: Optional[bool] = None
    champion: Optional[bool] = None
    competition: Optional[bool] = None
    
    def score(self) -> float:
        """
        Calculate qualification score (0.0 to 1.0).
        
        Uses BANT as baseline (4 criteria), with MEDDICC extensions
        adding bonus weight for deeper qualification.
        """
        bant_score = sum([
            self.budget or False,
            self.authority or False,
            self.need or False,
            self.timing or False,
        ]) / 4.0
        
        meddicc_fields = [
            self.metrics, self.economic_buyer, self.decision_criteria,
            self.decision_process, self.identify_pain, self.champion,
            self.competition
        ]
        meddicc_score = sum([f or False for f in meddicc_fields]) / len(meddicc_fields)
        
        # Weighted: 70% BANT, 30% MEDDICC
        return 0.7 * bant_score + 0.3 * meddicc_score


__all__ = [
    "AccountStatus",
    "DealStage",
    "MessageChannel",
    "AccountRecord",
    "OpportunityRecord",
    "OutreachMessage",
    "QualificationCriteria",
]
