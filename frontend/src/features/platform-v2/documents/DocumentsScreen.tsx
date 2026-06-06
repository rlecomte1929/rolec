/**
 * T14 — Documents Screen (S8) /documents
 * Employee-facing document management with sidebar, upload zone, and rejection banner.
 */

import React, { useCallback, useRef, useState } from 'react';
import { FileInput } from '../../../components/antigravity/FileInput';
import { Button } from '../../../components/antigravity/Button';
import { ProgressBar, StatusBadge, DateFormatter, EmptyState } from '../shared';
import type { DocStatus } from '../../../types/relopass-api-contracts';

// ─── Brand colour constants ───────────────────────────────────────────────────
// These mirror the main ReloPass app's Tailwind slate palette so the component
// looks identical in the real AppShell context (where platform-v2 CSS vars are
// not defined).
const C = {
  // Backgrounds
  bg:          '#f8fafc', // slate-50
  surface:     '#ffffff',
  surface2:    '#f1f5f9', // slate-100
  surfaceHov:  '#f8fafc', // slate-50

  // Borders & text
  border:      '#e2e8f0', // slate-200
  text:        '#0f172a', // slate-900
  textSec:     '#475569', // slate-600
  textMuted:   '#94a3b8', // slate-400

  // Brand accent (dark navy — matches PlatformShellSidebar)
  accent:      '#0b2b43',
  accentHov:   '#0d3554',
  accentSoft:  '#e0eaf2',

  // Semantic — success
  success:     '#15803d', // green-700
  successSoft: '#dcfce7', // green-100
  successBord: '#bbf7d0', // green-200

  // Semantic — warning (amber)
  warning:     '#b45309', // amber-700
  warningSoft: '#fef3c7', // amber-100
  warningBord: '#fde68a', // amber-200

  // Semantic — danger (red)
  danger:      '#b91c1c', // red-700
  dangerSoft:  '#fee2e2', // red-100
  dangerBord:  '#fca5a5', // red-300
  dangerText:  '#991b1b', // red-800

  // Semantic — info
  info:        '#1d4ed8', // blue-700
  infoSoft:    '#dbeafe', // blue-100
  infoBord:    '#bfdbfe', // blue-200

  // Radii
  radSm:  '4px',
  radMd:  '6px',
  radLg:  '10px',
  radFull:'9999px',
};

// ─── Types ────────────────────────────────────────────────────────────────────

export type RequirementCategory =
  | 'Identity & travel'
  | 'Immigration & permits'
  | 'Employment'
  | 'Housing & relocation'
  | 'Financial & tax'
  | 'Family & dependents';

export interface DocumentItem {
  id: string;
  filename: string;
  category: RequirementCategory;
  status: DocStatus;
  uploaded_at: string | null;
  /** Hard deadline by which the employee must upload this document (ISO date). */
  submission_deadline: string | null;
  expiry_date: string | null;
  rejection_reason: string | null;
  size_kb: number;
}

export interface DocumentsScreenProps {
  documents?: DocumentItem[];
  onUpload?: (file: File, category: RequirementCategory) => Promise<void>;
  onPreview?: (doc: DocumentItem) => void;
  onDownload?: (doc: DocumentItem) => void;
  onDelete?: (doc: DocumentItem) => void;
  onReupload?: (doc: DocumentItem) => void;
  /** Called when the user clicks "Remind HR" in an expiry or deadline alert. */
  onRemind?: (doc: DocumentItem) => Promise<void>;
}

// ─── Mock ─────────────────────────────────────────────────────────────────────

