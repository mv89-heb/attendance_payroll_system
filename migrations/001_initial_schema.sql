-- ==========================================
-- 1. Identity & Access
-- ==========================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE roles (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE employees (
    id BIGSERIAL PRIMARY KEY,
    employee_number VARCHAR(50) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(150) UNIQUE NOT NULL,
    active BOOLEAN DEFAULT TRUE NOT NULL,
    kiosk_pin_hash VARCHAR(255) NOT NULL,
    hire_date DATE NOT NULL,
    termination_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT chk_dates CHECK (termination_date IS NULL OR termination_date >= hire_date)
);

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    employee_id BIGINT REFERENCES employees(id) ON DELETE RESTRICT,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE user_roles (
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    role_id BIGINT REFERENCES roles(id) ON DELETE RESTRICT NOT NULL,
    PRIMARY KEY (user_id, role_id)
);

-- ==========================================
-- 2. Organization Layer
-- ==========================================

CREATE TABLE departments (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    manager_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE work_domains (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    code VARCHAR(20) UNIQUE NOT NULL,
    active BOOLEAN DEFAULT TRUE NOT NULL
);

CREATE TABLE employee_domains (
    id BIGSERIAL PRIMARY KEY,
    employee_id BIGINT REFERENCES employees(id) ON DELETE RESTRICT NOT NULL,
    domain_id BIGINT REFERENCES work_domains(id) ON DELETE RESTRICT NOT NULL,
    valid_from DATE NOT NULL,
    valid_until DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT chk_domain_dates CHECK (valid_until IS NULL OR valid_until >= valid_from)
);

-- ==========================================
-- 3. Calendar & Specials
-- ==========================================

CREATE TABLE calendar_days (
    id BIGSERIAL PRIMARY KEY,
    calendar_date DATE UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    day_type VARCHAR(50) NOT NULL,
    is_work_day BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- ==========================================
-- 4. Attendance punches
-- ==========================================

CREATE TABLE attendance_punches (
    id BIGSERIAL PRIMARY KEY,
    employee_id BIGINT REFERENCES employees(id) ON DELETE RESTRICT NOT NULL,
    domain_id BIGINT REFERENCES work_domains(id) ON DELETE RESTRICT NOT NULL,
    punch_type VARCHAR(10) NOT NULL,
    punched_at TIMESTAMP WITH TIME ZONE NOT NULL,
    work_date DATE NOT NULL,
    source VARCHAR(50) NOT NULL,
    integrity_status VARCHAR(50) DEFAULT 'VALID' NOT NULL,
    notes TEXT,
    created_by_user_id BIGINT REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT chk_punch_type CHECK (punch_type IN ('IN', 'OUT'))
);

CREATE TABLE attendance_corrections (
    id BIGSERIAL PRIMARY KEY,
    punch_id BIGINT REFERENCES attendance_punches(id) ON DELETE RESTRICT NOT NULL,
    user_id BIGINT REFERENCES users(id) ON DELETE RESTRICT NOT NULL,
    field_changed VARCHAR(100) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    reason TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE shifts (
    id BIGSERIAL PRIMARY KEY,
    employee_id BIGINT REFERENCES employees(id) ON DELETE RESTRICT NOT NULL,
    domain_id BIGINT REFERENCES work_domains(id) ON DELETE RESTRICT NOT NULL,
    shift_date DATE NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    break_minutes INTEGER DEFAULT 0 NOT NULL,
    status VARCHAR(30) DEFAULT 'PENDING' NOT NULL,
    source VARCHAR(50) DEFAULT 'AUTO' NOT NULL,
    notes TEXT,
    approved_by_user_id BIGINT REFERENCES users(id) ON DELETE RESTRICT,
    approved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT chk_shift_times CHECK (end_time IS NULL OR end_time > start_time),
    CONSTRAINT chk_break CHECK (break_minutes >= 0)
);

-- ==========================================
-- 5. Payroll Periods
-- ==========================================

CREATE TABLE payroll_periods (
    id BIGSERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(30) DEFAULT 'OPEN' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    locked_at TIMESTAMP WITH TIME ZONE,
    locked_by_user_id BIGINT REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT unique_year_month UNIQUE (year, month),
    CONSTRAINT chk_period_dates CHECK (end_date >= start_date)
);

-- ==========================================
-- 6. Timesheets Summary Model (Generic)
-- ==========================================

CREATE TABLE timesheet_entries (
    id BIGSERIAL PRIMARY KEY,
    payroll_period_id BIGINT REFERENCES payroll_periods(id) ON DELETE RESTRICT NOT NULL,
    employee_id BIGINT REFERENCES employees(id) ON DELETE RESTRICT NOT NULL,
    domain_id BIGINT REFERENCES work_domains(id) ON DELETE RESTRICT NOT NULL,
    work_date DATE NOT NULL,
    total_hours NUMERIC(6,2) DEFAULT 0.00 NOT NULL,
    status VARCHAR(30) DEFAULT 'DRAFT' NOT NULL,
    calculation_snapshot JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT unique_emp_date_domain UNIQUE (employee_id, work_date, domain_id)
);

CREATE TABLE timesheet_entry_items (
    id BIGSERIAL PRIMARY KEY,
    timesheet_entry_id BIGINT REFERENCES timesheet_entries(id) ON DELETE RESTRICT NOT NULL,
    component_type VARCHAR(50) NOT NULL,
    quantity NUMERIC(6,2) NOT NULL,
    unit VARCHAR(20) DEFAULT 'HOURS' NOT NULL,
    multiplier NUMERIC(5,2) DEFAULT 1.00 NOT NULL,
    source VARCHAR(50) DEFAULT 'SYSTEM' NOT NULL,
    calculation_rule_snapshot JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- ==========================================
-- 7. Configuration Models
-- ==========================================

CREATE TABLE employee_pay_rates (
    id BIGSERIAL PRIMARY KEY,
    employee_id BIGINT REFERENCES employees(id) ON DELETE RESTRICT NOT NULL,
    domain_id BIGINT REFERENCES work_domains(id) ON DELETE RESTRICT,
    hourly_rate NUMERIC(12,4) NOT NULL,
    valid_from DATE NOT NULL,
    valid_until DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT chk_hourly_rate CHECK (hourly_rate >= 0),
    CONSTRAINT chk_rate_dates CHECK (valid_until IS NULL OR valid_until >= valid_from)
);

CREATE TABLE pay_rules (
    id BIGSERIAL PRIMARY KEY,
    rule_name VARCHAR(100) NOT NULL,
    rule_type VARCHAR(50) NOT NULL,
    conditions JSONB NOT NULL,
    multiplier NUMERIC(5,2) DEFAULT 1.00 NOT NULL,
    fixed_amount NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    effective_from DATE NOT NULL,
    effective_to DATE,
    priority INTEGER DEFAULT 1 NOT NULL,
    version INTEGER DEFAULT 1 NOT NULL,
    source VARCHAR(100) DEFAULT 'LAW' NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE pay_components (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    is_taxable BOOLEAN DEFAULT TRUE NOT NULL,
    is_pensionable BOOLEAN DEFAULT TRUE NOT NULL,
    active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE employee_pay_components (
    id BIGSERIAL PRIMARY KEY,
    employee_id BIGINT REFERENCES employees(id) ON DELETE RESTRICT NOT NULL,
    component_id BIGINT REFERENCES pay_components(id) ON DELETE RESTRICT NOT NULL,
    value NUMERIC(12,4) NOT NULL,
    calculation_type VARCHAR(50) NOT NULL,
    valid_from DATE NOT NULL,
    valid_until DATE,
    conditions JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT chk_pay_comp_dates CHECK (valid_until IS NULL OR valid_until >= valid_from)
);

CREATE TABLE deduction_components (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    is_pre_tax BOOLEAN DEFAULT TRUE NOT NULL,
    active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE employee_deduction_components (
    id BIGSERIAL PRIMARY KEY,
    employee_id BIGINT REFERENCES employees(id) ON DELETE RESTRICT NOT NULL,
    deduction_id BIGINT REFERENCES deduction_components(id) ON DELETE RESTRICT NOT NULL,
    value NUMERIC(12,4) NOT NULL,
    calculation_type VARCHAR(50) NOT NULL,
    valid_from DATE NOT NULL,
    valid_until DATE,
    conditions JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT chk_ded_comp_dates CHECK (valid_until IS NULL OR valid_until >= valid_from)
);

-- ==========================================
-- 8. Payroll results
-- ==========================================

CREATE TABLE payroll_runs (
    id BIGSERIAL PRIMARY KEY,
    payroll_period_id BIGINT REFERENCES payroll_periods(id) ON DELETE RESTRICT NOT NULL,
    version INTEGER DEFAULT 1 NOT NULL,
    status VARCHAR(30) DEFAULT 'DRAFT' NOT NULL,
    created_by_user_id BIGINT REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    locked_at TIMESTAMP WITH TIME ZONE,
    locked_by_user_id BIGINT REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT unique_period_version UNIQUE (payroll_period_id, version)
);

CREATE TABLE payroll_results (
    id BIGSERIAL PRIMARY KEY,
    payroll_run_id BIGINT REFERENCES payroll_runs(id) ON DELETE RESTRICT NOT NULL,
    employee_id BIGINT REFERENCES employees(id) ON DELETE RESTRICT NOT NULL,
    total_gross NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    total_deductions NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    total_net NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    calculations_snapshot JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT unique_run_employee UNIQUE (payroll_run_id, employee_id)
);

CREATE TABLE payroll_result_items (
    id BIGSERIAL PRIMARY KEY,
    payroll_result_id BIGINT REFERENCES payroll_results(id) ON DELETE RESTRICT NOT NULL,
    component_type VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    quantity NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    unit VARCHAR(20) DEFAULT 'HOURS' NOT NULL,
    rate NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    multiplier NUMERIC(5,2) DEFAULT 1.00 NOT NULL,
    amount NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    source VARCHAR(50) DEFAULT 'SYSTEM' NOT NULL,
    rule_snapshot JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE payroll_run_actions (
    id BIGSERIAL PRIMARY KEY,
    payroll_run_id BIGINT REFERENCES payroll_runs(id) ON DELETE RESTRICT NOT NULL,
    user_id BIGINT REFERENCES users(id) ON DELETE RESTRICT NOT NULL,
    action VARCHAR(50) NOT NULL,
    version INTEGER NOT NULL,
    ip_address VARCHAR(45),
    performed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- ==========================================
-- 9. Payslips
-- ==========================================

CREATE TABLE payslips (
    id BIGSERIAL PRIMARY KEY,
    employee_id BIGINT REFERENCES employees(id) ON DELETE RESTRICT NOT NULL,
    payroll_period_id BIGINT REFERENCES payroll_periods(id) ON DELETE RESTRICT NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    upload_status VARCHAR(50) DEFAULT 'PENDING' NOT NULL,
    parsed_data JSONB,
    confidence_score NUMERIC(5,2),
    verified_by_user_id BIGINT REFERENCES users(id) ON DELETE RESTRICT,
    verified_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT unique_employee_period_payslip UNIQUE (employee_id, payroll_period_id)
);

CREATE TABLE payslip_components (
    id BIGSERIAL PRIMARY KEY,
    payslip_id BIGINT REFERENCES payslips(id) ON DELETE RESTRICT NOT NULL,
    original_name VARCHAR(150) NOT NULL,
    category VARCHAR(50) NOT NULL,
    quantity NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    unit_rate NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    amount NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    source VARCHAR(50) DEFAULT 'OCR' NOT NULL,
    confidence NUMERIC(5,2),
    verified_value NUMERIC(12,4),
    verification_status VARCHAR(50) DEFAULT 'UNVERIFIED' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE payslip_component_mappings (
    id BIGSERIAL PRIMARY KEY,
    original_name VARCHAR(150) UNIQUE NOT NULL,
    normalized_name VARCHAR(150) NOT NULL,
    mapped_to_component_id BIGINT REFERENCES pay_components(id) ON DELETE RESTRICT,
    mapped_to_deduction_id BIGINT REFERENCES deduction_components(id) ON DELETE RESTRICT,
    verified_by_user_id BIGINT REFERENCES users(id) ON DELETE RESTRICT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- ==========================================
-- 10. Reconciliation
-- ==========================================

CREATE TABLE payroll_reconciliations (
    id BIGSERIAL PRIMARY KEY,
    payroll_result_id BIGINT REFERENCES payroll_results(id) ON DELETE RESTRICT NOT NULL,
    payslip_id BIGINT REFERENCES payslips(id) ON DELETE RESTRICT NOT NULL,
    total_gross_diff NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    total_net_diff NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    reconciliation_status VARCHAR(50) DEFAULT 'UNREVIEWED' NOT NULL,
    reviewed_by_user_id BIGINT REFERENCES users(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT unique_reconciliation UNIQUE (payroll_result_id, payslip_id)
);

CREATE TABLE payroll_reconciliation_items (
    id BIGSERIAL PRIMARY KEY,
    reconciliation_id BIGINT REFERENCES payroll_reconciliations(id) ON DELETE RESTRICT NOT NULL,
    component_name VARCHAR(150) NOT NULL,
    system_quantity NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    payslip_quantity NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    quantity_diff NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    system_rate NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    payslip_rate NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    rate_diff NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    system_amount NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    payslip_amount NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    amount_diff NUMERIC(12,4) DEFAULT 0.0000 NOT NULL,
    status VARCHAR(50) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- ==========================================
-- 11. Security Audit & File Metadata
-- ==========================================

CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE RESTRICT,
    action VARCHAR(100) NOT NULL,
    target_table VARCHAR(100) NOT NULL,
    target_id BIGINT NOT NULL,
    before_state JSONB,
    after_state JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE stored_files (
    id BIGSERIAL PRIMARY KEY,
    file_uuid UUID DEFAULT gen_random_uuid() UNIQUE NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    created_by_user_id BIGINT REFERENCES users(id) ON DELETE RESTRICT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);
