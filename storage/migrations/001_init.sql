-- ============================================================================
-- UPSC Mentor AI — PostgreSQL Schema (001_init)
-- ============================================================================
-- Run this against your production Postgres instance once you're ready to
-- move off the SQLite testing storage (see storage/database.py DB_ENGINE).
-- Designed to sit alongside the main UPSC Master Bot's DB, not replace it —
-- users.user_id is the Telegram ID and is the join key if you later want to
-- correlate the two databases.

CREATE TABLE IF NOT EXISTS users (
    user_id           BIGINT PRIMARY KEY,           -- Telegram user id
    username          TEXT DEFAULT '',
    full_name         TEXT DEFAULT '',
    level             TEXT DEFAULT 'beginner',       -- beginner|intermediate|advanced
    timeline_months   INTEGER DEFAULT 6,
    phase             TEXT DEFAULT '',               -- foundation|revision|test-series etc.
    optional_subject  TEXT DEFAULT '',
    weak_subjects     JSONB DEFAULT '[]',
    turn_counter      INTEGER DEFAULT 0,             -- drives memory extraction cadence
    main_bot_linked   BOOLEAN DEFAULT FALSE,          -- true once linked to main bot's user
    created_at        TIMESTAMPTZ DEFAULT now(),
    updated_at        TIMESTAMPTZ DEFAULT now(),
    last_active       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    role        TEXT NOT NULL,                       -- 'user' | 'assistant'
    content     TEXT NOT NULL,
    feature     TEXT DEFAULT 'doubt',                 -- doubt|essay|evaluate|ethics|ca...
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_time ON chat_messages(user_id, created_at DESC);
-- Rolling window: application layer trims to last RECENT_CHAT_WINDOW per user
-- (or use a cron: DELETE old rows beyond N per user).

CREATE TABLE IF NOT EXISTS user_memories (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    category    TEXT NOT NULL,                       -- GOAL|WEAKNESS|STRENGTH|PATTERN|PREFERENCE
    fact        TEXT NOT NULL,
    confidence  REAL DEFAULT 1.0,
    active      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, category, fact)
);
CREATE INDEX IF NOT EXISTS idx_user_memories_active ON user_memories(user_id, active, updated_at DESC);

CREATE TABLE IF NOT EXISTS user_summaries (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    period      TEXT NOT NULL,                       -- 'weekly' | 'monthly'
    summary     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_user_summaries_user ON user_summaries(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS mentor_insights (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    insight_type TEXT NOT NULL,                      -- 'weekly_report'|'risk_flag'|'milestone'
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS study_progress (
    user_id         BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    streak          INTEGER DEFAULT 0,
    best_streak     INTEGER DEFAULT 0,
    days_done       INTEGER DEFAULT 0,
    answers_written INTEGER DEFAULT 0,
    mocks_taken     INTEGER DEFAULT 0,
    last_active     TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS performance_trends (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    metric      TEXT NOT NULL,                       -- 'answer_score'|'essay_score'|'ethics_score'
    value       REAL NOT NULL,
    subject     TEXT DEFAULT '',
    recorded_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_perf_trends_user_metric ON performance_trends(user_id, metric, recorded_at DESC);

CREATE TABLE IF NOT EXISTS uploaded_documents (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    doc_type    TEXT DEFAULT 'photo',                 -- photo|pdf
    extracted_text TEXT,
    related_feature TEXT DEFAULT '',                  -- answer_writing|essay
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS news_history (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    topic       TEXT NOT NULL,
    summary     TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id         BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    language        TEXT DEFAULT 'en',
    response_length TEXT DEFAULT 'standard',           -- brief|standard|detailed
    persona         TEXT DEFAULT 'default',             -- strict|friendly|strategy|answer_writing|default
    notify_weekly   BOOLEAN DEFAULT TRUE,
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analytics (
    id          BIGSERIAL PRIMARY KEY,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    recorded_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    event_type  TEXT NOT NULL,                        -- 'ai_call'|'evaluation'|'error'
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_type_time ON events(event_type, created_at DESC);

CREATE TABLE IF NOT EXISTS ai_sessions (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    feature         TEXT NOT NULL,                     -- doubt|essay|evaluate|ethics|ca_summary
    prompt_tokens   INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    finish_reason   TEXT DEFAULT '',                    -- watch for 'length'/'MAX_TOKENS'
    latency_ms      INTEGER DEFAULT 0,
    success         BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ai_sessions_feature_time ON ai_sessions(feature, created_at DESC);
-- This table is what would have caught the truncation bug immediately:
-- a spike in finish_reason='length' rows with tiny completion_tokens counts.
