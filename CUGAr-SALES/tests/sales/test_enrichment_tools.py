from unittest import TestCase
from src.cuga.modular.tools.sales.enrichment.clearbit import enrich_data as clearbit_enrich
from src.cuga.modular.tools.sales.enrichment.apollo import enrich_data as apollo_enrich
from src.cuga.modular.tools.sales.enrichment.zoominfo import enrich_data as zoominfo_enrich

class TestEnrichmentTools(TestCase):

    def test_clearbit_enrichment(self):
        # Test Clearbit enrichment functionality
        input_data = {"email": "test@example.com"}
        expected_output = {"company": "Example Corp", "role": "Developer"}  # Example expected output
        result = clearbit_enrich(input_data)
        self.assertEqual(result, expected_output)

    def test_apollo_enrichment(self):
        # Test Apollo enrichment functionality
        input_data = {"email": "test@example.com"}
        expected_output = {"company": "Example Corp", "role": "Developer"}  # Example expected output
        result = apollo_enrich(input_data)
        self.assertEqual(result, expected_output)

    def test_zoominfo_enrichment(self):
        # Test ZoomInfo enrichment functionality
        input_data = {"company_name": "Example Corp"}
        expected_output = {"tech_stack": ["React", "Node.js"], "funding": "Series A"}  # Example expected output
        result = zoominfo_enrich(input_data)
        self.assertEqual(result, expected_output)