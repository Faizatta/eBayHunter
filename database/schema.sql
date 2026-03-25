-- eBay Product Hunter SaaS Database Schema
-- Compatible with PostgreSQL 14+

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(500) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'Free' CHECK (role IN ('Free', 'Basic', 'Pro', 'Admin')),
    search_limit INT NOT NULL DEFAULT 5,
    search_used INT NOT NULL DEFAULT 0,
    last_reset_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Search history table
CREATE TABLE search_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    keyword VARCHAR(500) NOT NULL,
    results JSONB,
    result_count INT DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_search_history_user_id ON search_history(user_id);
CREATE INDEX idx_search_history_created_at ON search_history(created_at);

-- Seed: default admin user (password: Admin@123)
INSERT INTO users (email, password_hash, role, search_limit, search_used)
VALUES (
    'admin@ebayhunter.com',
    'Admin@123',
    'Admin',
    999999,
    0
);
