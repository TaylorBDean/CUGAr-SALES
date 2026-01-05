"""
HubSpot CRM adapter using SafeClient.

Implements CRMAdapter protocol for HubSpot-specific integration.

SAFETY:
- All HTTP via SafeClient (10s timeout, exponential backoff)
- Env-only secrets (HUBSPOT_API_KEY)
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


class HubSpotAdapter:
    """
    HubSpot CRM adapter implementing CRMAdapter protocol.
    
    API Documentation: https://developers.hubspot.com/docs/api/overview
    
    Requires:
        HUBSPOT_API_KEY environment variable
    """
    
    BASE_URL = "https://api.hubapi.com"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize HubSpot adapter.
        
        Args:
            api_key: HubSpot API key (defaults to HUBSPOT_API_KEY env var)
            
        Raises:
            ValueError: If API key not provided and not in environment
        """
        self.api_key = api_key or os.getenv("HUBSPOT_API_KEY")
        if not self.api_key:
            raise ValueError(
                "HUBSPOT_API_KEY not found. Set via environment variable or pass to constructor."
            )
        
        # Initialize SafeClient with HubSpot-specific config
        self.client = SafeClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        
        logger.info("Initialized HubSpot adapter with SafeClient")
    
    def create_account(
        self,
        account_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create company in HubSpot.
        
        Maps AccountRecord → HubSpot company properties.
        
        Args:
            account_data: Normalized AccountRecord dict
            context: {trace_id, profile}
            
        Returns:
            {account_id, status, created_at}
            
        Raises:
            httpx.HTTPError: On API failure
        """
        trace_id = context.get("trace_id", "unknown")
        
        # Map AccountRecord to HubSpot properties
        properties = {
            "name": account_data["name"],
            "domain": account_data.get("metadata", {}).get("domain", ""),
            "industry": account_data.get("industry", ""),
            "numberofemployees": account_data.get("employee_count"),
            "annualrevenue": account_data.get("revenue"),
            "city": account_data.get("region", ""),
        }
        
        # Remove None values (HubSpot rejects them)
        properties = {k: v for k, v in properties.items() if v is not None}
        
        logger.info(f"[{trace_id}] Creating HubSpot company: {account_data['name']}")
        
        try:
            response = self.client.post(
                "/crm/v3/objects/companies",
                json={"properties": properties}
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "account_id": data["id"],
                "status": "created",
                "created_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"[{trace_id}] HubSpot company creation failed: {e}")
            raise
    
    def get_account(
        self,
        account_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Retrieve company from HubSpot.
        
        Maps HubSpot company → AccountRecord.
        
        Args:
            account_id: HubSpot company ID
            context: {trace_id, profile}
            
        Returns:
            Normalized AccountRecord dict
        """
        trace_id = context.get("trace_id", "unknown")
        
        logger.info(f"[{trace_id}] Fetching HubSpot company: {account_id}")
        
        try:
            response = self.client.get(
                f"/crm/v3/objects/companies/{account_id}",
                params={"properties": "name,industry,numberofemployees,annualrevenue,city"}
            )
            response.raise_for_status()
            data = response.json()
            
            # Map HubSpot properties → AccountRecord
            properties = data.get("properties", {})
            
            account = AccountRecord(
                account_id=data["id"],
                name=properties.get("name", "Unknown"),
                status=AccountStatus.ACTIVE,  # HubSpot doesn't have direct status mapping
                industry=properties.get("industry"),
                employee_count=int(properties["numberofemployees"]) if properties.get("numberofemployees") else None,
                revenue=float(properties["annualrevenue"]) if properties.get("annualrevenue") else None,
                region=properties.get("city"),
                metadata={
                    "source": "hubspot",
                    "hubspot_id": data["id"],
                    "created_at": data.get("createdAt"),
                    "updated_at": data.get("updatedAt"),
                }
            )
            
            return account.to_dict()
            
        except Exception as e:
            logger.error(f"[{trace_id}] HubSpot company fetch failed: {e}")
            raise
    
    def search_accounts(
        self,
        filters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Search companies in HubSpot.
        
        Args:
            filters: {name?, industry?, domain?}
            context: {trace_id, profile}
            
        Returns:
            {accounts: List[AccountRecord], count: int}
        """
        trace_id = context.get("trace_id", "unknown")
        
        # Build HubSpot search query
        filter_groups = []
        
        if "name" in filters:
            filter_groups.append({
                "filters": [{
                    "propertyName": "name",
                    "operator": "CONTAINS_TOKEN",
                    "value": filters["name"]
                }]
            })
        
        if "industry" in filters:
            filter_groups.append({
                "filters": [{
                    "propertyName": "industry",
                    "operator": "EQ",
                    "value": filters["industry"]
                }]
            })
        
        if "domain" in filters:
            filter_groups.append({
                "filters": [{
                    "propertyName": "domain",
                    "operator": "EQ",
                    "value": filters["domain"]
                }]
            })
        
        search_request = {
            "filterGroups": filter_groups,
            "properties": ["name", "industry", "numberofemployees", "annualrevenue", "city"],
            "limit": filters.get("limit", 100)
        }
        
        logger.info(f"[{trace_id}] Searching HubSpot companies with {len(filter_groups)} filters")
        
        try:
            response = self.client.post(
                "/crm/v3/objects/companies/search",
                json=search_request
            )
            response.raise_for_status()
            data = response.json()
            
            # Map results to AccountRecord
            accounts = []
            for result in data.get("results", []):
                properties = result.get("properties", {})
                
                account = AccountRecord(
                    account_id=result["id"],
                    name=properties.get("name", "Unknown"),
                    status=AccountStatus.ACTIVE,
                    industry=properties.get("industry"),
                    employee_count=int(properties["numberofemployees"]) if properties.get("numberofemployees") else None,
                    revenue=float(properties["annualrevenue"]) if properties.get("annualrevenue") else None,
                    region=properties.get("city"),
                    metadata={"source": "hubspot", "hubspot_id": result["id"]}
                )
                accounts.append(account.to_dict())
            
            return {
                "accounts": accounts,
                "count": len(accounts),
                "total": data.get("total", len(accounts))
            }
            
        except Exception as e:
            logger.error(f"[{trace_id}] HubSpot company search failed: {e}")
            raise
    
    def create_opportunity(
        self,
        opportunity_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create deal in HubSpot.
        
        Maps OpportunityRecord → HubSpot deal properties.
        
        Args:
            opportunity_data: Normalized OpportunityRecord dict
            context: {trace_id, profile}
            
        Returns:
            {opportunity_id, status, created_at}
        """
        trace_id = context.get("trace_id", "unknown")
        
        # Map OpportunityRecord to HubSpot deal properties
        properties = {
            "dealname": opportunity_data.get("metadata", {}).get("name", "New Deal"),
            "dealstage": self._map_deal_stage_to_hubspot(opportunity_data.get("stage", "discovery")),
            "amount": opportunity_data.get("amount"),
            "closedate": opportunity_data.get("close_date"),
            "pipeline": "default"  # HubSpot requires pipeline
        }
        
        # Remove None values
        properties = {k: v for k, v in properties.items() if v is not None}
        
        # Associate with company (account)
        associations = []
        if "account_id" in opportunity_data:
            associations.append({
                "to": {"id": opportunity_data["account_id"]},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 341}]  # Deal-to-Company
            })
        
        logger.info(f"[{trace_id}] Creating HubSpot deal")
        
        try:
            payload = {"properties": properties}
            if associations:
                payload["associations"] = associations
            
            response = self.client.post(
                "/crm/v3/objects/deals",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "opportunity_id": data["id"],
                "status": "created",
                "created_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"[{trace_id}] HubSpot deal creation failed: {e}")
            raise
    
    def get_opportunity(
        self,
        opportunity_id: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Retrieve deal from HubSpot.
        
        Maps HubSpot deal → OpportunityRecord.
        
        Args:
            opportunity_id: HubSpot deal ID
            context: {trace_id, profile}
            
        Returns:
            Normalized OpportunityRecord dict
        """
        trace_id = context.get("trace_id", "unknown")
        
        logger.info(f"[{trace_id}] Fetching HubSpot deal: {opportunity_id}")
        
        try:
            response = self.client.get(
                f"/crm/v3/objects/deals/{opportunity_id}",
                params={"properties": "dealname,dealstage,amount,closedate,pipeline"}
            )
            response.raise_for_status()
            data = response.json()
            
            properties = data.get("properties", {})
            
            # Map HubSpot deal stage → DealStage enum
            stage = self._map_hubspot_stage_to_deal_stage(properties.get("dealstage", ""))
            
            opportunity = OpportunityRecord(
                opportunity_id=data["id"],
                account_id="",  # Would need association query
                stage=stage,
                amount=float(properties["amount"]) if properties.get("amount") else None,
                close_date=properties.get("closedate"),
                probability=None,  # HubSpot doesn't store probability directly
                metadata={
                    "source": "hubspot",
                    "hubspot_id": data["id"],
                    "dealname": properties.get("dealname"),
                    "pipeline": properties.get("pipeline"),
                }
            )
            
            return opportunity.to_dict()
            
        except Exception as e:
            logger.error(f"[{trace_id}] HubSpot deal fetch failed: {e}")
            raise
    
    # Helper methods for stage mapping
    
    def _map_deal_stage_to_hubspot(self, stage: str) -> str:
        """Map canonical DealStage → HubSpot deal stage ID."""
        mapping = {
            "discovery": "appointmentscheduled",
            "qualification": "qualifiedtobuy",
            "proposal": "presentationscheduled",
            "negotiation": "decisionmakerboughtin",
            "closed_won": "closedwon",
            "closed_lost": "closedlost",
        }
        return mapping.get(stage, "appointmentscheduled")
    
    def _map_hubspot_stage_to_deal_stage(self, hubspot_stage: str) -> DealStage:
        """Map HubSpot deal stage → canonical DealStage enum."""
        stage_lower = hubspot_stage.lower()
        
        if "closedwon" in stage_lower:
            return DealStage.CLOSED_WON
        elif "closedlost" in stage_lower:
            return DealStage.CLOSED_LOST
        elif "decision" in stage_lower or "negotiat" in stage_lower:
            return DealStage.NEGOTIATION
        elif "presentation" in stage_lower or "proposal" in stage_lower:
            return DealStage.PROPOSAL
        elif "qualified" in stage_lower:
            return DealStage.QUALIFICATION
        else:
            return DealStage.DISCOVERY
