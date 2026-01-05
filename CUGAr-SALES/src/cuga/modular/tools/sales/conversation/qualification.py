from cuga.schemas.sales.conversation import ConversationSchema
from cuga.schemas.sales.lead import LeadSchema

def qualify_lead(conversation_data: dict) -> dict:
    """
    Qualifies a lead based on the conversation data provided.
    
    Args:
        conversation_data (dict): The data from the conversation to analyze.
        
    Returns:
        dict: A dictionary containing the qualification status and relevant details.
    """
    # Example logic for lead qualification
    lead_info = extract_lead_info(conversation_data)
    qualification_status = assess_lead(lead_info)
    
    return {
        "lead_info": lead_info,
        "qualification_status": qualification_status
    }

def extract_lead_info(conversation_data: dict) -> LeadSchema:
    """
    Extracts lead information from the conversation data.
    
    Args:
        conversation_data (dict): The data from the conversation.
        
    Returns:
        LeadSchema: A structured representation of the lead information.
    """
    # Logic to extract lead information from conversation data
    return LeadSchema(
        name=conversation_data.get("name"),
        email=conversation_data.get("email"),
        phone=conversation_data.get("phone"),
        company=conversation_data.get("company"),
        status="qualified"  # Default status
    )

def assess_lead(lead_info: LeadSchema) -> str:
    """
    Assesses the lead based on predefined criteria.
    
    Args:
        lead_info (LeadSchema): The structured lead information.
        
    Returns:
        str: The qualification status of the lead.
    """
    # Example assessment logic
    if lead_info.status == "qualified":
        return "Lead is qualified."
    else:
        return "Lead is not qualified."