"""
Salesforce CRM adapter using SafeClient with OAuth2 authentication.

Implements CRMAdapter protocol for Salesforce-specific integration.

SAFETY:
- All HTTP via SafeClient (10s timeout, exponential backoff)
- Env-only secrets (SALESFORCE_* credentials)
- OAuth2 token refresh with automatic retry
- URL redaction in logs
- Vendor-neutral return types (AccountRecord, OpportunityRecord)

REMOVABILITY:
- Can be disabled without breaking capabilities
- Capabilities fall back to offline mode if adapter unavailable

OAuth2 Flow:
1. Username-password flow (for service accounts)
2. Token cached in memory (no persistent storage)
3. Automatic refresh on 401 responses
"""

from typing import Dict, Any, List, Optional
import os
import logging
from datetime import datetime
from urllib.parse import urlencode

from cuga.security.http_client import SafeClient
from cuga.modular.tools.sales.schemas import AccountRecord, OpportunityRecord, AccountStatus, DealStage

logger = logging.getLogger(__name__)


class SalesforceAdapter:
    """
    Salesforce CRM adapter implementing CRMAdapter protocol.
    
    API Documentation: https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/
    
    Requires:
        SALESFORCE_CLIENT_ID: Connected app client ID
        SALESFORCE_CLIENT_SECRET: Connected app client secret
        SALESFORCE_USERNAME: Salesforce username
        SALESFORCE_PASSWORD: Salesforce password
        SALESFORCE_SECURITY_TOKEN: Security token (appended to password)
        SALESFORCE_INSTANCE_URL (optional): Instance URL (defaults to login.salesforce.com)
    """
    
    AUTH_URL = "https://login.salesforce.com/services/oauth2/token"
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        security_token: Optional[str] = None,
        instance_url: Optional[str] = None,
    ):
        """
        Initialize Salesforce adapter with OAuth2 credentials.
        
        Args:
            client_id: Connected app client ID (defaults to SALESFORCE_CLIENT_ID env var)
            client_secret: Connected app client secret (defaults to SALESFORCE_CLIENT_SECRET)
            username: Salesforce username (defaults to SALESFORCE_USERNAME)
            password: Salesforce password (defaults to SALESFORCE_PASSWORD)
            security_token: Security token (defaults to SALESFORCE_SECURITY_TOKEN)
            instance_url: Salesforce instance URL (defaults to SALESFORCE_INSTANCE_URL or login.salesforce.com)
            
        Raises:
            ValueError: If required credentials not provided and not in environment
        """
        self.client_id = client_id or os.getenv("SALESFORCE_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("SALESFORCE_CLIENT_SECRET")
        self.username = username or os.getenv("SALESFORCE_USERNAME")
        self.password = password or os.getenv("SALESFORCE_PASSWORD")
        self.security_token = security_token or os.getenv("SALESFORCE_SECURITY_TOKEN")
        self.instance_url = instance_url or os.getenv("SALESFORCE_INSTANCE_URL", "https://login.salesforce.com")
        
        # Validate required credentials
        missing = []
        if not self.client_id:
            missing.append("SALESFORCE_CLIENT_ID")
        if not self.client_secret:
            missing.append("SALESFORCE_CLIENT_SECRET")
        if not self.username:
            missing.append("SALESFORCE_USERNAME")
        if not self.password:
            missing.append("SALESFORCE_PASSWORD")
        if not self.security_token:
            missing.append("SALESFORCE_SECURITY_TOKEN")
        
        if missing:
            raise ValueError(
                f"Salesforce credentials not found. Missing environment variables: {', '.join(missing)}. "
                "See .env.example for configuration."
            )
        
        # OAuth2 token state
        self._access_token: Optional[str] = None
        self._instance_url: Optional[str] = None
        
        # Initialize SafeClient (will be configured after auth)
        self._client: Optional[SafeClient] = None
        
        # Authenticate on initialization
        self._authenticate()
    
    def _authenticate(self):
        """
        Authenticate with Salesforce using username-password OAuth2 flow.
        
        Raises:
            Exception: If authentication fails
        """
        logger.info("Authenticating with Salesforce OAuth2")
        
        # Prepare OAuth2 request
        auth_data = {
            "grant_type": "password",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "password": f"{self.password}{self.security_token}",  # Token appended to password
        }
        
        # Use temporary SafeClient for auth request
        auth_client = SafeClient(base_url=self.AUTH_URL.rsplit("/", 1)[0])
        
        try:
            response = auth_client.post(
                "/services/oauth2/token",
                data=auth_data,
            )
            response.raise_for_status()
            
            auth_response = response.json()
            self._access_token = auth_response["access_token"]
            self._instance_url = auth_response["instance_url"]
            
            logger.info(f"Salesforce authentication successful: {self._instance_url}")
            
            # Initialize API client with access token
            self._client = SafeClient(
                base_url=self._instance_url,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                },
            )
            
        except Exception as e:
            logger.error(f"Salesforce authentication failed: {e}")
            raise
    
    def _refresh_token_if_needed(self, response):
        """
        Check if token expired and refresh if needed.
        
        Args:
            response: HTTP response to check for 401
            
        Returns:
            True if token was refreshed
        """
        if response.status_code == 401:
            logger.warning("Salesforce token expired, refreshing")
            self._authenticate()
            return True
        return False
    
    # ========================================
    # CRMAdapter Protocol Implementation
    # ========================================
    
    def create_account(
        self,
        account_data: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create account in Salesforce.
        
        Args:
            account_data: Normalized AccountRecord dict
            context: {trace_id, profile}
            
        Returns:
            {account_id, status, created_at}
        """
        trace_id = context.get("trace_id", "unknown")
        logger.info(f"[{trace_id}] Creating Salesforce account: {account_data.get('name')}")
        
        # Map to Salesforce Account object
        sf_account = self._map_account_to_salesforce(account_data)
        
        # Create via API
        response = self._client.post(
            "/services/data/v58.0/sobjects/Account",
            json=sf_account,
        )
        
        # Handle token expiration
        if self._refresh_token_if_needed(response):
            response = self._client.post(
                "/services/data/v58.0/sobjects/Account",
                json=sf_account,
            )
        
        response.raise_for_status()
        result = response.json()
        
        return {
            "account_id": result["id"],
            "status": "created",
            "created_at": datetime.utcnow().isoformat(),
        }
    
    def get_account(
        self,
        account_id: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Retrieve account from Salesforce.
        
        Args:
            account_id: Salesforce Account ID
            context: {trace_id, profile}
            
        Returns:
            Vendor-neutral AccountRecord dict
        """
        trace_id = context.get("trace_id", "unknown")
        logger.info(f"[{trace_id}] Retrieving Salesforce account: {account_id}")
        
        # Query Account with fields
        fields = [
            "Id", "Name", "Industry", "NumberOfEmployees", "AnnualRevenue",
            "BillingCity", "BillingState", "BillingCountry",
            "Type", "CreatedDate", "LastModifiedDate",
        ]
        response = self._client.get(
            f"/services/data/v58.0/sobjects/Account/{account_id}",
            params={"fields": ",".join(fields)},
        )
        
        # Handle token expiration
        if self._refresh_token_if_needed(response):
            response = self._client.get(
                f"/services/data/v58.0/sobjects/Account/{account_id}",
                params={"fields": ",".join(fields)},
            )
        
        response.raise_for_status()
        sf_account = response.json()
        
        # Map to vendor-neutral AccountRecord
        return self._map_salesforce_to_account(sf_account)
    
    def search_accounts(
        self,
        filters: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Search accounts in Salesforce using SOQL.
        
        Args:
            filters: Search criteria (name, industry, min_revenue, etc.)
            context: {trace_id, profile}
            
        Returns:
            {count, total, accounts: [AccountRecord dicts]}
        """
        trace_id = context.get("trace_id", "unknown")
        logger.info(f"[{trace_id}] Searching Salesforce accounts with filters: {filters}")
        
        # Build SOQL query
        query = "SELECT Id, Name, Industry, NumberOfEmployees, AnnualRevenue, BillingCity, BillingState, Type FROM Account WHERE "
        conditions = []
        
        if "name" in filters:
            conditions.append(f"Name LIKE '%{filters['name']}%'")
        if "industry" in filters:
            conditions.append(f"Industry = '{filters['industry']}'")
        if "min_revenue" in filters:
            conditions.append(f"AnnualRevenue >= {filters['min_revenue']}")
        
        if not conditions:
            conditions.append("Id != null")  # Match all if no filters
        
        query += " AND ".join(conditions)
        query += " LIMIT 100"
        
        # Execute query
        response = self._client.get(
            "/services/data/v58.0/query",
            params={"q": query},
        )
        
        # Handle token expiration
        if self._refresh_token_if_needed(response):
            response = self._client.get(
                "/services/data/v58.0/query",
                params={"q": query},
            )
        
        response.raise_for_status()
        result = response.json()
        
        # Map results to vendor-neutral format
        accounts = [
            self._map_salesforce_to_account(record)
            for record in result.get("records", [])
        ]
        
        return {
            "count": len(accounts),
            "total": result.get("totalSize", len(accounts)),
            "accounts": accounts,
        }
    
    def create_opportunity(
        self,
        opportunity_data: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create opportunity in Salesforce.
        
        Args:
            opportunity_data: Normalized OpportunityRecord dict
            context: {trace_id, profile}
            
        Returns:
            {opportunity_id, status, created_at}
        """
        trace_id = context.get("trace_id", "unknown")
        logger.info(f"[{trace_id}] Creating Salesforce opportunity: {opportunity_data.get('name')}")
        
        # Map to Salesforce Opportunity object
        sf_opp = self._map_opportunity_to_salesforce(opportunity_data)
        
        # Create via API
        response = self._client.post(
            "/services/data/v58.0/sobjects/Opportunity",
            json=sf_opp,
        )
        
        # Handle token expiration
        if self._refresh_token_if_needed(response):
            response = self._client.post(
                "/services/data/v58.0/sobjects/Opportunity",
                json=sf_opp,
            )
        
        response.raise_for_status()
        result = response.json()
        
        return {
            "opportunity_id": result["id"],
            "status": "created",
            "created_at": datetime.utcnow().isoformat(),
        }
    
    def get_opportunity(
        self,
        opportunity_id: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Retrieve opportunity from Salesforce.
        
        Args:
            opportunity_id: Salesforce Opportunity ID
            context: {trace_id, profile}
            
        Returns:
            Vendor-neutral OpportunityRecord dict
        """
        trace_id = context.get("trace_id", "unknown")
        logger.info(f"[{trace_id}] Retrieving Salesforce opportunity: {opportunity_id}")
        
        # Query Opportunity with fields
        fields = [
            "Id", "Name", "AccountId", "StageName", "Amount", "CloseDate",
            "Probability", "Type", "CreatedDate", "LastModifiedDate",
        ]
        response = self._client.get(
            f"/services/data/v58.0/sobjects/Opportunity/{opportunity_id}",
            params={"fields": ",".join(fields)},
        )
        
        # Handle token expiration
        if self._refresh_token_if_needed(response):
            response = self._client.get(
                f"/services/data/v58.0/sobjects/Opportunity/{opportunity_id}",
                params={"fields": ",".join(fields)},
            )
        
        response.raise_for_status()
        sf_opp = response.json()
        
        # Map to vendor-neutral OpportunityRecord
        return self._map_salesforce_to_opportunity(sf_opp)
    
    # ========================================
    # Vendor-Specific Mapping Helpers
    # ========================================
    
    def _map_account_to_salesforce(self, account: Dict[str, Any]) -> Dict[str, Any]:
        """Map vendor-neutral AccountRecord to Salesforce Account object."""
        sf_account = {
            "Name": account.get("name"),
        }
        
        # Optional fields
        if "industry" in account:
            sf_account["Industry"] = account["industry"]
        if "employee_count" in account:
            sf_account["NumberOfEmployees"] = account["employee_count"]
        if "revenue" in account:
            sf_account["AnnualRevenue"] = account["revenue"]
        if "region" in account:
            # Map region to BillingCity (simplified)
            sf_account["BillingCity"] = account["region"]
        if "status" in account:
            # Map status to Type (Customer/Prospect)
            sf_account["Type"] = "Customer" if account["status"] == "customer" else "Prospect"
        
        return sf_account
    
    def _map_salesforce_to_account(self, sf_account: Dict[str, Any]) -> Dict[str, Any]:
        """Map Salesforce Account object to vendor-neutral AccountRecord."""
        return {
            "account_id": sf_account.get("Id"),
            "name": sf_account.get("Name"),
            "industry": sf_account.get("Industry"),
            "employee_count": sf_account.get("NumberOfEmployees"),
            "revenue": sf_account.get("AnnualRevenue"),
            "region": sf_account.get("BillingCity") or sf_account.get("BillingState") or sf_account.get("BillingCountry"),
            "status": "customer" if sf_account.get("Type") == "Customer" else "prospect",
            "metadata": {
                "source": "salesforce",
                "salesforce_id": sf_account.get("Id"),
                "created_at": sf_account.get("CreatedDate"),
                "updated_at": sf_account.get("LastModifiedDate"),
            },
        }
    
    def _map_opportunity_to_salesforce(self, opp: Dict[str, Any]) -> Dict[str, Any]:
        """Map vendor-neutral OpportunityRecord to Salesforce Opportunity object."""
        sf_opp = {
            "Name": opp.get("name"),
            "AccountId": opp.get("account_id"),
            "CloseDate": opp.get("close_date"),
            "StageName": self._map_stage_to_salesforce(opp.get("stage")),
        }
        
        # Optional fields
        if "value" in opp:
            sf_opp["Amount"] = opp["value"]
        if "probability" in opp:
            sf_opp["Probability"] = int(opp["probability"] * 100)  # Convert 0.75 → 75
        
        return sf_opp
    
    def _map_salesforce_to_opportunity(self, sf_opp: Dict[str, Any]) -> Dict[str, Any]:
        """Map Salesforce Opportunity object to vendor-neutral OpportunityRecord."""
        return {
            "opportunity_id": sf_opp.get("Id"),
            "account_id": sf_opp.get("AccountId"),
            "name": sf_opp.get("Name"),
            "stage": self._map_salesforce_stage_to_enum(sf_opp.get("StageName")),
            "value": sf_opp.get("Amount"),
            "close_date": sf_opp.get("CloseDate"),
            "probability": sf_opp.get("Probability", 0) / 100.0,  # Convert 75 → 0.75
            "metadata": {
                "source": "salesforce",
                "salesforce_id": sf_opp.get("Id"),
                "created_at": sf_opp.get("CreatedDate"),
                "updated_at": sf_opp.get("LastModifiedDate"),
                "original_stage": sf_opp.get("StageName"),
            },
        }
    
    def _map_stage_to_salesforce(self, stage: Optional[str]) -> str:
        """Map DealStage enum to Salesforce stage name."""
        stage_map = {
            "discovery": "Qualification",
            "qualification": "Needs Analysis",
            "proposal": "Proposal/Price Quote",
            "negotiation": "Negotiation/Review",
            "closed_won": "Closed Won",
            "closed_lost": "Closed Lost",
        }
        return stage_map.get(stage, "Prospecting")
    
    def _map_salesforce_stage_to_enum(self, sf_stage: Optional[str]) -> str:
        """Map Salesforce stage name to DealStage enum."""
        # Reverse mapping with common Salesforce stage names
        stage_map = {
            "Prospecting": "discovery",
            "Qualification": "discovery",
            "Needs Analysis": "qualification",
            "Value Proposition": "qualification",
            "Id. Decision Makers": "qualification",
            "Perception Analysis": "qualification",
            "Proposal/Price Quote": "proposal",
            "Negotiation/Review": "negotiation",
            "Closed Won": "closed_won",
            "Closed Lost": "closed_lost",
        }
        return stage_map.get(sf_stage, "discovery")
