import unittest
from src.cuga.modular.tools.sales.crm.salesforce import Salesforce
from src.cuga.modular.tools.sales.crm.hubspot import HubSpot
from src.cuga.modular.tools.sales.crm.pipedrive import Pipedrive

class TestCRMTools(unittest.TestCase):

    def setUp(self):
        self.salesforce = Salesforce(api_key='test_salesforce_key')
        self.hubspot = HubSpot(api_key='test_hubspot_key')
        self.pipedrive = Pipedrive(api_key='test_pipedrive_key')

    def test_salesforce_integration(self):
        # Test Salesforce data retrieval
        contact = self.salesforce.get_contact(contact_id='12345')
        self.assertIsNotNone(contact)
        self.assertEqual(contact['id'], '12345')

    def test_hubspot_integration(self):
        # Test HubSpot contact creation
        contact_data = {'email': 'test@example.com', 'firstname': 'Test', 'lastname': 'User'}
        contact = self.hubspot.create_contact(contact_data)
        self.assertIsNotNone(contact)
        self.assertEqual(contact['email'], 'test@example.com')

    def test_pipedrive_integration(self):
        # Test Pipedrive deal creation
        deal_data = {'title': 'Test Deal', 'value': 1000}
        deal = self.pipedrive.create_deal(deal_data)
        self.assertIsNotNone(deal)
        self.assertEqual(deal['title'], 'Test Deal')

if __name__ == '__main__':
    unittest.main()