const MOCK_DOCS: DocumentItem[] = [
  // Identity & travel
  { id: 'd1', filename: 'passport.pdf',              category: 'Identity & travel',     status: 'approved',      uploaded_at: '2026-05-02', submission_deadline: null,         expiry_date: '2026-06-14', rejection_reason: null, size_kb: 340 },
  { id: 'd2', filename: 'national_id.pdf',           category: 'Identity & travel',     status: 'approved',      uploaded_at: '2026-04-28', submission_deadline: null,         expiry_date: '2031-03-15', rejection_reason: null, size_kb: 210 },
  { id: 'd3', filename: 'birth_certificate.pdf',     category: 'Identity & travel',     status: 'approved',      uploaded_at: '2026-05-05', submission_deadline: null,         expiry_date: null,         rejection_reason: null, size_kb: 185 },

  // Immigration & permits
  { id: 'd4', filename: 'work_permit_germany.pdf',   category: 'Immigration & permits', status: 'approved',      uploaded_at: '2026-05-10', submission_deadline: null,         expiry_date: '2026-08-01', rejection_reason: null, size_kb: 520 },
  { id: 'd5', filename: 'visa_copy.pdf',             category: 'Immigration & permits', status: 'required',      uploaded_at: null,         submission_deadline: '2026-06-01', expiry_date: null,         rejection_reason: null, size_kb: 0 },
  { id: 'd6', filename: 'residence_registration.pdf',category: 'Immigration & permits', status: 'under_review',  uploaded_at: '2026-05-15', submission_deadline: null,         expiry_date: null,         rejection_reason: null, size_kb: 310 },

  // Employment
  { id: 'd7', filename: 'employment_contract.pdf',   category: 'Employment',            status: 'approved',      uploaded_at: '2026-03-20', submission_deadline: null,         expiry_date: null,         rejection_reason: null, size_kb: 445 },
  { id: 'd8', filename: 'offer_letter.pdf',          category: 'Employment',            status: 'approved',      uploaded_at: '2026-03-18', submission_deadline: null,         expiry_date: null,         rejection_reason: null, size_kb: 230 },
  { id: 'd9', filename: 'payslips_last3.pdf',        category: 'Employment',            status: 'submitted',     uploaded_at: '2026-05-12', submission_deadline: null,         expiry_date: null,         rejection_reason: null, size_kb: 580 },

  // Housing & relocation
  { id: 'd10', filename: 'lease_agreement.pdf',      category: 'Housing & relocation',  status: 'approved',      uploaded_at: '2026-05-01', submission_deadline: null,         expiry_date: '2027-05-01', rejection_reason: null, size_kb: 670 },
  { id: 'd11', filename: 'proof_of_address.pdf',     category: 'Housing & relocation',  status: 'rejected',      uploaded_at: '2026-05-08', submission_deadline: '2026-06-15', expiry_date: null,         rejection_reason: 'Document must be dated within the last 3 months. Please re-upload a recent utility bill or bank statement.', size_kb: 195 },
  { id: 'd12', filename: 'moving_quote.pdf',         category: 'Housing & relocation',  status: 'submitted',     uploaded_at: '2026-05-14', submission_deadline: null,         expiry_date: null,         rejection_reason: null, size_kb: 420 },

  // Financial & tax
  { id: 'd13', filename: 'tax_declaration_fr.pdf',   category: 'Financial & tax',       status: 'required',      uploaded_at: null,         submission_deadline: '2026-06-30', expiry_date: null,         rejection_reason: null, size_kb: 0 },
  { id: 'd14', filename: 'bank_statement_3mo.pdf',   category: 'Financial & tax',       status: 'required',      uploaded_at: null,         submission_deadline: null,         expiry_date: null,         rejection_reason: null, size_kb: 0 },

  // Family & dependents (optional — empty by default)
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

const CATEGORIES: RequirementCategory[] = [
  'Identity & travel',
  'Immigration & permits',
  'Employment',
  'Housing & relocation',
  'Financial & tax',
  'Family & dependents',
];

/** Days until a date (negative = already past). Returns null if no date. */
function daysUntil(date: string | null): number | null {
  if (!date) return null;
  return Math.ceil((new Date(date).getTime() - Date.now()) / (24 * 60 * 60 * 1000));
}

type ExpiryUrgency = 'critical' | 'warning' | null;

/** Returns urgency tier based on days to expiry. */
function expiryUrgency(expiry: string | null): ExpiryUrgency {
  const d = daysUntil(expiry);
  if (d === null || d <= 0) return null;
  if (d <= 30) return 'critical';
  if (d <= 90) return 'warning';
  return null;
}

/** True if expiry is in the future but within 90 days. */
function isExpiringSoon(expiry: string | null): boolean {
  return expiryUrgency(expiry) !== null;
}

/** True if a submission deadline exists and is within 30 days. */
function isDeadlineSoon(deadline: string | null): boolean {
  const d = daysUntil(deadline);
  return d !== null && d > 0 && d <= 30;
}

export type DocFilter = 'all' | 'missing' | 'pending' | 'expiring' | 'approved';

function matchesFilter(doc: DocumentItem, filter: DocFilter): boolean {
  switch (filter) {
    case 'missing':  return doc.status === 'required';
    case 'pending':  return doc.status === 'submitted' || doc.status === 'under_review';
    case 'expiring': return isExpiringSoon(doc.expiry_date);
    case 'approved': return doc.status === 'approved';
    default: return true;
  }
}

function formatSize(kb: number): string {
  if (kb === 0) return '—';
  if (kb > 1024) return `${(kb / 1024).toFixed(1)} MB`;
  return `${kb} KB`;
}

// ─── Category icons (inline SVG paths) ───────────────────────────────────────

const CATEGORY_ICON: Record<RequirementCategory, string> = {
  'Identity & travel':     'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
  'Immigration & permits': 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 0 0 1 1h3m10-11l2 2m-2-2v10a1 1 0 0 0-1 1h-3m-6 0h6',
  'Employment':            'M20 7H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2zM16 3H8a2 2 0 0 0-2 2v2h12V5a2 2 0 0 0-2-2z',
  'Housing & relocation':  'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 0 0 1 1h3m10-11l2 2m-2-2v10a1 1 0 0 0-1 1h-3m-6 0a1 1 0 0 0 1 1h2a1 1 0 0 0 1-1v-3a1 1 0 0 0-1-1h-2a1 1 0 0 0-1 1v3z',
  'Financial & tax':       'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8v1m0 10v1M8 12H4m16 0h-4',
  'Family & dependents':   'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
};

// ─── Upload Zone ──────────────────────────────────────────────────────────────

interface UploadZoneProps {
  category: RequirementCategory;
  onUpload: (file: File, category: RequirementCategory) => Promise<void>;
}

function UploadZone({ category, onUpload }: UploadZoneProps) {
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const ACCEPTED = ['application/pdf', 'image/jpeg', 'image/png', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
  const MAX_BYTES = 25 * 1024 * 1024;

  const handleFiles = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const file = files[0]!;
    if (!ACCEPTED.includes(file.type)) { setError('Unsupported file type. Use PDF, JPEG, PNG or DOCX.'); return; }
    if (file.size > MAX_BYTES) { setError('File exceeds 25 MB limit.'); return; }
    setError(null);
    setProgress(0);
    const interval = setInterval(() => setProgress(p => (p !== null && p < 90 ? p + 15 : p)), 200);
    try {
      await onUpload(file, category);
      clearInterval(interval);
      setProgress(100);
      setTimeout(() => setProgress(null), 1000);
    } catch {
      clearInterval(interval);
      setError('Upload failed. Please try again.');
      setProgress(null);
    }
  }, [category, onUpload]);

  return (
    <div style={{ marginBottom: '4px' }}>
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
        style={{
          border: `2px dashed ${dragging ? C.accent : C.border}`,
          borderRadius: C.radLg,
          padding: '20px 24px',
          textAlign: 'center',
          background: dragging ? C.accentSoft : C.surface2,
          cursor: 'pointer',
          transition: 'all 0.15s',
        }}
      >
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke={C.textMuted} strokeWidth="1.5" style={{ margin: '0 auto 8px', display: 'block' }}>
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" />
        </svg>
        <p style={{ margin: '0 0 3px', fontSize: '13px', fontWeight: 600, color: C.text }}>
          Drop file here or{' '}
          <span style={{ color: C.accent, textDecoration: 'underline' }}>browse</span>
        </p>
        <p style={{ margin: 0, fontSize: '11px', color: C.textMuted }}>PDF, JPEG, PNG or DOCX · max 25 MB</p>
      </div>
      <FileInput ref={inputRef} accept=".pdf,.jpg,.jpeg,.png,.docx" style={{ display: 'none' }} onChange={e => handleFiles(e.target.files)} />
      {progress !== null && <div style={{ marginTop: '8px' }}><ProgressBar value={progress} label="Uploading…" height={6} /></div>}
      {error && <p style={{ margin: '6px 0 0', fontSize: '12px', color: C.danger }}>{error}</p>}
    </div>
  );
}

