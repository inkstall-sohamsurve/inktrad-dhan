"""
Authentication router for user registration, login, and DHAN credentials management.
"""
from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timedelta
from bson import ObjectId
from app.models.user import (
    UserCreate, UserLogin, UserResponse, Token, DhanCredentials
)
from app.core.security import (
    get_password_hash, verify_password, create_access_token,
    encrypt_data, decrypt_data
)
from app.db.database import Database
from app.api.deps import get_current_user
from app.models.user import UserInDB
from app.core.config import settings


router = APIRouter(prefix="/api/v2/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate):
    """
    Register a new user.
    
    - **username**: Unique username (3-50 characters)
    - **email**: Valid email address
    - **password**: Password (minimum 8 characters)
    """
    users_collection = Database.get_users_collection()
    
    # Check if username already exists
    existing_user = await users_collection.find_one({"username": user_data.username})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email already exists
    existing_email = await users_collection.find_one({"email": user_data.email})
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user document
    user_doc = {
        "username": user_data.username,
        "email": user_data.email,
        "hashed_password": get_password_hash(user_data.password),
        "dhan_client_id": None,
        "dhan_access_token": None,
        "created_at": datetime.utcnow()
    }
    
    # Insert into database
    result = await users_collection.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id
    
    # Return user response
    return UserResponse(
        id=str(result.inserted_id),
        username=user_data.username,
        email=user_data.email,
        created_at=user_doc["created_at"],
        has_dhan_credentials=False
    )


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    """
    Login with username and password to get JWT access token.
    
    - **username**: Your username
    - **password**: Your password
    """
    users_collection = Database.get_users_collection()
    
    # Find user by username
    user_doc = await users_collection.find_one({"username": credentials.username})
    
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not verify_password(credentials.password, user_doc["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token = create_access_token(
        data={
            "sub": user_doc["username"],
            "user_id": str(user_doc["_id"])
        }
    )
    
    return Token(access_token=access_token, token_type="bearer")


@router.post("/dhan-credentials", status_code=status.HTTP_200_OK)
async def add_dhan_credentials(
    credentials: DhanCredentials,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Add or update DHAN API credentials for the authenticated user.
    Credentials are encrypted before storage.
    
    - **dhan_client_id**: Your DHAN Client ID
    - **dhan_access_token**: Your DHAN Access Token
    """
    users_collection = Database.get_users_collection()
    
    # Encrypt credentials
    encrypted_client_id = encrypt_data(credentials.dhan_client_id)
    encrypted_access_token = encrypt_data(credentials.dhan_access_token)
    
    # Update user document
    await users_collection.update_one(
        {"_id": ObjectId(current_user.id)},
        {
            "$set": {
                "dhan_client_id": encrypted_client_id,
                "dhan_access_token": encrypted_access_token
            }
        }
    )
    
    return {
        "message": "DHAN credentials added successfully",
        "status": "success"
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: UserInDB = Depends(get_current_user)):
    """
    Get the current authenticated user's profile.
    """
    has_credentials = bool(current_user.dhan_client_id and current_user.dhan_access_token)
    
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        created_at=current_user.created_at,
        has_dhan_credentials=has_credentials
    )
