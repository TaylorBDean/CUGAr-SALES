from pydantic import BaseModel, EmailStr
from typing import Optional

class Lead(BaseModel):
    id: str
    name: str
    email: EmailStr
    phone: Optional[str] = None
    company: Optional[str] = None
    status: str
    created_at: str
    updated_at: str

    class Config:
        schema_extra = {
            "example": {
                "id": "lead_123",
                "name": "John Doe",
                "email": "john.doe@example.com",
                "phone": "+1234567890",
                "company": "Example Corp",
                "status": "New",
                "created_at": "2023-01-01T12:00:00Z",
                "updated_at": "2023-01-01T12:00:00Z",
            }
        }