// ─── Rejection Banner ─────────────────────────────────────────────────────────

interface RejectionBannerProps {
  doc: DocumentItem;
  onReupload: () => void;
}

function RejectionBanner({ doc, onReupload }: RejectionBannerProps) {
  return (
    <div style={{
      background: C.dangerSoft,
      border: `1px solid ${C.dangerBord}`,
      borderRadius: C.radMd,
      padding: '12px 16px',
      display: 'flex',
      gap: '12px',
      alignItems: 'flex-start',
      marginBottom: '10px',
    }}>
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke={C.danger} strokeWidth="2" style={{ flexShrink: 0, marginTop: '1px' }}>
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01" />
      </svg>
      <div style={{ flex: 1 }}>
        <p style={{ margin: '0 0 2px', fontSize: '13px', fontWeight: 700, color: C.dangerText }}>
          {doc.filename} was rejected
        </p>
        <p style={{ margin: '0 0 8px', fontSize: '13px', color: C.dangerText }}>{doc.rejection_reason}</p>
        <Button unstyled
          onClick={onReupload}
          style={{
            padding: '5px 12px', borderRadius: C.radMd, border: 'none',
            background: C.danger, color: '#fff', fontSize: '12px', fontWeight: 600, cursor: 'pointer',
          }}
        >
          Re-upload
        </Button>
      </div>
    </div>
  );
}

// ─── Document Row ─────────────────────────────────────────────────────────────

interface DocRowProps {
  doc: DocumentItem;
  onPreview: () => void;
  onDownload: () => void;
  onDelete: () => void;
}

