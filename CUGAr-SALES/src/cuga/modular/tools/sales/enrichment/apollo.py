from cuga.security.http_client import SafeClient
import os

class ApolloAPI:
    def __init__(self):
        self.api_key = os.getenv("APOLLO_API_KEY")
        self.base_url = "https://api.apollo.io/v1"

    def get_contact(self, contact_id):
        url = f"{self.base_url}/contacts/{contact_id}"
        response = SafeClient.get(url, headers={"Authorization": f"Bearer {self.api_key}"})
        return response.json()

    def get_company(self, company_id):
        url = f"{self.base_url}/companies/{company_id}"
        response = SafeClient.get(url, headers={"Authorization": f"Bearer {self.api_key}"})
        return response.json()

    def search_contacts(self, params):
        url = f"{self.base_url}/contacts/search"
        response = SafeClient.post(url, json=params, headers={"Authorization": f"Bearer {self.api_key}"})
        return response.json()

    def search_companies(self, params):
        url = f"{self.base_url}/companies/search"
        response = SafeClient.post(url, json=params, headers={"Authorization": f"Bearer {self.api_key}"})
        return response.json()