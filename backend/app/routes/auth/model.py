from pydantic import BaseModel, Field, EmailStr
from typing import Optional

class RegisterRequestModel(BaseModel):
    name: str = Field(..., min_length=1, description="User name")
    email: EmailStr
    password: str = Field(..., min_length=5, description="User password")

class LoginRequestModel(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, description="User password")

class AuthResponseModel(BaseModel):
    success: bool
    message: str
    authToken: Optional[str] = None
    user: Optional[dict] = None