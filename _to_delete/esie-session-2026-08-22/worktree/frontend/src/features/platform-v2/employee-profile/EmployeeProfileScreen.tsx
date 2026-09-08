/**
 * T17 — Employee Profile (S1p) /profile
 * Employee-facing profile view with case summary, documents/forms status, and contact info.
 */

import { Avatar, CountryFlag, DateFormatter, Pill, ProgressBar } from '../shared';
import type { CaseStage, CaseStatus, UserRole } from '../../../types/relopass-api-contracts';
import type { PillVariant } from '../shared';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface EmployeeProfileData {
  id: string;
  full_name: string;
  email: string;
  role: UserRole;
  avatar_url: string | null;
  phone: string | null;
}

export interface ActiveCaseSummary {
  id: string;
  corridor: string; // e.g. "FR-DE"
  origin_code: string;
  dest_code: string;
  stage: CaseStage;
  status: CaseStatus;
  progress: number; // 0-100
  target_start_date: string | null;
  next_action: string;
  docs_submitted: number;
  docs_total: number;
  forms_complete: number;
  forms_total: number;
}

export interface HRContact {
  name: string;
  email: string;
  phone: string | null;
  avatar_url: string | null;
}

export interface EmployeeProfileScreenProps {
  employee?: EmployeeProfileData;
  activeCase?: ActiveCaseSummary | null;
  hrContact?: HRContact | null;
}

// ─── Mock ─────────────────────────────────────────────────────────────────────

const DEFAULT_EMPLOYEE: EmployeeProfileData = {
  id: 'u1',
  full_name: 'Alice Martin',
  email: 'alice.martin@company.com',
  role: 'employee',
  avatar_url: null,
  phone: '+33 6 12 34 56 78',
};

const DEFAULT_CASE: ActiveCaseSummary = {
  id: 'c1',
  corridor: 'FR-DE',
  origin_code: 'FR',
  dest_code: 'DE',
  stage: 'compliance',
  status: 'active',
  progress: 45,
  target_start_date: '2026-07-01',
  next_action: 'Upload residence certificate to continue compliance checks.',
  docs_submitted: 4,
  docs_total: 7,
  forms_complete: 2,
  forms_total: 4,
};

const DEFAULT_HR: HRContact = {
  name: 'Sophie Leconte',
  email: 'sophie.leconte@company.com',
  phone: '+33 1 00 00 00 00',
  avatar_url: null,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

const ROLE_LABEL: Record<UserRole, string> = {
  employee: 'Employee',
  hr: 'HR',
  admin: 'Admin',
  vendor_contact: 'Vendor',
};

const STAGE_LABEL: Record<CaseStage, string> = {
  intake: 'Intake',
  compliance: 'Compliance',
  housing: 'Housing',
  logistics: 'Logistics',
  settling_in: 'Settling In',
  close_out: 'Close Out',
};

const STATUS_VARIANT: Record<CaseStatus, PillVariant> = {
  draft: 'muted',
  active: 'success',
  on_hold: 'warning',
  completed: 'info',
  cancelled: 'danger',
};

function daysUntil(dateStr: string): number {
  return Math.ceil((new Date(dateStr).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
}

// ─── Section heading ──────────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p style={{ margin: '0 0 8px', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-muted)' }}>
      {children}
    </p>
  );
}

// ─── Case summary card ────────────────────────────────────────────────────────

function CaseSummaryCard({ c }: { c: ActiveCaseSummary }) {
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '18px 20px', marginBottom: '16px' }}>
      {/* Header */}
      <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '14px' }}>
        <CountryFlag code={c.origin_code} showCode />
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
        <CountryFlag code={c.dest_code} showCode />
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '6px', alignItems: 'center' }}>
          <Pill variant="default" size="sm">{STAGE_LABEL[c.stage]}</Pill>
          <Pill variant={STATUS_VARIANT[c.status]} size="sm" dot>{c.status === 'active' ? 'Active' : c.status}</Pill>
        </div>
      </div>

      {/* Progress */}
      <div style={{ marginBottom: '14px' }}>
        <ProgressBar value={c.progress} label="Overall progress" height={8} />
      </div>

      {/* Next action */}
      <div style={{ background: 'var(--accent-soft)', border: '1px solid var(--accent-soft-2)', borderRadius: 'var(--radius-md)', padding: '10px 14px', display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" style={{ flexShrink: 0, marginTop: '1px' }}>
          <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM12 8v4l3 3" />
        </svg>
        <div>
          <p style={{ margin: '0 0 2px', fontSize: '12px', fontWeight: 700, color: 'var(--accent-text)' }}>Next action</p>
          <p style={{ margin: 0, fontSize: '13px', color: 'var(--accent-text)', lineHeight: 1.5 }}>{c.next_action}</p>
        </div>
      </div>
    </div>
  );
}

// ─── Status mini card ─────────────────────────────────────────────────────────

