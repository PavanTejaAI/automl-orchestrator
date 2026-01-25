from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncpg
from src.auth.jwt import verify_token
from src.auth.service import get_user_by_id
from src.database import get_db
from src.utils import logger

security = HTTPBearer()


def _raise_unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _parse_user_id(user_id_str: Optional[str]) -> UUID:
    if not user_id_str:
        raise _raise_unauthorized("Invalid token payload")
    
    try:
        return UUID(user_id_str)
    except ValueError:
        raise _raise_unauthorized("Invalid user ID format")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: asyncpg.Connection = Depends(get_db)
) -> dict:
    token = credentials.credentials
    
    payload = verify_token(token)
    if not payload:
        raise _raise_unauthorized("Invalid authentication credentials")
    
    user_id = _parse_user_id(payload.get("sub"))
    
    user = await get_user_by_id(db, user_id)
    if not user:
        raise _raise_unauthorized("User not found")
    
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    
    return user


async def get_current_active_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    return current_user


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    return request.headers.get("User-Agent", "unknown")
