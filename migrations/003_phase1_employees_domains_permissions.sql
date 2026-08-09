-- =========================================================================
-- MIGRATION: 003_phase1_employees_domains_permissions.sql
-- =========================================================================

-- 1. Create permissions table
CREATE TABLE IF NOT EXISTS permissions (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- 2. Create role_permissions table
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id BIGINT REFERENCES roles(id) ON DELETE RESTRICT NOT NULL,
    permission_id BIGINT REFERENCES permissions(id) ON DELETE RESTRICT NOT NULL,
    PRIMARY KEY (role_id, permission_id)
);

CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role_id);

-- 3. Seed Base Permissions
INSERT INTO permissions (name, description) VALUES
('employees.view', 'צפייה ברשימת ופרטי עובדים'),
('employees.create', 'יצירת עובדים חדשים במערכת'),
('employees.edit', 'עריכת פרטי עובדים קיימים'),
('employees.deactivate', 'השבתה או הפעלה מחדש של עובד'),
('domains.view', 'צפייה בתחומי עבודה'),
('domains.create', 'יצירת תחומי עבודה חדשים'),
('domains.edit', 'עריכה ועדכון תחומי עבודה'),
('users.view', 'צפייה במשתמשי המערכת ותפקידיהם'),
('payroll.view', 'צפייה בנתוני שכר מחושבים'),
('payroll.manage', 'הרצה ונעילה של מחזורי שכר')
ON CONFLICT DO NOTHING;

-- 4. Map Permissions to Roles (RBAC Configuration)
-- Mapping for SUPER_ADMIN (All permissions)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'SUPER_ADMIN'
ON CONFLICT DO NOTHING;

-- Mapping for ADMIN (All except system super-admin configs)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'ADMIN' AND p.name IN (
    'employees.view', 'employees.create', 'employees.edit', 'employees.deactivate',
    'domains.view', 'domains.create', 'domains.edit', 'users.view', 'payroll.view', 'payroll.manage'
)
ON CONFLICT DO NOTHING;

-- Mapping for MANAGER (Read-only on staff, no payroll manage access)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'MANAGER' AND p.name IN ('employees.view', 'domains.view')
ON CONFLICT DO NOTHING;

-- Mapping for EMPLOYEE (Read-only personal limits)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'EMPLOYEE' AND p.name IN ('domains.view')
ON CONFLICT DO NOTHING;
