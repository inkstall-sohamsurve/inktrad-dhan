"""
Security utilities for authentication, password hashing, and encryption.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet
from fastapi import HTTPException, status
from app.core.config import settings


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Encryption cipher for DHAN credentials
cipher_suite = Fernet(settings.ENCRYPTION_KEY.encode())


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def encrypt_data(data: str) -> str:
    """Encrypt sensitive data (like DHAN credentials)."""
    if not data:
        return ""
    encrypted = cipher_suite.encrypt(data.encode())
    return encrypted.decode()


def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data."""
    if not encrypted_data:
        return ""
    try:
        decrypted = cipher_suite.decrypt(encrypted_data.encode())
        return decrypted.decode()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to decrypt data: {str(e)}"
        )


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary containing claims to encode in the token
        expires_delta: Optional expiration time delta
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a JWT access token.
    
    Args:
        token: JWT token string
        
    Returns:
        Dictionary containing the decoded claims
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
