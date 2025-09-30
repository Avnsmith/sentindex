-- Initialize Sentindex database
-- This script runs when the TimescaleDB container starts

-- Create database if it doesn't exist
SELECT 'CREATE DATABASE sentindex'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'sentindex')\gexec

-- Connect to the sentindex database
\c sentindex;

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create index_values table
CREATE TABLE IF NOT EXISTS index_values (
    time TIMESTAMPTZ NOT NULL,
    index_name TEXT NOT NULL,
    index_value NUMERIC NOT NULL,
    method TEXT NOT NULL,
    delta_24h_pct NUMERIC,
    payload JSONB,
    PRIMARY KEY (time, index_name)
);

-- Create hypertable
SELECT create_hypertable('index_values', 'time', if_not_exists => TRUE);

-- Create index configurations table
CREATE TABLE IF NOT EXISTS index_configs (
    name TEXT PRIMARY KEY,
    config JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create insights table
CREATE TABLE IF NOT EXISTS insights (
    id SERIAL PRIMARY KEY,
    index_name TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    insights JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create data sources table
CREATE TABLE IF NOT EXISTS data_sources (
    source TEXT NOT NULL,
    symbol TEXT NOT NULL,
    last_update TIMESTAMPTZ,
    status TEXT DEFAULT 'unknown',
    confidence NUMERIC DEFAULT 0.0,
    PRIMARY KEY (source, symbol)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_index_values_name_time 
ON index_values (index_name, time DESC);

CREATE INDEX IF NOT EXISTS idx_insights_name_time 
ON insights (index_name, timestamp DESC);

-- Insert default index configuration
INSERT INTO index_configs (name, config) VALUES (
    'gold_silver_oil_crypto',
    '{
        "name": "Gold-Silver-Oil-Crypto Index",
        "base_level": 1000.0,
        "base_date": "2025-01-01",
        "weights": {
            "GOLD": 0.25,
            "SILVER": 0.25,
            "OIL": 0.20,
            "BTC": 0.15,
            "ETH": 0.15
        },
        "base_prices": {
            "GOLD": 1800.0,
            "SILVER": 23.0,
            "OIL": 75.0,
            "BTC": 20000.0,
            "ETH": 1000.0
        }
    }'
) ON CONFLICT (name) DO NOTHING;

-- Create retention policy (keep data for 1 year)
SELECT add_retention_policy('index_values', INTERVAL '1 year', if_not_exists => TRUE);

-- Create compression policy (compress data older than 7 days)
SELECT add_compression_policy('index_values', INTERVAL '7 days', if_not_exists => TRUE);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO sentindex;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO sentindex;
