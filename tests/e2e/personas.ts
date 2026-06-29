/**
 * Persona registry for the ReloPass v2.0 campaign.
 *
 * Identifiers (emails) are NON-secret config and live here. PASSWORDS are NEVER
 * stored here — each persona names the ENV VAR that supplies its password, which
 * YOU set in your shell before running `npm run auth`. Only two passwords are
 * needed: the TestCompany accounts share one, the *-demo accounts share another.
 */
export type Role = 'ADMIN' | 'HR' | 'EMPLOYEE';

export interface Persona {
  key: string;          // storageState file stem → playwright/.auth/<key>.json
  identifier: string;   // login email (non-secret)
  pwEnv: string;        // name of the env var holding the password
  role: Role;
  company?: string;
  name?: string;
  masterPersona?: string; // maps to v2.0 doc personas (A1/A2/H1/H2/E1..E5)
}

export const PERSONAS: Persona[] = [
  { key: 'admin',          identifier: 'admin@relopass.com',               pwEnv: 'PW_TESTCO', role: 'ADMIN',    company: 'TestCompany',      masterPersona: 'A1/A2' },
  { key: 'hr_tc',          identifier: 'hr@testcompany.com',               pwEnv: 'PW_TESTCO', role: 'HR',       company: 'TestCompany',      masterPersona: 'H1/H2' },
  { key: 'emp_tc',         identifier: 'employee@testcompany.com',         pwEnv: 'PW_TESTCO', role: 'EMPLOYEE', company: 'TestCompany',      masterPersona: 'E1' },
  { key: 'globaltech_hr',  identifier: 'hannah.hr@globaltech-demo.com',    pwEnv: 'PW_DEMO',   role: 'HR',       company: 'GlobalTech SAS',   name: 'Hannah Müller' },
  { key: 'globaltech_emp', identifier: 'adrien.martin@globaltech-demo.com',pwEnv: 'PW_DEMO',   role: 'EMPLOYEE', company: 'GlobalTech SAS',   name: 'Adrien Martin' },
  { key: 'meridian_hr',    identifier: 'sophie.hr@meridian-demo.com',      pwEnv: 'PW_DEMO',   role: 'HR',       company: 'Meridian Capital', name: 'Sophie Leclerc' },
  { key: 'meridian_emp',   identifier: 'celine.dupont@meridian-demo.com',  pwEnv: 'PW_DEMO',   role: 'EMPLOYEE', company: 'Meridian Capital', name: 'Céline Dupont' },
  { key: 'nexora_hr',      identifier: 'marta.hr@nexora-demo.com',         pwEnv: 'PW_DEMO',   role: 'HR',       company: 'Nexora Labs',      name: 'Marta García' },
  { key: 'nexora_emp',     identifier: 'carlos.rivera@nexora-demo.com',    pwEnv: 'PW_DEMO',   role: 'EMPLOYEE', company: 'Nexora Labs',      name: 'Carlos Rivera' },
];

export const byKey = (k: string): Persona => {
  const p = PERSONAS.find((x) => x.key === k);
  if (!p) throw new Error(`Unknown persona key: ${k}`);
  return p;
};
