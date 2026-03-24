-- eBay Hunter SaaS — PostgreSQL Schema
-- No daily reset: searches are a permanent pool that admin tops up

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE users (
    id            UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(500) NOT NULL,
    role          VARCHAR(20)  NOT NULL DEFAULT 'Free'
                  CHECK (role IN ('Free', 'Basic', 'Pro', 'Admin')),
    search_limit  INT          NOT NULL DEFAULT 5,   -- total searches allocated
    search_used   INT          NOT NULL DEFAULT 0,   -- total searches consumed
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE search_history (
    id           UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    keyword      VARCHAR(500) NOT NULL,
    results      JSONB,
    result_count INT          DEFAULT 0,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email            ON users(email);
CREATE INDEX idx_search_history_user    ON search_history(user_id);
CREATE INDEX idx_search_history_created ON search_history(created_at);

-- Default admin (password: Admin@123)
INSERT INTO users (email, password_hash, role, search_limit, search_used)
VALUES (
    'admin@ebayhunter.com',
    '$2a$11$rBnl.OkGQHsqK9lBPBsMKuGHl0sXM0v9e1QJfNsD2JL4o9YyZGSGe',
    'Admin', 999999, 0
);
