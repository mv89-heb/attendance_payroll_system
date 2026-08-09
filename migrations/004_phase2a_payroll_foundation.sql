-- =========================================================================
-- MIGRATION: 004_phase2a_payroll_foundation.sql
-- =========================================================================

-- 1. Create employee_employment_terms table (Historical Terms)
CREATE TABLE IF NOT EXISTS employee_employment_terms (
    id BIGSERIAL PRIMARY KEY,
    employee_id BIGINT REFERENCES employees(id) ON DELETE RESTRICT NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE, -- NULL indicates active without an end date
    employment_type VARCHAR(50) NOT NULL, -- 'HOURLY', 'SALARIED'
    base_salary NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    hourly_rate NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    monthly_hours NUMERIC(6,2) DEFAULT 0.00 NOT NULL,
    travel_rate NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT chk_term_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT chk_base_salary CHECK (base_salary >= 0),
    CONSTRAINT chk_hourly_rate_term CHECK (hourly_rate >= 0),
    CONSTRAINT chk_monthly_hours CHECK (monthly_hours >= 0),
    CONSTRAINT chk_travel_rate CHECK (travel_rate >= 0)
);

-- Indexing for performance
CREATE INDEX IF NOT EXISTS idx_emp_terms_lookup ON employee_employment_terms(employee_id, effective_from, effective_to);

-- 2. Trigger Function: Prevent changes to employment terms overlapping with locked periods (DB Immutability)
CREATE OR REPLACE FUNCTION fn_prevent_locked_employment_terms_modifications()
RETURNS TRIGGER AS $$
DECLARE
    v_locked_period_exists BOOLEAN;
    v_target_record RECORD;
BEGIN
    IF (TG_OP = 'DELETE') THEN
        v_target_record := OLD;
    ELSE
        v_target_record := NEW;
    END IF;

    -- Check if any locked payroll period overlaps with this employment term period
    SELECT EXISTS (
        SELECT 1 FROM payroll_periods
        WHERE status = 'LOCKED'
          AND (start_date, end_date) OVERLAPS (v_target_record.effective_from, COALESCE(v_target_record.effective_to, '9999-12-31'::date))
    ) INTO v_locked_period_exists;

    IF v_locked_period_exists THEN
        RAISE EXCEPTION 'MIGRATION_LOCK_ERROR: Cannot modify employment terms that overlap with a locked payroll period.';
    END IF;

    IF (TG_OP = 'DELETE') THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_lock_employment_terms ON employee_employment_terms;
CREATE TRIGGER trg_lock_employment_terms
BEFORE INSERT OR UPDATE OR DELETE ON employee_employment_terms
FOR EACH ROW EXECUTE FUNCTION fn_prevent_locked_employment_terms_modifications();
