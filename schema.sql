-- Antigravity Nexus V31 Schema
-- Sprint 1: Users, Portfolios, Trades

-- 1. Users Table (MVP: Single User 'local')
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, -- e.g. 'local' or email
    email TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Portfolios Table
CREATE TABLE IF NOT EXISTS portfolios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Trades Table
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL REFERENCES users(id),
    portfolio_id UUIDREFERENCES portfolios(id), -- Optional for now, can be NULL if just user-wide
    ticker TEXT NOT NULL,
    datetime TIMESTAMPTZ NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('BUY', 'SELL', 'ADD', 'REDUCE')),
    shares NUMERIC(12, 4) NOT NULL CHECK (shares >= 0),
    price NUMERIC(12, 4) NOT NULL CHECK (price >= 0),
    fee NUMERIC(12, 4) DEFAULT 0 CHECK (fee >= 0),
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_trades_user_ticker_dt ON trades (user_id, ticker, datetime DESC);

-- Seed Data (Optional)
INSERT INTO users (id, email) VALUES ('local', 'admin@nexus.ai') ON CONFLICT (id) DO NOTHING;
