"""
Pipedrive CRM adapter using SafeClient with API key authentication.

Implements CRMAdapter protocol for Pipedrive-specific integration.

SAFETY:
- All HTTP via SafeClient (10s timeout, exponential backoff)
- Env-only secrets (PIPEDRIVE_API_KEY)
- URL redaction in logs
- Vendor-neutral return types (AccountRecord, OpportunityRecord)

REMOVABILITY:
- Can be disabled without breaking capabilities
- Capabilities fall back to offline mode if adapter unavailable
"""

from typing import Dict, Any, List, Optional
import os
import logging
from datetime import datetime

from cuga.security.http_client import SafeClient
from cuga.modular.tools.sales.schemas import AccountRecord, OpportunityRecord, AccountStatus, DealStage

logger = logging.getLogger(__name__)


class PipedriveAdapter:
    """
    Pipedrive CRM adapter implementing CRMAdapter protocol.
    
    API Documentation: https://developers.pipedrive.com/docs/api/v1
    
    Requires:
        PIPEDRIVE_API_KEY: API key from Settings > Personal preferences > API
        PIPEDRIVE_COMPANY_DOMAIN: Company domain (e.g., 'mycompany' for mycompany.pipedrive.com)
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        company_domain: Optional[str] = None,
    ):
        """
        Initialize Pipedrive adapter.
        
        Args:
            api_key: Pipedrive API key (defaults to PIPEDRIVE_API_KEY env var)
            company_domain: Company domain (defaults to PIPEDRIVE_COMPANY_DOMAIN)
            
        Raises:
            ValueError: If required credentials not provided and not in environment
        """
        self.api_key = api_key or os.getenv("PIPEDRIVE_API_KEY")
        self.company_domain = company_domain or os.getenv("PIPEDRIVE_COMPANY_DOMAIN")
        
        # Validate required credentials
        if not self.api_key:
            raise ValueError(
                "PIPEDRIVE_API_KEY not found in environment variables. "
                "See .env.example for configuration."
            )
        if not self.company_domain:
            raise ValueError(
                "PIPEDRIVE_COMPANY_DOMAIN not found in environment variables. "
                "See .env.example for configuration."
            )
        
        # Initialize SafeClient with API key in query params (Pipedrive convention)
        base_url = f"https://{self.company_domain}.pipedrive.com/api/v1"
        self.client = SafeClient(
            base_url=base_url,
            headers={"Content-Type": "application/json"},
        )
        
        logger.info(f"Pipedrive adapter initialized: {base_url}")
    
    def _add_api_key(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add API key to query parameters (Pipedrive convention)."""
        params = params or {}
        params["api_token"] = self.api_key
        return params
    
    # ========================================
    # CRMAdapter Protocol Implementation
    # ========================================
    
    def create_account(
        self,
        account_data: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create organization in Pipedrive.
        
        Args:
            account_data: Normalized AccountRecord dict
            context: {trace_id, profile}
            
        Returns:
            {account_id, status, created_at}
        """
        trace_id = context.get("trace_id", "unknown")
        logger.info(f"[{trace_id}] Creating Pipedrive organization: {account_data.get('name')}")
        
        # Map to Pipedrive Organization object
        pd_org = self._map_account_to_pipedrive(account_data)
        
        # Create via API
        response = self.client.post(
            "/organizations",
            json=pd_org,
            params=self._add_api_key(),
        )
        response.raise_for_status()
        result = response.json()
        
        if not result.get("success"):
            raise Exception(f"Pipedrive API error: {result.get('error')}")
        
        org_data = result["data"]
        
        return {
            "account_id": str(org_data["id"]),
            "status": "created",
            "created_at": org_data.get("add_time", datetime.utcnow().isoformat()),
        }
    
    def get_account(
        self,
        account_id: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Retrieve organization from Pipedrive.
        
        Args:
            account_id: Pipedrive Organization ID
            context: {trace_id, profile}
            
        Returns:
            Vendor-neutral AccountRecord dict
        """
        trace_id = context.get("trace_id", "unknown")
        logger.info(f"[{trace_id}] Retrieving Pipedrive organization: {account_id}")
        
        # Query Organization
        response = self.client.get(
            f"/organizations/{account_id}",
            params=self._add_api_key(),
        )
        response.raise_for_status()
        result = response.json()
        
        if not result.get("success"):
            raise Exception(f"Pipedrive API error: {result.get('error')}")
        
        pd_org = result["data"]
        
        # Map to vendor-neutral AccountRecord
        return self._map_pipedrive_to_account(pd_org)
    
    def search_accounts(
        self,
        filters: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Search organizations in Pipedrive.
        
        Args:
            filters: Search criteria (name, industry, etc.)
            context: {trace_id, profile}
            
        Returns:
            {count, total, accounts: [AccountRecord dicts]}
        """
        trace_id = context.get("trace_id", "unknown")
        logger.info(f"[{trace_id}] Searching Pipedrive organizations with filters: {filters}")
        
        # Pipedrive search uses term parameter
        search_term = filters.get("name", "")
        
        if not search_term:
            # If no search term, get all organizations (limited)
            response = self.client.get(
                "/organizations",
                params=self._add_api_key({"limit": 100}),
            )
        else:
            # Search organizations by term
            response = self.client.get(
                "/organizations/search",
                params=self._add_api_key({"term": search_term, "limit": 100}),
            )
        
        response.raise_for_status()
        result = response.json()
        
        if not result.get("success"):
            raise Exception(f"Pipedrive API error: {result.get('error')}")
        
        # Map results to vendor-neutral format
        items = result.get("data", {}).get("items", []) if "items" in result.get("data", {}) else result.get("data", [])
        
        accounts = []
        for item in items:
            # Handle search result format vs direct list format
            org_data = item.get("item", item) if "item" in item else item
            accounts.append(self._map_pipedrive_to_account(org_data))
        
        return {
            "count": len(accounts),
            "total": result.get("additional_data", {}).get("pagination", {}).get("total", len(accounts)),
            "accounts": accounts,
        }
    
    def create_opportunity(
        self,
        opportunity_data: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create deal in Pipedrive.
        
        Args:
            opportunity_data: Normalized OpportunityRecord dict
            context: {trace_id, profile}
            
        Returns:
            {opportunity_id, status, created_at}
        """
        trace_id = context.get("trace_id", "unknown")
        logger.info(f"[{trace_id}] Creating Pipedrive deal: {opportunity_data.get('name')}")
        
        # Map to Pipedrive Deal object
        pd_deal = self._map_opportunity_to_pipedrive(opportunity_data)
        
        # Create via API
        response = self.client.post(
            "/deals",
            json=pd_deal,
            params=self._add_api_key(),
        )
        response.raise_for_status()
        result = response.json()
        
        if not result.get("success"):
            raise Exception(f"Pipedrive API error: {result.get('error')}")
        
        deal_data = result["data"]
        
        return {
            "opportunity_id": str(deal_data["id"]),
            "status": "created",
            "created_at": deal_data.get("add_time", datetime.utcnow().isoformat()),
        }
    
    def get_opportunity(
        self,
        opportunity_id: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Retrieve deal from Pipedrive.
        
        Args:
            opportunity_id: Pipedrive Deal ID
            context: {trace_id, profile}
            
        Returns:
            Vendor-neutral OpportunityRecord dict
        """
        trace_id = context.get("trace_id", "unknown")
        logger.info(f"[{trace_id}] Retrieving Pipedrive deal: {opportunity_id}")
        
        # Query Deal
        response = self.client.get(
            f"/deals/{opportunity_id}",
            params=self._add_api_key(),
        )
        response.raise_for_status()
        result = response.json()
        
        if not result.get("success"):
            raise Exception(f"Pipedrive API error: {result.get('error')}")
        
        pd_deal = result["data"]
        
        # Map to vendor-neutral OpportunityRecord
        return self._map_pipedrive_to_opportunity(pd_deal)
    
    # ========================================
    # Vendor-Specific Mapping Helpers
    # ========================================
    
    def _map_account_to_pipedrive(self, account: Dict[str, Any]) -> Dict[str, Any]:
        """Map vendor-neutral AccountRecord to Pipedrive Organization object."""
        pd_org = {
            "name": account.get("name"),
        }
        
        # Pipedrive uses custom fields for industry, revenue, employee count
        # Note: In production, you'd configure custom field IDs from Pipedrive settings
        # For now, we'll use the standard 'address' field for region
        
        if "region" in account:
            pd_org["address"] = account["region"]
        
        # Custom fields would be added like:
        # pd_org["<custom_field_hash>"] = account["industry"]
        
        return pd_org
    
    def _map_pipedrive_to_account(self, pd_org: Dict[str, Any]) -> Dict[str, Any]:
        """Map Pipedrive Organization object to vendor-neutral AccountRecord."""
        return {
            "account_id": str(pd_org.get("id")),
            "name": pd_org.get("name"),
            "industry": None,  # Would come from custom field
            "employee_count": pd_org.get("people_count"),
            "revenue": None,  # Would come from custom field
            "region": pd_org.get("address"),
            "status": "active" if pd_org.get("active_flag") else "inactive",
            "metadata": {
                "source": "pipedrive",
                "pipedrive_id": pd_org.get("id"),
                "created_at": pd_org.get("add_time"),
                "updated_at": pd_org.get("update_time"),
                "owner_id": pd_org.get("owner_id", {}).get("id") if isinstance(pd_org.get("owner_id"), dict) else pd_org.get("owner_id"),
            },
        }
    
    def _map_opportunity_to_pipedrive(self, opp: Dict[str, Any]) -> Dict[str, Any]:
        """Map vendor-neutral OpportunityRecord to Pipedrive Deal object."""
        pd_deal = {
            "title": opp.get("name"),
            "org_id": int(opp["account_id"]) if opp.get("account_id") else None,
        }
        
        # Optional fields
        if "value" in opp:
            pd_deal["value"] = opp["value"]
        if "stage" in opp:
            # Note: stage_id would need to be mapped from your pipeline configuration
            # For now, we'll use the stage name as a custom field
            pd_deal["stage_id"] = self._map_stage_to_pipedrive_id(opp["stage"])
        if "close_date" in opp:
            pd_deal["expected_close_date"] = opp["close_date"]
        if "probability" in opp:
            # Pipedrive doesn't have a standard probability field
            # Would be stored in custom field in production
            pass
        
        return pd_deal
    
    def _map_pipedrive_to_opportunity(self, pd_deal: Dict[str, Any]) -> Dict[str, Any]:
        """Map Pipedrive Deal object to vendor-neutral OpportunityRecord."""
        # Extract org_id (can be object or int)
        org_id = pd_deal.get("org_id")
        if isinstance(org_id, dict):
            org_id = org_id.get("value")
        
        return {
            "opportunity_id": str(pd_deal.get("id")),
            "account_id": str(org_id) if org_id else None,
            "name": pd_deal.get("title"),
            "stage": self._map_pipedrive_stage_to_enum(pd_deal.get("stage_id")),
            "value": pd_deal.get("value"),
            "close_date": pd_deal.get("expected_close_date"),
            "probability": pd_deal.get("win_probability", 0) / 100.0 if pd_deal.get("win_probability") else None,
            "metadata": {
                "source": "pipedrive",
                "pipedrive_id": pd_deal.get("id"),
                "created_at": pd_deal.get("add_time"),
                "updated_at": pd_deal.get("update_time"),
                "status": pd_deal.get("status"),
                "pipeline_id": pd_deal.get("pipeline_id"),
                "stage_id": pd_deal.get("stage_id"),
            },
        }
    
    def _map_stage_to_pipedrive_id(self, stage: Optional[str]) -> Optional[int]:
        """
        Map DealStage enum to Pipedrive stage ID.
        
        NOTE: In production, this should be configured from your actual pipeline.
        Pipedrive stage IDs are specific to each company's pipeline configuration.
        This is a placeholder that returns None (default stage).
        """
        # Example mapping (would be customized per deployment):
        # stage_map = {
        #     "discovery": 1,
        #     "qualification": 2,
        #     "proposal": 3,
        #     "negotiation": 4,
        #     "closed_won": 5,
        #     "closed_lost": 6,
        # }
        # return stage_map.get(stage)
        
        logger.warning(f"Stage mapping not configured for Pipedrive. Stage '{stage}' will use default.")
        return None
    
    def _map_pipedrive_stage_to_enum(self, stage_id: Optional[int]) -> str:
        """
        Map Pipedrive stage ID to DealStage enum.
        
        NOTE: In production, this should be configured from your actual pipeline.
        This is a placeholder that returns 'discovery' for all stages.
        """
        # Example reverse mapping (would be customized per deployment):
        # stage_map = {
        #     1: "discovery",
        #     2: "qualification",
        #     3: "proposal",
        #     4: "negotiation",
        #     5: "closed_won",
        #     6: "closed_lost",
        # }
        # return stage_map.get(stage_id, "discovery")
        
        return "discovery"  # Default fallback
