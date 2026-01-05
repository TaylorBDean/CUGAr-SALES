from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class Conversation(BaseModel):
    id: str
    participants: List[str]
    content: str
    timestamp: datetime
    duration: Optional[int]  # Duration in seconds
    context: Optional[dict]  # Additional context for the conversation

    class Config:
        schema_extra = {
            "example": {
                "id": "conv_12345",
                "participants": ["user_1", "agent_1"],
                "content": "Hello, how can I help you today?",
                "timestamp": "2023-10-01T12:00:00Z",
                "duration": 300,
                "context": {
                    "lead_id": "lead_123",
                    "intent": "inquiry"
                }
            }
        }