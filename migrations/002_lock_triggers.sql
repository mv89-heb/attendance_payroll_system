-- =========================================================================
-- TRIGGER FUNCTION: Prevent Locked Payroll modifications (DB-level Enforcement)
-- =========================================================================

CREATE OR REPLACE FUNCTION fn_prevent_locked_modifications()
RETURNS TRIGGER AS $$
DECLARE
    v_period_status VARCHAR(30);
    v_period_id BIGINT;
    v_target_record RECORD;
BEGIN
    IF (TG_OP = 'DELETE') THEN
        v_target_record := OLD;
    ELSE
        v_target_record := NEW;
    END IF;

    IF TG_TABLE_NAME = 'timesheet_entries' THEN
        v_period_id := v_target_record.payroll_period_id;
    ELSIF TG_TABLE_NAME = 'timesheet_entry_items' THEN
        SELECT payroll_period_id INTO v_period_id FROM timesheet_entries 
        WHERE id = v_target_record.timesheet_entry_id;
    ELSIF TG_TABLE_NAME = 'shifts' THEN
        SELECT id INTO v_period_id FROM payroll_periods 
        WHERE v_target_record.shift_date BETWEEN start_date AND end_date;
    ELSIF TG_TABLE_NAME = 'attendance_punches' THEN
        SELECT id INTO v_period_id FROM payroll_periods 
        WHERE v_target_record.work_date BETWEEN start_date AND end_date;
    ELSIF TG_TABLE_NAME = 'payroll_results' THEN
        SELECT payroll_period_id INTO v_period_id FROM payroll_runs 
        WHERE id = v_target_record.payroll_run_id;
    ELSIF TG_TABLE_NAME = 'payroll_result_items' THEN
        SELECT pr.payroll_period_id INTO v_period_id 
        FROM payroll_results res
        JOIN payroll_runs pr ON res.payroll_run_id = pr.id
        WHERE res.id = v_target_record.payroll_result_id;
    END IF;

    IF v_period_id IS NOT NULL THEN
        SELECT status INTO v_period_status FROM payroll_periods WHERE id = v_period_id;
        IF v_period_status = 'LOCKED' THEN
            RAISE EXCEPTION 'MIGRATION_LOCK_ERROR: Period is locked. Modifications are strictly forbidden.';
        END IF;
    END IF;

    IF (TG_OP = 'DELETE') THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_lock_shifts ON shifts;
CREATE TRIGGER trg_lock_shifts
BEFORE INSERT OR UPDATE OR DELETE ON shifts
FOR EACH ROW EXECUTE FUNCTION fn_prevent_locked_modifications();

DROP TRIGGER IF EXISTS trg_lock_punches ON attendance_punches;
CREATE TRIGGER trg_lock_punches
BEFORE INSERT OR UPDATE OR DELETE ON attendance_punches
FOR EACH ROW EXECUTE FUNCTION fn_prevent_locked_modifications();

DROP TRIGGER IF EXISTS trg_lock_timesheet_entries ON timesheet_entries;
CREATE TRIGGER trg_lock_timesheet_entries
BEFORE INSERT OR UPDATE OR DELETE ON timesheet_entries
FOR EACH ROW EXECUTE FUNCTION fn_prevent_locked_modifications();

DROP TRIGGER IF EXISTS trg_lock_timesheet_entry_items ON timesheet_entry_items;
CREATE TRIGGER trg_lock_timesheet_entry_items
BEFORE INSERT OR UPDATE OR DELETE ON timesheet_entry_items
FOR EACH ROW EXECUTE FUNCTION fn_prevent_locked_modifications();

DROP TRIGGER IF EXISTS trg_lock_payroll_results ON payroll_results;
CREATE TRIGGER trg_lock_payroll_results
BEFORE INSERT OR UPDATE OR DELETE ON payroll_results
FOR EACH ROW EXECUTE FUNCTION fn_prevent_locked_modifications();

DROP TRIGGER IF EXISTS trg_lock_payroll_result_items ON payroll_result_items;
CREATE TRIGGER trg_lock_payroll_result_items
BEFORE INSERT OR UPDATE OR DELETE ON payroll_result_items
FOR EACH ROW EXECUTE FUNCTION fn_prevent_locked_modifications();