function MiniStatusCard({ label, done, total, icon }: { label: string; done: number; total: number; icon: string }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '14px 16px', flex: 1 }}>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '10px' }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2"><path d={icon} /></svg>
        <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)' }}>{label}</span>
      </div>
      <p style={{ margin: '0 0 6px', fontSize: '20px', fontWeight: 700, color: 'var(--text)' }}>
        {done}<span style={{ fontSize: '13px', fontWeight: 400, color: 'var(--text-muted)' }}>/{total}</span>
      </p>
      <ProgressBar value={pct} height={4} />
    </div>
  );
}

// ─── HR Contact Card ──────────────────────────────────────────────────────────

function HRContactCard({ hr }: { hr: HRContact }) {
  return (
    <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '16px' }}>
      <SectionLabel>Your HR contact</SectionLabel>
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '12px' }}>
        <Avatar name={hr.name} src={hr.avatar_url ?? undefined} size={40} />
        <p style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: 'var(--text)' }}>{hr.name}</p>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <a href={`mailto:${hr.email}`} style={{ fontSize: '13px', color: 'var(--link)', textDecoration: 'none' }}>{hr.email}</a>
        {hr.phone && <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{hr.phone}</span>}
      </div>
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export function EmployeeProfileScreen({
  employee = DEFAULT_EMPLOYEE,
  activeCase = DEFAULT_CASE,
  hrContact = DEFAULT_HR,
}: EmployeeProfileScreenProps) {
  const days = activeCase?.target_start_date ? daysUntil(activeCase.target_start_date) : null;

  return (
    <div style={{ padding: '28px 32px', maxWidth: '1000px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', gap: '18px', alignItems: 'center', marginBottom: '28px', padding: '20px 24px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-xl)' }}>
        <Avatar name={employee.full_name} src={employee.avatar_url ?? undefined} size={72} />
        <div style={{ flex: 1 }}>
          <h1 style={{ margin: '0 0 4px', fontSize: '22px', fontWeight: 700, color: 'var(--text)' }}>{employee.full_name}</h1>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <Pill variant="info" size="sm">{ROLE_LABEL[employee.role]}</Pill>
            {activeCase && (
              <>
                <CountryFlag code={activeCase.origin_code} />
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
                <CountryFlag code={activeCase.dest_code} />
                <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{activeCase.corridor}</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Two-column body */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px', alignItems: 'start' }}>
        {/* Left column */}
        <div>
          {activeCase ? (
            <>
              <SectionLabel>Active relocation</SectionLabel>
              <CaseSummaryCard c={activeCase} />

              <div style={{ display: 'flex', gap: '12px' }}>
                <MiniStatusCard
                  label="Documents"
                  done={activeCase.docs_submitted}
                  total={activeCase.docs_total}
                  icon="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zM14 2v6h6"
                />
                <MiniStatusCard
                  label="Forms"
                  done={activeCase.forms_complete}
                  total={activeCase.forms_total}
                  icon="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2"
                />
              </div>
            </>
          ) : (
            <p style={{ fontSize: '14px', color: 'var(--text-muted)' }}>No active relocation case.</p>
          )}
        </div>

        {/* Right column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Contact info */}
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '16px' }}>
            <SectionLabel>Contact</SectionLabel>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><path d="m22 6-10 7L2 6" /></svg>
                <a href={`mailto:${employee.email}`} style={{ fontSize: '13px', color: 'var(--link)', textDecoration: 'none' }}>{employee.email}</a>
              </div>
              {employee.phone && (
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.56 3.37 2 2 0 0 1 3.54 1.18h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 8.91a16 16 0 0 0 6 6l.81-.81a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 21.73 16.92z" /></svg>
                  <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{employee.phone}</span>
                </div>
              )}
            </div>
          </div>

          {/* Move countdown */}
          {activeCase?.target_start_date && days !== null && (
            <div style={{ background: days < 30 ? 'var(--warning-soft)' : 'var(--accent-soft)', border: `1px solid ${days < 30 ? 'var(--pill-warning-border)' : 'var(--accent-soft-2)'}`, borderRadius: 'var(--radius-lg)', padding: '16px', textAlign: 'center' }}>
              <p style={{ margin: '0 0 4px', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: days < 30 ? 'var(--warning-text)' : 'var(--accent-text)' }}>Move date</p>
              <p style={{ margin: '0 0 4px', fontSize: '32px', fontWeight: 800, color: days < 30 ? 'var(--warning)' : 'var(--accent)' }}>{days}</p>
              <p style={{ margin: '0 0 6px', fontSize: '12px', color: days < 30 ? 'var(--warning-text)' : 'var(--accent-text)' }}>days until move</p>
              <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-muted)' }}>
                <DateFormatter date={activeCase.target_start_date} format="absolute" />
              </p>
            </div>
          )}

          {/* HR contact */}
          {hrContact && <HRContactCard hr={hrContact} />}
        </div>
      </div>
    </div>
  );
}
