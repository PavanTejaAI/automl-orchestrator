import hashlib
from typing import Optional
from uuid import UUID
import asyncpg
from src.utils import logger


def hash_email(email: str) -> str:
    return hashlib.sha256(email.lower().encode()).hexdigest()


async def create_tables(conn: asyncpg.Connection):
    await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    await conn.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email VARCHAR(255) NOT NULL,
            email_hash VARCHAR(64) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            name VARCHAR(255),
            is_active BOOLEAN DEFAULT true,
            is_verified BOOLEAN DEFAULT false,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_users_email_hash ON users USING hash(email_hash)')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active) WHERE is_active = true')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_users_created ON users(created_at)')
    
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash VARCHAR(255) NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NOT NULL,
            is_revoked BOOLEAN DEFAULT false,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            last_used_at TIMESTAMPTZ
        )
    """)
    
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id)')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires ON refresh_tokens(expires_at)')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens USING hash(token_hash)')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_refresh_tokens_revoked ON refresh_tokens(is_revoked) WHERE is_revoked = false')
    
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            access_token_jti VARCHAR(255) UNIQUE,
            ip_address VARCHAR(45),
            user_agent TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL,
            is_revoked BOOLEAN DEFAULT false
        )
    """)
    
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON user_sessions(user_id)')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_jti ON user_sessions USING hash(access_token_jti)')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_expires ON user_sessions(expires_at)')
    await conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_revoked ON user_sessions(is_revoked) WHERE is_revoked = false')
    
    await conn.execute('ALTER TABLE users ENABLE ROW LEVEL SECURITY')
    
    policies = [
        ('users_select_policy', 'users', 'SELECT', 'true', None),
        ('users_insert_policy', 'users', 'INSERT', None, 'true'),
        ('users_update_policy', 'users', 'UPDATE', "id = current_setting('app.user_id', true)::uuid", None),
        ('users_delete_policy', 'users', 'DELETE', "id = current_setting('app.user_id', true)::uuid", None),
        ('refresh_tokens_select_policy', 'refresh_tokens', 'SELECT', 'true', None),
        ('refresh_tokens_insert_policy', 'refresh_tokens', 'INSERT', None, "user_id = current_setting('app.user_id', true)::uuid"),
        ('refresh_tokens_delete_policy', 'refresh_tokens', 'DELETE', "user_id = current_setting('app.user_id', true)::uuid", None),
        ('sessions_select_policy', 'user_sessions', 'SELECT', "user_id = current_setting('app.user_id', true)::uuid", None),
        ('sessions_insert_policy', 'user_sessions', 'INSERT', None, "user_id = current_setting('app.user_id', true)::uuid"),
        ('sessions_delete_policy', 'user_sessions', 'DELETE', "user_id = current_setting('app.user_id', true)::uuid", None),
    ]
    
    for policy_name, table_name, command, using_clause, with_check_clause in policies:
        policy_exists = await conn.fetchval("""
            SELECT 1 FROM pg_policies 
            WHERE schemaname = 'public' 
            AND tablename = $1 
            AND policyname = $2
        """, table_name, policy_name)
        
        if not policy_exists:
            parts = []
            if using_clause:
                parts.append(f"USING ({using_clause})")
            if with_check_clause:
                parts.append(f"WITH CHECK ({with_check_clause})")
            
            policy_sql = f"""
                CREATE POLICY {policy_name} ON {table_name}
                FOR {command}
                {' '.join(parts)}
            """
            await conn.execute(policy_sql)
    
    await conn.execute('ALTER TABLE refresh_tokens ENABLE ROW LEVEL SECURITY')
    await conn.execute('ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY')
    
    logger.info("Database tables and security policies created")


async def set_user_context(conn: asyncpg.Connection, user_id: Optional[str]):
    if user_id:
        try:
            UUID(user_id)
            await conn.execute(f"SET LOCAL app.user_id = '{user_id}'")
        except ValueError:
            pass
    else:
        await conn.execute("RESET app.user_id")
