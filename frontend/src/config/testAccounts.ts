export interface TestAccount {
  label: string;
  email: string;
  role: 'HR' | 'EMPLOYEE' | 'ADMIN';
  password: string;
}

export const TEST_ACCOUNTS: TestAccount[] = [
  { label: 'Admin (ReloPass)', email: 'admin@relopass.com', role: 'ADMIN', password: 'Passw0rd!' },
  { label: 'HR Manager', email: 'hr@relopass.com', role: 'HR', password: 'Passw0rd!' },
  { label: 'Employee: Sarah J.', email: 'sarah@relopass.com', role: 'EMPLOYEE', password: 'employee123' },
  { label: 'Employee: Demo', email: 'employee@relopass.com', role: 'EMPLOYEE', password: 'employee123' },
  { label: 'Employee: Test (policy)', email: 'testEMPtest@relopass.com', role: 'EMPLOYEE', password: 'Passw0rd!' },
];
