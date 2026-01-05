from unittest import TestCase
from src.cuga.modular.tools.sales.crm.salesforce import Salesforce
from src.cuga.modular.tools.sales.enrichment.clearbit import Clearbit
from src.cuga.modular.tools.sales.outreach.email_provider import EmailProvider
from src.cuga.modular.tools.sales.conversation.chat_interface import ChatInterface
from src.cuga.modular.tools.sales.closing.proposal_generator import ProposalGenerator

class TestIntegrationScenarios(TestCase):

    def setUp(self):
        self.salesforce = Salesforce()
        self.clearbit = Clearbit()
        self.email_provider = EmailProvider()
        self.chat_interface = ChatInterface()
        self.proposal_generator = ProposalGenerator()

    def test_crm_integration(self):
        contact_data = self.salesforce.get_contact('test@example.com')
        self.assertIsNotNone(contact_data)

    def test_data_enrichment(self):
        enriched_data = self.clearbit.enrich('test@example.com')
        self.assertIn('company', enriched_data)
        self.assertIn('role', enriched_data)

    def test_email_outreach(self):
        response = self.email_provider.send_email('test@example.com', 'Subject', 'Body')
        self.assertTrue(response['success'])

    def test_chat_interface(self):
        response = self.chat_interface.send_message('Hello, how can I help you?')
        self.assertEqual(response['status'], 'sent')

    def test_proposal_generation(self):
        proposal = self.proposal_generator.generate_proposal('test@example.com', 'Proposal Title')
        self.assertIn('proposal_id', proposal)