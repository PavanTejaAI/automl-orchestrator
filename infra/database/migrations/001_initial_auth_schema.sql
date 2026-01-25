CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    email_hash VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email_hash ON users USING hash(email_hash);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_users_created ON users(created_at);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    is_revoked BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    last_used_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires ON refresh_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens USING hash(token_hash);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_revoked ON refresh_tokens(is_revoked) WHERE is_revoked = false;

CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    access_token_jti VARCHAR(255) UNIQUE,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    is_revoked BOOLEAN DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_jti ON user_sessions USING hash(access_token_jti);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON user_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_sessions_revoked ON user_sessions(is_revoked) WHERE is_revoked = false;

ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS users_select_policy ON users
    FOR SELECT
    USING (true);

CREATE POLICY IF NOT EXISTS users_insert_policy ON users
    FOR INSERT
    WITH CHECK (true);

CREATE POLICY IF NOT EXISTS users_update_policy ON users
    FOR UPDATE
    USING (id = current_setting('app.user_id', true)::uuid);

CREATE POLICY IF NOT EXISTS users_delete_policy ON users
    FOR DELETE
    USING (id = current_setting('app.user_id', true)::uuid);

ALTER TABLE refresh_tokens ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS refresh_tokens_select_policy ON refresh_tokens
    FOR SELECT
    USING (user_id = current_setting('app.user_id', true)::uuid);

CREATE POLICY IF NOT EXISTS refresh_tokens_insert_policy ON refresh_tokens
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.user_id', true)::uuid);

CREATE POLICY IF NOT EXISTS refresh_tokens_delete_policy ON refresh_tokens
    FOR DELETE
    USING (user_id = current_setting('app.user_id', true)::uuid);

ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS sessions_select_policy ON user_sessions
    FOR SELECT
    USING (user_id = current_setting('app.user_id', true)::uuid);

CREATE POLICY IF NOT EXISTS sessions_insert_policy ON user_sessions
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.user_id', true)::uuid);

CREATE POLICY IF NOT EXISTS sessions_delete_policy ON user_sessions
    FOR DELETE
    USING (user_id = current_setting('app.user_id', true)::uuid);
