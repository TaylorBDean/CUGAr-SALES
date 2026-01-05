from typing import Dict, Any
from cuga.modular.tools.sales.closing.pricing_engine import PricingEngine
from cuga.modular.tools.sales.closing.contract_handler import ContractHandler

class ProposalGenerator:
    def __init__(self, pricing_engine: PricingEngine, contract_handler: ContractHandler):
        self.pricing_engine = pricing_engine
        self.contract_handler = contract_handler

    def generate_proposal(self, client_info: Dict[str, Any], proposal_details: Dict[str, Any]) -> str:
        """
        Generate a tailored proposal for a client.

        Args:
            client_info (Dict[str, Any]): Information about the client.
            proposal_details (Dict[str, Any]): Details of the proposal including services, pricing, etc.

        Returns:
            str: The generated proposal document.
        """
        # Calculate pricing based on proposal details
        pricing = self.pricing_engine.calculate_pricing(proposal_details)

        # Create the proposal content
        proposal_content = f"Proposal for {client_info['name']}\n\n"
        proposal_content += "Details:\n"
        for key, value in proposal_details.items():
            proposal_content += f"{key}: {value}\n"
        proposal_content += f"\nTotal Pricing: {pricing}\n"

        # Optionally handle contract generation
        contract = self.contract_handler.create_contract(client_info, proposal_details)

        return proposal_content, contract

    def send_proposal(self, proposal: str, client_email: str) -> None:
        """
        Send the generated proposal to the client via email.

        Args:
            proposal (str): The proposal document to send.
            client_email (str): The email address of the client.
        """
        # Logic to send the proposal via email (implementation not shown)
        pass