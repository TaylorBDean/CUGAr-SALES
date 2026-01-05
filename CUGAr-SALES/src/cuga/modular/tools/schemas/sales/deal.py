from pydantic import BaseModel
from typing import List, Optional

class Deal(BaseModel):
    id: str
    name: str
    stage: str
    value: float
    associated_contacts: List[str]
    close_date: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        schema_extra = {
            "example": {
                "id": "deal_123",
                "name": "New Website Launch",
                "stage": "Negotiation",
                "value": 15000.00,
                "associated_contacts": ["contact_456", "contact_789"],
                "close_date": "2023-12-31",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-10T00:00:00Z"
            }
        }