function DocRow({ doc, onPreview, onDownload, onDelete }: DocRowProps) {
  const urgency      = expiryUrgency(doc.expiry_date);
  const deadlineSoon = isDeadlineSoon(doc.submission_deadline);
  const expiryDays   = daysUntil(doc.expiry_date);
  const deadlineDays = daysUntil(doc.submission_deadline);

  // Row background tint for urgent items
  const rowBg =
    urgency === 'critical' ? '#fff1f1' :
    urgency === 'warning'  ? '#fffbeb' :
    (doc.status === 'required' && deadlineSoon ? '#fffbeb' : 'transparent');

  // Expiry / deadline cell
  let dateCell: React.ReactNode = <span style={{ color: C.textMuted }}>—</span>;
  if (doc.expiry_date) {
    const expiryColor =
      urgency === 'critical' ? C.danger :
      urgency === 'warning'  ? C.warning :
      C.textSec;
    const expiryWeight = urgency ? 600 : 400;

    dateCell = (
      <span style={{ color: expiryColor, fontWeight: expiryWeight, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
        {urgency === 'critical' && (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke={C.danger} strokeWidth="2.5" style={{ flexShrink: 0 }}>
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01" />
          </svg>
        )}
        {urgency && expiryDays !== null
          ? `Expires in ${expiryDays}d`
          : <DateFormatter date={doc.expiry_date} format="absolute" />}
      </span>
    );
  } else if (doc.submission_deadline) {
    const dlColor = deadlineSoon ? C.warning : C.textSec;
    dateCell = (
      <span style={{ color: dlColor, fontWeight: deadlineSoon ? 600 : 400 }}>
        {deadlineSoon && deadlineDays !== null
          ? `Due in ${deadlineDays}d`
          : <>Due <DateFormatter date={doc.submission_deadline} format="absolute" /></>}
      </span>
    );
  }

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 110px 140px 130px auto',
      alignItems: 'center',
      gap: '12px',
      padding: '11px 16px',
      borderBottom: `1px solid ${C.border}`,
      fontSize: '13px',
      background: rowBg,
      transition: 'background 0.1s',
    }}>
      {/* Name */}
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', minWidth: 0 }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={C.textMuted} strokeWidth="1.5" style={{ flexShrink: 0 }}>
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" />
          <path d="M14 2v6h6" />
        </svg>
        <span style={{ fontWeight: 500, color: C.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{doc.filename}</span>
        {doc.size_kb > 0 && (
          <span style={{ color: C.textMuted, flexShrink: 0, fontSize: '11px' }}>{formatSize(doc.size_kb)}</span>
        )}
      </div>
      {/* Upload date */}
      <div style={{ color: C.textSec, fontSize: '12px' }}>
        {doc.uploaded_at
          ? <DateFormatter date={doc.uploaded_at} format="absolute" />
          : <span style={{ color: C.textMuted }}>—</span>}
      </div>
      {/* Expiry / deadline */}
      <div style={{ fontSize: '12px' }}>{dateCell}</div>
      {/* Status */}
      <StatusBadge type="doc" status={doc.status} />
      {/* Actions */}
      <div style={{ display: 'flex', gap: '2px' }}>
        <Button unstyled onClick={onPreview} title="Preview" style={{ background: 'none', border: 'none', cursor: 'pointer', color: C.textMuted, padding: '5px', borderRadius: C.radSm, lineHeight: 0 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>
        </Button>
        <Button unstyled onClick={onDownload} title="Download" style={{ background: 'none', border: 'none', cursor: 'pointer', color: C.textMuted, padding: '5px', borderRadius: C.radSm, lineHeight: 0 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" /></svg>
        </Button>
        <Button unstyled onClick={onDelete} title="Delete" style={{ background: 'none', border: 'none', cursor: 'pointer', color: C.danger, padding: '5px', borderRadius: C.radSm, lineHeight: 0 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" /></svg>
        </Button>
      </div>
    </div>
  );
}

// ─── Reminder Settings ────────────────────────────────────────────────────────

interface ReminderSettings {
  firstAlertDays: number;
  cadence: 'weekly' | 'biweekly' | 'daily-last7';
  deadlineNoticeDays: number;
  notifyHr: boolean;
}

const DEFAULT_REMINDER_SETTINGS: ReminderSettings = {
  firstAlertDays: 90,
  cadence: 'weekly',
  deadlineNoticeDays: 14,
  notifyHr: true,
};

const selectStyle: React.CSSProperties = {
  fontSize: '12px', padding: '4px 8px', borderRadius: C.radMd,
  border: `1px solid ${C.border}`, background: C.surface2,
  color: C.text, cursor: 'pointer', outline: 'none',
};

function ReminderSettingsPanel() {
  const [open, setOpen] = useState(false);
  const [settings, setSettings] = useState<ReminderSettings>(DEFAULT_REMINDER_SETTINGS);

  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`,
      borderRadius: C.radLg, marginTop: '16px', overflow: 'hidden',
    }}>
      <Button unstyled
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: '10px',
          padding: '13px 16px', background: 'none', border: 'none', cursor: 'pointer',
          borderBottom: open ? `1px solid ${C.border}` : 'none', textAlign: 'left',
        }}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={C.textMuted} strokeWidth="1.5">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        <span style={{ flex: 1, fontSize: '13px', fontWeight: 600, color: C.text }}>Reminder settings</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={C.textMuted} strokeWidth="2"
          style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s', flexShrink: 0 }}>
          <path d="M6 9l6 6 6-6" />
        </svg>
      </Button>

      {open && (
        <div style={{ padding: '4px 16px 16px' }}>
          {[
            {
              label: 'Expiry warning — first alert',
              control: (
                <select value={settings.firstAlertDays}
                  onChange={e => setSettings(s => ({ ...s, firstAlertDays: Number(e.target.value) }))}
                  style={selectStyle}>
                  <option value={90}>90 days before</option>
                  <option value={60}>60 days before</option>
                  <option value={30}>30 days before</option>
                </select>
              ),
            },
            {
              label: 'Expiry warning — reminder cadence',
              control: (
                <select value={settings.cadence}
                  onChange={e => setSettings(s => ({ ...s, cadence: e.target.value as ReminderSettings['cadence'] }))}
                  style={selectStyle}>
                  <option value="weekly">Every week</option>
                  <option value="biweekly">Every 2 weeks</option>
                  <option value="daily-last7">Daily (last 7 days)</option>
                </select>
              ),
            },
            {
              label: 'Deadline reminder — notify employee',
              control: (
                <select value={settings.deadlineNoticeDays}
                  onChange={e => setSettings(s => ({ ...s, deadlineNoticeDays: Number(e.target.value) }))}
                  style={selectStyle}>
                  <option value={14}>14 days before</option>
                  <option value={7}>7 days before</option>
                  <option value={3}>3 days before</option>
                </select>
              ),
            },
          ].map(({ label, control }, i, arr) => (
            <div key={label} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '9px 0', borderBottom: i < arr.length - 1 ? `1px solid ${C.border}` : 'none',
              fontSize: '13px',
            }}>
              <span style={{ color: C.textSec }}>{label}</span>
              {control}
            </div>
          ))}

          {/* HR toggle */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            paddingTop: '9px', fontSize: '13px',
          }}>
            <span style={{ color: C.textSec }}>Also notify the HR manager</span>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <span style={{ fontSize: '12px', color: settings.notifyHr ? C.accent : C.textMuted }}>
                {settings.notifyHr ? 'On' : 'Off'}
              </span>
              <div
                onClick={() => setSettings(s => ({ ...s, notifyHr: !s.notifyHr }))}
                role="switch"
                aria-checked={settings.notifyHr}
                style={{
                  width: '36px', height: '20px', borderRadius: '10px', cursor: 'pointer',
                  background: settings.notifyHr ? C.accent : C.border,
                  position: 'relative', transition: 'background 0.15s', flexShrink: 0,
                }}
              >
                <div style={{
                  position: 'absolute', top: '3px',
                  left: settings.notifyHr ? '19px' : '3px',
                  width: '14px', height: '14px', borderRadius: '50%',
                  background: '#fff', transition: 'left 0.15s',
                }} />
              </div>
            </label>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Alert Banners ────────────────────────────────────────────────────────────

interface AlertRowProps {
  doc: DocumentItem;
  label: string;
  days: number;
  tier: 'critical' | 'warning' | 'deadline';
  onRemind: () => void;
}

function AlertRow({ doc, label, days, tier, onRemind }: AlertRowProps) {
  const [sent, setSent] = useState(false);

  const fg =
    tier === 'critical' ? C.danger :
    tier === 'warning'  ? C.warning :
    C.warning;
  const bg =
    tier === 'critical' ? C.dangerSoft :
    C.warningSoft;
  const bord =
    tier === 'critical' ? C.dangerBord :
    C.warningBord;

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px',
      background: C.surface, borderRadius: C.radMd, padding: '6px 10px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke={fg} strokeWidth="2" style={{ flexShrink: 0 }}>
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" />
          <path d="M14 2v6h6" />
        </svg>
        <span style={{ fontSize: '13px', color: C.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {doc.filename}
        </span>
        <span style={{ fontSize: '11px', color: C.textMuted, flexShrink: 0 }}>{doc.category}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
        {tier === 'critical' && (
          <span style={{
            fontSize: '10px', fontWeight: 700, padding: '1px 6px',
            borderRadius: C.radFull, background: C.danger, color: '#fff', letterSpacing: '0.04em',
          }}>
            URGENT
          </span>
        )}
        <span style={{ fontSize: '12px', fontWeight: 600, color: fg, whiteSpace: 'nowrap' }}>
          {label} · {days}d left
        </span>
        {sent ? (
          <span style={{
            fontSize: '11px', padding: '3px 10px', borderRadius: C.radMd,
            background: C.successSoft, color: C.success, fontWeight: 600,
          }}>
            Reminder sent ✓
          </span>
        ) : (
          <Button unstyled
            onClick={() => { setSent(true); onRemind(); }}
            style={{
              fontSize: '11px', padding: '4px 10px', borderRadius: C.radMd, cursor: 'pointer',
              background: bg, color: fg, border: `1px solid ${bord}`, fontWeight: 600,
              whiteSpace: 'nowrap',
            }}
          >
            Remind employee
          </Button>
        )}
      </div>
    </div>
  );
}

interface ExpiryAlertBannerProps {
  docs: DocumentItem[];
  onRemind: (doc: DocumentItem) => void;
}

function ExpiryAlertBanner({ docs, onRemind }: ExpiryAlertBannerProps) {
  if (docs.length === 0) return null;
  const criticalDocs = docs.filter(d => expiryUrgency(d.expiry_date) === 'critical');
  const warningDocs  = docs.filter(d => expiryUrgency(d.expiry_date) === 'warning');

  return (
    <div style={{
      background: C.dangerSoft, border: `1px solid ${C.dangerBord}`,
      borderRadius: C.radLg, padding: '10px 14px', marginBottom: '8px',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke={C.danger} strokeWidth="2" style={{ flexShrink: 0, marginTop: '2px' }}>
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01" />
        </svg>
        <div style={{ flex: 1 }}>
          <p style={{ margin: '0 0 7px', fontSize: '13px', fontWeight: 700, color: C.dangerText }}>
            {docs.length === 1 ? '1 document expiring within 90 days' : `${docs.length} documents expiring within 90 days`}
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {criticalDocs.map(doc => (
              <AlertRow key={doc.id} doc={doc} tier="critical"
                label={`Expires ${doc.expiry_date}`}
                days={daysUntil(doc.expiry_date) ?? 0}
                onRemind={() => onRemind(doc)} />
            ))}
            {warningDocs.map(doc => (
              <AlertRow key={doc.id} doc={doc} tier="warning"
                label={`Expires ${doc.expiry_date}`}
                days={daysUntil(doc.expiry_date) ?? 0}
                onRemind={() => onRemind(doc)} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

interface DeadlineAlertBannerProps {
  docs: DocumentItem[];
  onRemind: (doc: DocumentItem) => void;
}

function DeadlineAlertBanner({ docs, onRemind }: DeadlineAlertBannerProps) {
  if (docs.length === 0) return null;
  return (
    <div style={{
      background: C.warningSoft, border: `1px solid ${C.warningBord}`,
      borderRadius: C.radLg, padding: '10px 14px', marginBottom: '12px',
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke={C.warning} strokeWidth="2" style={{ flexShrink: 0, marginTop: '2px' }}>
          <circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" />
        </svg>
        <div style={{ flex: 1 }}>
          <p style={{ margin: '0 0 7px', fontSize: '13px', fontWeight: 700, color: C.warning }}>
            {docs.length === 1 ? '1 upcoming submission deadline' : `${docs.length} upcoming submission deadlines`}
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {docs.map(doc => (
              <AlertRow key={doc.id} doc={doc} tier="deadline"
                label={`Due ${doc.submission_deadline}`}
                days={daysUntil(doc.submission_deadline) ?? 0}
                onRemind={() => onRemind(doc)} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Collapsible Upload ───────────────────────────────────────────────────────

interface CollapsibleUploadProps {
  category: RequirementCategory;
  onUpload: (file: File, category: RequirementCategory) => Promise<void>;
}

function CollapsibleUpload({ category, onUpload }: CollapsibleUploadProps) {
  const [open, setOpen] = useState(false);

  return (
    <div style={{ borderTop: `1px solid ${C.border}` }}>
      {!open ? (
        <Button unstyled
          onClick={() => setOpen(true)}
          style={{
            width: '100%', display: 'flex', alignItems: 'center', gap: '6px',
            padding: '8px 16px', background: 'none', border: 'none',
            cursor: 'pointer', color: C.textMuted, fontSize: '12px',
            textAlign: 'left', transition: 'color 0.1s',
          }}
          onMouseEnter={e => (e.currentTarget.style.color = C.accent)}
          onMouseLeave={e => (e.currentTarget.style.color = C.textMuted)}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0 }}>
            <path d="M12 5v14M5 12h14" />
          </svg>
          Add document
        </Button>
      ) : (
        <div style={{ padding: '12px 16px 14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: C.textSec }}>Upload to {category}</span>
            <Button unstyled
              onClick={() => setOpen(false)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: C.textMuted, padding: '2px', lineHeight: 0 }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </Button>
          </div>
          <UploadZone category={category} onUpload={async (file, cat) => { await onUpload(file, cat); setOpen(false); }} />
        </div>
      )}
    </div>
  );
}

// ─── Category Section ─────────────────────────────────────────────────────────

interface CategorySectionProps {
  cat: RequirementCategory;
  docs: DocumentItem[];
  isOpen: boolean;
  onToggle: () => void;
  onUpload: (file: File, category: RequirementCategory) => Promise<void>;
  onPreview: (doc: DocumentItem) => void;
  onDownload: (doc: DocumentItem) => void;
  onDelete: (doc: DocumentItem) => void;
  onReupload: (doc: DocumentItem) => void;
  isOptional?: boolean;
}

function CategorySection({
  cat, docs, isOpen, onToggle, onUpload, onPreview, onDownload, onDelete, onReupload, isOptional,
}: CategorySectionProps) {
  const approved = docs.filter(d => d.status === 'approved').length;
  const rejected = docs.filter(d => d.status === 'rejected');
  const hasAlert = docs.some(d => isExpiringSoon(d.expiry_date) || (d.status === 'required' && isDeadlineSoon(d.submission_deadline)));
  const allDone  = docs.length > 0 && approved === docs.length;

  const badgeBg =
    isOptional ? C.surface2 :
    allDone    ? C.successSoft :
    C.warningSoft;
  const badgeColor =
    isOptional ? C.textMuted :
    allDone    ? C.success :
    C.warning;
  const badgeText = isOptional ? 'Optional' : `${approved} / ${docs.length}`;

  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`,
      borderRadius: C.radLg, overflow: 'hidden', marginBottom: '10px',
    }}>
      {/* Header row */}
      <Button unstyled
        onClick={onToggle}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: '10px',
          padding: '13px 16px', background: isOpen ? C.surface2 : C.surface,
          border: 'none', cursor: 'pointer',
          borderBottom: isOpen ? `1px solid ${C.border}` : 'none',
          textAlign: 'left', transition: 'background 0.1s',
        }}
      >
        <div style={{
          width: '30px', height: '30px', borderRadius: C.radMd,
          background: C.accentSoft, display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={C.accent} strokeWidth="1.8">
            <path d={CATEGORY_ICON[cat]} />
          </svg>
        </div>
        <span style={{ flex: 1, fontSize: '14px', fontWeight: 600, color: C.text }}>{cat}</span>
        {hasAlert && !isOptional && (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={C.danger} strokeWidth="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01" />
          </svg>
        )}
        <span style={{
          fontSize: '11px', padding: '2px 9px', borderRadius: C.radFull,
          background: badgeBg, color: badgeColor, fontWeight: 600,
        }}>
          {badgeText}
        </span>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke={C.textMuted} strokeWidth="2"
          style={{ transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s', flexShrink: 0 }}>
          <path d="M6 9l6 6 6-6" />
        </svg>
      </Button>

      {/* Body */}
      {isOpen && (
        <div>
          {/* Rejection banners */}
          {rejected.length > 0 && (
            <div style={{ padding: '12px 16px 0' }}>
              {rejected.map(doc => (
                <RejectionBanner key={doc.id} doc={doc} onReupload={() => onReupload(doc)} />
              ))}
            </div>
          )}

          {/* Document table */}
          {docs.length === 0 ? (
            <EmptyState icon="M14 2H6a2 2 0 0 0-2 2v16" title="No documents yet" description="Upload a document below to get started." />
          ) : (
            <>
              {/* Column headers */}
              <div style={{
                display: 'grid', gridTemplateColumns: '1fr 110px 140px 130px auto',
                gap: '12px', padding: '7px 16px',
                background: C.surface2, borderBottom: `1px solid ${C.border}`,
                fontSize: '10px', fontWeight: 700, color: C.textMuted,
                textTransform: 'uppercase', letterSpacing: '0.05em',
              }}>
                <span>Document</span><span>Uploaded</span><span>Expiry / deadline</span><span>Status</span><span>Actions</span>
              </div>
              {docs.map(doc => (
                <DocRow key={doc.id} doc={doc}
                  onPreview={() => onPreview(doc)}
                  onDownload={() => onDownload(doc)}
                  onDelete={() => onDelete(doc)}
                />
              ))}
            </>
          )}

          {/* Upload zone — collapsed by default */}
          <CollapsibleUpload category={cat} onUpload={onUpload} />
        </div>
      )}
    </div>
  );
}

// ─── Filter chips ─────────────────────────────────────────────────────────────

interface FilterChipsProps {
  active: DocFilter;
  onChange: (f: DocFilter) => void;
  counts: Record<DocFilter, number>;
}

function FilterChips({ active, onChange, counts }: FilterChipsProps) {
  const chips: { key: DocFilter; label: string; dot?: string }[] = [
    { key: 'all',      label: `All (${counts.all})` },
    { key: 'missing',  label: `Missing (${counts.missing})`,  dot: counts.missing > 0  ? C.warning : undefined },
    { key: 'pending',  label: `Pending (${counts.pending})` },
    { key: 'expiring', label: `Expiring (${counts.expiring})`, dot: counts.expiring > 0 ? C.danger  : undefined },
    { key: 'approved', label: `Approved (${counts.approved})` },
  ];

  return (
    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '16px' }}>
      {chips.map(({ key, label, dot }) => {
        const isActive = active === key;
        return (
          <Button unstyled
            key={key}
            onClick={() => onChange(key)}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: '5px',
              padding: '5px 13px', borderRadius: C.radFull, fontSize: '12px', cursor: 'pointer',
              background: isActive ? C.accent : C.surface,
              color:      isActive ? '#fff'   : C.textSec,
              border:     isActive ? `1px solid ${C.accent}` : `1px solid ${C.border}`,
              fontWeight: isActive ? 600 : 400,
              transition: 'all 0.12s',
            }}
          >
            {dot && !isActive && (
              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: dot, flexShrink: 0 }} />
            )}
            {label}
          </Button>
        );
      })}
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export function DocumentsScreen({
  documents = MOCK_DOCS,
  onUpload = async () => {},
  onPreview,
  onDownload,
  onDelete,
  onReupload,
  onRemind,
}: DocumentsScreenProps) {
  const [openCats, setOpenCats] = useState<Set<RequirementCategory>>(
    new Set<RequirementCategory>(['Identity & travel', 'Immigration & permits'])
  );
  const [activeFilter, setActiveFilter] = useState<DocFilter>('all');

  const toggleCat = (cat: RequirementCategory) =>
    setOpenCats(prev => { const n = new Set(prev); n.has(cat) ? n.delete(cat) : n.add(cat); return n; });

  // ── Alert docs ──
  const expiringDocs = documents.filter(d => isExpiringSoon(d.expiry_date));
  const deadlineDocs = documents.filter(d => d.status === 'required' && isDeadlineSoon(d.submission_deadline));

  const handleRemind = (doc: DocumentItem) => {
    if (onRemind) {
      void onRemind(doc);
    }
  };

  // ── Stats ──
  const totalDocs     = documents.length;
  const approvedCount = documents.filter(d => d.status === 'approved').length;
  const missingCount  = documents.filter(d => d.status === 'required').length;
  const pendingCount  = documents.filter(d => d.status === 'submitted' || d.status === 'under_review').length;
  const expiringCount = expiringDocs.length;
  const completion    = totalDocs > 0 ? Math.round((approvedCount / totalDocs) * 100) : 0;

  const filterCounts: Record<DocFilter, number> = {
    all:      totalDocs,
    missing:  documents.filter(d => matchesFilter(d, 'missing')).length,
    pending:  documents.filter(d => matchesFilter(d, 'pending')).length,
    expiring: documents.filter(d => matchesFilter(d, 'expiring')).length,
    approved: approvedCount,
  };

  const filteredDocs = documents.filter(d => matchesFilter(d, activeFilter));

  return (
    <div>

      {/* ── Page header ── */}
      <div style={{
        display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
        marginBottom: '20px', gap: '12px',
      }}>
        <div>
          <p style={{ margin: '0 0 2px', fontSize: '11px', color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600 }}>
            Documents
          </p>
          <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 700, color: C.text }}>Document vault</h2>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: C.textSec }}>
            Manage and track all relocation documents in one place.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
          <Button unstyled
            style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '7px 14px', borderRadius: C.radMd,
              border: `1px solid ${C.border}`, background: C.surface,
              color: C.textSec, fontSize: '13px', cursor: 'pointer',
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />
            </svg>
            Export all
          </Button>
          <Button unstyled
            onClick={() => {/* future: open upload modal */}}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px',
              padding: '7px 14px', borderRadius: C.radMd,
              border: `1px solid ${C.accent}`, background: C.accent,
              color: '#fff', fontSize: '13px', fontWeight: 600, cursor: 'pointer',
            }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" />
            </svg>
            Upload
          </Button>
        </div>
      </div>

      {/* ── Alert banners ── */}
      <ExpiryAlertBanner  docs={expiringDocs} onRemind={handleRemind} />
      <DeadlineAlertBanner docs={deadlineDocs} onRemind={handleRemind} />

      {/* ── Stat strip + progress ── */}
      <div style={{
        background: C.surface, border: `1px solid ${C.border}`,
        borderRadius: C.radLg, marginBottom: '14px', overflow: 'hidden',
      }}>
        {/* Stat cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)' }}>
          {[
            { label: 'Total',        value: totalDocs,                         accent: C.accent,   bg: C.surface },
            { label: 'Approved',     value: approvedCount,                     accent: C.success,  bg: C.surface },
            { label: 'Missing',      value: missingCount + pendingCount,        accent: missingCount + pendingCount > 0 ? C.warning : C.border, bg: C.surface },
            { label: 'Expiring soon',value: expiringCount,                     accent: expiringCount > 0 ? C.danger : C.border,  bg: C.surface },
          ].map(({ label, value, accent, bg }, i, arr) => (
            <div key={label} style={{
              background: bg,
              borderRight: i < arr.length - 1 ? `1px solid ${C.border}` : 'none',
              borderLeft: `3px solid ${accent}`,
              padding: '10px 14px',
              display: 'flex', alignItems: 'center', gap: '12px',
            }}>
              <p style={{ margin: 0, fontSize: '20px', fontWeight: 700, color: accent, lineHeight: 1, minWidth: '24px' }}>{value}</p>
              <p style={{ margin: 0, fontSize: '11px', color: C.textMuted, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, lineHeight: 1.3 }}>{label}</p>
            </div>
          ))}
        </div>
        {/* Inline progress bar */}
        <div style={{ height: '5px', background: C.border }}>
          <div style={{ height: '100%', width: `${completion}%`, background: C.success, transition: 'width 0.4s ease' }} />
        </div>
      </div>

      {/* ── Filter chips ── */}
      <FilterChips active={activeFilter} onChange={setActiveFilter} counts={filterCounts} />

      {/* ── Category accordions ── */}
      {CATEGORIES.map(cat => {
        const catDocs   = filteredDocs.filter(d => d.category === cat);
        const isOptional = cat === 'Family & dependents';
        // If filtering and no docs match in this category, hide the section entirely
        if (activeFilter !== 'all' && catDocs.length === 0) return null;
        return (
          <CategorySection
            key={cat}
            cat={cat}
            docs={catDocs}
            isOpen={openCats.has(cat)}
            onToggle={() => toggleCat(cat)}
            onUpload={onUpload}
            onPreview={doc => onPreview?.(doc)}
            onDownload={doc => onDownload?.(doc)}
            onDelete={doc => onDelete?.(doc)}
            onReupload={doc => onReupload?.(doc)}
            isOptional={isOptional}
          />
        );
      })}

      {/* ── Reminder settings ── */}
      <ReminderSettingsPanel />

    </div>
  );
}
