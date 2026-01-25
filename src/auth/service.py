from typing import Optional
from uuid import UUID
import asyncpg
import hashlib
from src.auth.password import get_password_hash, verify_password, validate_password_strength
from src.config import config
from src.database.models import hash_email, set_user_context
from src.utils import logger

class EmailService:
    @staticmethod
    def normalize(email: str) -> str:
        return email.lower().strip()
    
    @staticmethod
    def hash(email: str) -> str:
        return hash_email(email)

class TokenService:
    @staticmethod
    def hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

class AuthService:
    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn
        self.email_service = EmailService()
        self.token_service = TokenService()
    
    async def create_user(self, email: str, password: str, name: Optional[str] = None) -> dict:
        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            raise ValueError(error_msg)
        
        email_normalized = self.email_service.normalize(email)
        email_hash = self.email_service.hash(email_normalized)
        
        existing_user = await self.conn.fetchrow(
            "SELECT id FROM users WHERE email_hash = $1",
            email_hash
        )
        
        if existing_user:
            raise ValueError("Email already registered")
        
        password_hash = get_password_hash(password)
        
        user_id = await self.conn.fetchval("""
            INSERT INTO users (email, email_hash, password_hash, name)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """, email_normalized, email_hash, password_hash, name)
        
        logger.info("User created", user_id=str(user_id), email=email_normalized)
        
        return {
            "id": str(user_id),
            "email": email_normalized,
            "name": name,
            "is_verified": False
        }
    
    async def authenticate_user(self, email: str, password: str) -> Optional[dict]:
        email_normalized = self.email_service.normalize(email)
        email_hash = self.email_service.hash(email_normalized)
        
        user = await self.conn.fetchrow("""
            SELECT id, email, password_hash, name, is_active, is_verified
            FROM users
            WHERE email_hash = $1
        """, email_hash)
        
        if not user:
            logger.warning("Login attempt with non-existent email", email=email_normalized)
            return None
        
        if not user["is_active"]:
            logger.warning("Login attempt with inactive account", user_id=str(user["id"]))
            return None
        
        if not verify_password(password, user["password_hash"]):
            logger.warning("Invalid password attempt", user_id=str(user["id"]))
            return None
        
        logger.info("User authenticated", user_id=str(user["id"]))
        
        return {
            "id": str(user["id"]),
            "email": user["email"],
            "name": user["name"],
            "is_verified": user["is_verified"]
        }
    
    async def store_session(self, user_id: UUID, access_token: str, refresh_token: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        from src.auth.jwt import verify_token
        
        payload = verify_token(access_token)
        jti = payload.get("jti") if payload else None
        token_hash = self.token_service.hash(refresh_token)
        
        await set_user_context(self.conn, str(user_id))
        
        await self.conn.execute(f"""
            INSERT INTO user_sessions (user_id, access_token_jti, ip_address, user_agent, expires_at)
            VALUES ($1, $2, $3, $4, NOW() + INTERVAL '{config.jwt_access_token_expire_minutes} minutes')
        """, user_id, jti, ip_address, user_agent)
        
        await self.conn.execute(f"""
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES ($1, $2, NOW() + INTERVAL '{config.jwt_refresh_token_expire_days} days')
            ON CONFLICT (token_hash) DO NOTHING
        """, user_id, token_hash)
        
        await set_user_context(self.conn, None)
