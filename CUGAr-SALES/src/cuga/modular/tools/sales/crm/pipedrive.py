from cuga.modular.tools.sales.crm.base import CRMBase

class PipedriveCRM(CRMBase):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "https://api.pipedrive.com/v1"

    def get_deals(self):
        """Retrieve all deals from Pipedrive."""
        endpoint = f"{self.base_url}/deals?api_token={self.api_key}"
        response = self._make_request(endpoint)
        return response.get('data', [])

    def add_deal(self, title: str, value: float, stage_id: int):
        """Add a new deal to Pipedrive."""
        endpoint = f"{self.base_url}/deals?api_token={self.api_key}"
        data = {
            "title": title,
            "value": value,
            "stage_id": stage_id
        }
        response = self._make_request(endpoint, method='POST', json=data)
        return response.get('data', {})

    def update_deal(self, deal_id: int, updates: dict):
        """Update an existing deal in Pipedrive."""
        endpoint = f"{self.base_url}/deals/{deal_id}?api_token={self.api_key}"
        response = self._make_request(endpoint, method='PUT', json=updates)
        return response.get('data', {})

    def delete_deal(self, deal_id: int):
        """Delete a deal from Pipedrive."""
        endpoint = f"{self.base_url}/deals/{deal_id}?api_token={self.api_key}"
        response = self._make_request(endpoint, method='DELETE')
        return response.get('success', False)

    def _make_request(self, url: str, method: str = 'GET', json: dict = None):
        """Make a request to the Pipedrive API."""
        import requests
        if method == 'POST':
            response = requests.post(url, json=json)
        elif method == 'PUT':
            response = requests.put(url, json=json)
        elif method == 'DELETE':
            response = requests.delete(url)
        else:
            response = requests.get(url)
        
        response.raise_for_status()
        return response.json()