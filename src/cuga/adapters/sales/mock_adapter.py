"""
Mock adapter with realistic demo data for immediate showcase.

Uses YAML fixtures in src/cuga/adapters/sales/fixtures/*.yaml
Zero configuration - works out of the box for demos.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import yaml

from .protocol import VendorAdapter, AdapterMode, AdapterConfig


class MockAdapter:
    """Base mock adapter with fixture loading"""
    
    def __init__(self, vendor: str, config: AdapterConfig):
        self.vendor = vendor
        self.config = config
        self.fixtures_path = Path(__file__).parent / "fixtures" / f"{vendor}.yaml"
        self._data: Optional[Dict[str, Any]] = None
    
    def _load_fixtures(self) -> Dict[str, Any]:
        """Load fixtures from YAML (lazy load)"""
        if self._data is None:
            if self.fixtures_path.exists():
                with open(self.fixtures_path, "r") as f:
                    self._data = yaml.safe_load(f) or {}
            else:
                # Fallback to empty data
                self._data = {"accounts": [], "contacts": [], "opportunities": []}
        return self._data
    
    def fetch_accounts(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Fetch accounts from fixtures"""
        data = self._load_fixtures()
        accounts = data.get("accounts", [])
        
        if not filters:
            return accounts
        
        # Apply simple filters
        filtered = accounts
        if "territory" in filters:
            filtered = [a for a in filtered if a.get("territory") == filters["territory"]]
        if "industry" in filters:
            filtered = [a for a in filtered if a.get("industry") == filters["industry"]]
        if "min_revenue" in filters:
            filtered = [a for a in filtered if a.get("annual_revenue", 0) >= filters["min_revenue"]]
        
        return filtered
    
    def fetch_contacts(self, account_id: str) -> List[Dict[str, Any]]:
        """Fetch contacts from fixtures"""
        data = self._load_fixtures()
        contacts = data.get("contacts", [])
        return [c for c in contacts if c.get("account_id") == account_id]
    
    def fetch_opportunities(
        self,
        account_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch opportunities from fixtures"""
        data = self._load_fixtures()
        opportunities = data.get("opportunities", [])
        
        if account_id:
            return [o for o in opportunities if o.get("account_id") == account_id]
        return opportunities
    
    def get_mode(self) -> AdapterMode:
        """Always mock mode"""
        return AdapterMode.MOCK
    
    def validate_connection(self) -> bool:
        """Mock always validates (no real connection)"""
        return True
