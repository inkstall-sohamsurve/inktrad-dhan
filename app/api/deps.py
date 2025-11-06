"""
FastAPI dependencies for authentication and authorization.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from app.core.security import decode_access_token
from app.db.database import Database
from app.models.user import UserInDB, TokenData
from bson import ObjectId


# HTTP Bearer token security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserInDB:
    """
    Dependency to get the current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        UserInDB: Current authenticated user
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    
    # Decode JWT token
    payload = decode_access_token(token)
    
    username: Optional[str] = payload.get("sub")
    user_id: Optional[str] = payload.get("user_id")
    
    if username is None or user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Fetch user from database
    users_collection = Database.get_users_collection()
    user_doc = await users_collection.find_one({"_id": ObjectId(user_id)})
    
    if user_doc is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Convert MongoDB document to UserInDB model
    user_doc["_id"] = str(user_doc["_id"])
    return UserInDB(**user_doc)


async def get_current_user_with_dhan_credentials(
    current_user: UserInDB = Depends(get_current_user)
) -> UserInDB:
    """
    Dependency to ensure the current user has DHAN credentials configured.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        UserInDB: Current user with DHAN credentials
        
    Raises:
        HTTPException: If user doesn't have DHAN credentials
    """
    if not current_user.dhan_client_id or not current_user.dhan_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="DHAN credentials not configured. Please add your DHAN API credentials first."
        )
    
    return current_user
