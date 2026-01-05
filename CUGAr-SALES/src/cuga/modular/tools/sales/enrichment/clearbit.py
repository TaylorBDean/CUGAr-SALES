from cuga.security.http_client import SafeClient
import os

class ClearbitAPI:
    def __init__(self):
        self.api_key = os.getenv("CLEARBIT_API_KEY")
        self.base_url = "https://api.clearbit.com/v2/"

    def get_company(self, domain):
        url = f"{self.base_url}companies/find?domain={domain}"
        response = SafeClient.get(url, headers={"Authorization": f"Bearer {self.api_key}"})
        return response.json() if response.status_code == 200 else None

    def get_person(self, email):
        url = f"{self.base_url}people/find?email={email}"
        response = SafeClient.get(url, headers={"Authorization": f"Bearer {self.api_key}"})
        return response.json() if response.status_code == 200 else None

    def enrich_data(self, email=None, domain=None):
        if email:
            return self.get_person(email)
        elif domain:
            return self.get_company(domain)
        else:
            raise ValueError("Either email or domain must be provided for enrichment.")