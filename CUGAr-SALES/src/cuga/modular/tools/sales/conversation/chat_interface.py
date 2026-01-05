from cuga.modular.tools.sales.conversation.qualification import qualify_lead
from cuga.modular.schemas.sales.conversation import ConversationSchema

class ChatInterface:
    def __init__(self):
        self.conversation_history = []

    def add_message(self, message: str, sender: str):
        self.conversation_history.append({"message": message, "sender": sender})

    def get_conversation_history(self):
        return self.conversation_history

    def qualify_lead(self, user_input: str) -> dict:
        lead_info = qualify_lead(user_input)
        return lead_info

    def reset_conversation(self):
        self.conversation_history = []