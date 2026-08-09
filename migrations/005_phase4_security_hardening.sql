-- =========================================================================
-- MIGRATION: 005_phase4_security_hardening.sql
-- =========================================================================

-- 1. Create kiosk failed attempts table for brute-force protection
CREATE TABLE IF NOT EXISTS kiosk_failed_attempts (
    employee_number VARCHAR(50) PRIMARY KEY,
    failed_count INTEGER DEFAULT 0 NOT NULL,
    locked_until TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Indexing for quick lookups
CREATE INDEX IF NOT EXISTS idx_kiosk_failed_lookup ON kiosk_failed_attempts(employee_number);