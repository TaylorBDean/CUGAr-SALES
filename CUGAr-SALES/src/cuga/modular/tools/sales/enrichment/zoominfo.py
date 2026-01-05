from cuga.security.http_client import SafeClient
import os

class ZoomInfoAPI:
    def __init__(self):
        self.api_key = os.getenv("ZOOMINFO_API_KEY")
        self.base_url = "https://api.zoominfo.com"

    def get_company_info(self, company_name):
        endpoint = f"{self.base_url}/company"
        params = {
            "name": company_name,
            "api_key": self.api_key
        }
        response = SafeClient.get(endpoint, params=params)
        return response.json()

    def get_contact_info(self, email):
        endpoint = f"{self.base_url}/contact"
        params = {
            "email": email,
            "api_key": self.api_key
        }
        response = SafeClient.get(endpoint, params=params)
        return response.json()

    def get_buying_signals(self, company_name):
        endpoint = f"{self.base_url}/buying-signals"
        params = {
            "company": company_name,
            "api_key": self.api_key
        }
        response = SafeClient.get(endpoint, params=params)
        return response.json()