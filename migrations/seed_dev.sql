-- Seed Setup for local/testing environment
INSERT INTO roles (name, description) VALUES
('SUPER_ADMIN', 'System top level administrator'),
('PAYROLL_ADMIN', 'Handles periods, results, mappings and reconciliation'),
('MANAGER', 'Team/Department manager with attendance access only'),
('EMPLOYEE', 'Standard employee')
ON CONFLICT DO NOTHING;

INSERT INTO work_domains (name, code) VALUES
('Maintenance', 'MAINT'),
('Security', 'SEC'),
('Administration', 'ADMIN')
ON CONFLICT DO NOTHING;

INSERT INTO pay_components (name, code, is_taxable, is_pensionable) VALUES
('Travel Expenses', 'TRAVEL_BUDGET', false, false),
('Seniority Bonus', 'SENIORITY_BONUS', true, true)
ON CONFLICT DO NOTHING;

INSERT INTO deduction_components (name, code, is_pre_tax) VALUES
('Pension Fund Ded.', 'PENSION_DEDUCTION', true)
ON CONFLICT DO NOTHING;
