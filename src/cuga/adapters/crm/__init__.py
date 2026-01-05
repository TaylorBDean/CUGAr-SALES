"""
CRM adapters for vendor-neutral capability integration.

All CRM adapters MUST:
- Use SafeClient for HTTP (10s read, 5s connect, exponential backoff)
- Load secrets from environment only (no hardcoded API keys)
- Return vendor-neutral data (AccountRecord, OpportunityRecord)
- Handle errors gracefully (raise clear exceptions)
- Support trace-ID propagation for observability
"""

from typing import Protocol, Dict, Any, List, Optional


class CRMAdapter(Protocol):
    """
    Protocol for CRM adapter implementations.
    
    All CRM adapters (HubSpot, Salesforce, Pipedrive, etc.) implement this interface.
    Capabilities call through this protocol, never directly to vendor-specific code.
    """
    
    def create_account(
        self,
        account_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create account in CRM.
        
        Args:
            account_data: Normalized AccountRecord dict
            context: {trace_id, profile}
            
        Returns:
            {account_id, status, created_at}
        """
        ...
    
    def get_account(
        self,
        account_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Retrieve account from CRM.
        
        Args:
            account_id: CRM-specific account identifier
            context: {trace_id, profile}
            
        Returns:
            Normalized AccountRecord dict
        """
        ...
    
    def search_accounts(
        self,
        filters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Search accounts in CRM.
        
        Args:
            filters: {email?, company?, status?}
            context: {trace_id, profile}
            
        Returns:
            {accounts: List[AccountRecord], count: int}
        """
        ...
    
    def create_opportunity(
        self,
        opportunity_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create opportunity/deal in CRM.
        
        Args:
            opportunity_data: Normalized OpportunityRecord dict
            context: {trace_id, profile}
            
        Returns:
            {opportunity_id, status, created_at}
        """
        ...
    
    def get_opportunity(
        self,
        opportunity_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Retrieve opportunity from CRM.
        
        Args:
            opportunity_id: CRM-specific opportunity identifier
            context: {trace_id, profile}
            
        Returns:
            Normalized OpportunityRecord dict
        """
        ...


__all__ = ["CRMAdapter"]
