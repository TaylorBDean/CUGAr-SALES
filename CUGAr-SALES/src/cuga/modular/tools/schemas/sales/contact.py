from pydantic import BaseModel, EmailStr

class Contact(BaseModel):
    email: EmailStr
    phone_number: str
    associated_company: str

    class Config:
        schema_extra = {
            "example": {
                "email": "john.doe@example.com",
                "phone_number": "+1234567890",
                "associated_company": "Example Corp"
            }
        }