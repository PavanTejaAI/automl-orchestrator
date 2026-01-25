from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from src.config import config
from src.utils import logger


def _create_token(data: dict, expires_delta: timedelta, token_type: str) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire, "type": token_type})
    return jwt.encode(to_encode, config.jwt_secret_key, algorithm=config.jwt_algorithm)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=config.jwt_access_token_expire_minutes)
    return _create_token(data, expires_delta, "access")


def create_refresh_token(data: dict) -> str:
    expires_delta = timedelta(days=config.jwt_refresh_token_expire_days)
    return _create_token(data, expires_delta, "refresh")


def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
    try:
        payload = jwt.decode(token, config.jwt_secret_key, algorithms=[config.jwt_algorithm])
        
        if payload.get("type") != token_type:
            logger.warning("Invalid token type", expected=token_type, got=payload.get("type"))
            return None
        
        return payload
    except JWTError as e:
        logger.warning("Token verification failed", error=str(e))
        return None
