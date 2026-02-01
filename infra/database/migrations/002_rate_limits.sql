CREATE TABLE IF NOT EXISTS rate_limits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tool VARCHAR(100) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    request_count INTEGER DEFAULT 0,
    UNIQUE(user_id, tool, window_start)
);

CREATE INDEX IF NOT EXISTS idx_rate_limits_user_tool ON rate_limits(user_id, tool);
CREATE INDEX IF NOT EXISTS idx_rate_limits_window ON rate_limits(window_start);

ALTER TABLE rate_limits ENABLE ROW LEVEL SECURITY;

CREATE POLICY rate_limits_select_policy ON rate_limits
    FOR SELECT
    USING (user_id = current_setting('app.user_id', true)::uuid);

CREATE POLICY rate_limits_insert_policy ON rate_limits
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.user_id', true)::uuid);

CREATE POLICY rate_limits_update_policy ON rate_limits
    FOR UPDATE
    USING (user_id = current_setting('app.user_id', true)::uuid);
