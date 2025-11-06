"""
Pydantic models for User entity.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
    
    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


class UserBase(BaseModel):
    """Base user model with common fields."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    """Model for user registration."""
    password: str = Field(..., min_length=8, max_length=100)


class UserLogin(BaseModel):
    """Model for user login."""
    username: str
    password: str


class DhanCredentials(BaseModel):
    """Model for storing DHAN API credentials."""
    dhan_client_id: str = Field(..., min_length=1)
    dhan_access_token: str = Field(..., min_length=1)


class UserInDB(UserBase):
    """User model as stored in database."""
    id: str = Field(alias="_id")
    hashed_password: str
    dhan_client_id: Optional[str] = None
    dhan_access_token: Optional[str] = None
    created_at: datetime
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}


class UserResponse(UserBase):
    """User model for API responses (excludes sensitive data)."""
    id: str
    created_at: datetime
    has_dhan_credentials: bool = False
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT token response model."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Data extracted from JWT token."""
    username: Optional[str] = None
    user_id: Optional[str] = None
