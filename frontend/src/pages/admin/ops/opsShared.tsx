/**
 * Shared primitives + helpers for the Ops Analytics pages
 * (Dashboard / SLA / Queue / Reviewers / Destinations / Alerts).
 */

import type React from 'react';
import { Button } from '../../../components/antigravity/Button';
// ── Country helpers ────────────────────────────────────────────────────────

export const COUNTRY_NAMES: Record<string, string> = {
  // Europe
  NO: 'Norway', DE: 'Germany', FR: 'France', ES: 'Spain', IT: 'Italy',
  NL: 'Netherlands', GB: 'United Kingdom', UK: 'United Kingdom', IE: 'Ireland',
  BE: 'Belgium', LU: 'Luxembourg', CH: 'Switzerland', AT: 'Austria',
  DK: 'Denmark', SE: 'Sweden', FI: 'Finland', IS: 'Iceland',
  PL: 'Poland', PT: 'Portugal', GR: 'Greece', CZ: 'Czech Republic',
  SK: 'Slovakia', HU: 'Hungary', RO: 'Romania', BG: 'Bulgaria',
  HR: 'Croatia', SI: 'Slovenia', EE: 'Estonia', LV: 'Latvia', LT: 'Lithuania',
  UA: 'Ukraine', TR: 'Türkiye', RU: 'Russia', CY: 'Cyprus', MT: 'Malta', RS: 'Serbia',
  // Americas
  US: 'United States', CA: 'Canada', MX: 'Mexico', BR: 'Brazil',
  AR: 'Argentina', CL: 'Chile', CO: 'Colombia', PE: 'Peru', UY: 'Uruguay',
  CR: 'Costa Rica', PA: 'Panama',
  // Asia / Pacific
  JP: 'Japan', CN: 'China', KR: 'South Korea', KP: 'North Korea',
  IN: 'India', PK: 'Pakistan', BD: 'Bangladesh', LK: 'Sri Lanka',
  SG: 'Singapore', MY: 'Malaysia', ID: 'Indonesia', TH: 'Thailand',
  VN: 'Vietnam', PH: 'Philippines', HK: 'Hong Kong', TW: 'Taiwan',
  AU: 'Australia', NZ: 'New Zealand',
  IL: 'Israel', SA: 'Saudi Arabia', AE: 'United Arab Emirates', QA: 'Qatar',
  KW: 'Kuwait', BH: 'Bahrain', OM: 'Oman', JO: 'Jordan', LB: 'Lebanon', EG: 'Egypt',
  // Africa
  ZA: 'South Africa', MA: 'Morocco', TN: 'Tunisia', KE: 'Kenya',
  NG: 'Nigeria', GH: 'Ghana', ET: 'Ethiopia',
};

/** True when `code` is a syntactically valid ISO 3166-1 alpha-2 code. */
function isIso2(code: string): boolean {
  return /^[A-Za-z]{2}$/.test(code);
}

export const COUNTRY_NAME = (code?: string): string => {
  if (!code) return '—';
  const upper = code.trim().toUpperCase();
  if (COUNTRY_NAMES[upper]) return COUNTRY_NAMES[upper];
  // Fall through to a humanized version of the raw value (e.g. "GERMANY" → "Germany").
  if (upper.length > 2) return upper.charAt(0) + upper.slice(1).toLowerCase();
  return upper;
};

/** Flag image from flagcdn.com (public CDN). Falls back to a globe glyph for
 *  values that aren't a valid ISO 3166-1 alpha-2 code (so we never request a
 *  flag the CDN can't serve). */
export function CountryFlag({ code, className = '' }: { code: string; className?: string }) {
  const raw = (code || '').trim();
  if (!raw || !isIso2(raw)) {
    return (
      <span
        className={`inline-block text-base leading-none ${className}`}
        title={raw ? `Unrecognized country code: ${raw}` : 'Missing country'}
        aria-hidden
      >
        🌍
      </span>
    );
  }
  const lc = raw.toLowerCase();
  return (
    <img
      src={`https://flagcdn.com/w40/${lc}.png`}
      srcSet={`https://flagcdn.com/w40/${lc}.png 1x, https://flagcdn.com/w80/${lc}.png 2x`}
      alt={`${COUNTRY_NAME(raw)} flag`}
      width={20}
      height={15}
      className={`inline-block rounded-[2px] object-cover shadow-[0_0_0_1px_rgba(15,23,42,0.06)] ${className}`}
      loading="lazy"
    />
  );
}

// ── Formatting ─────────────────────────────────────────────────────────────

export function fmtNum(n: number | undefined): string {
  return typeof n === 'number' && Number.isFinite(n) ? n.toLocaleString() : '—';
}

export function fmtPct(n: number | undefined): string {
  return typeof n === 'number' && Number.isFinite(n) ? `${n}%` : '—';
}

// ── Pills ──────────────────────────────────────────────────────────────────

export function Pill({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${className}`}>
      {children}
    </span>
  );
}

export function ConnectedPill() {
  return <Pill className="bg-emerald-50 text-emerald-700 ring-emerald-200">live</Pill>;
}

export function OnHoldPill() {
  return <Pill className="bg-amber-50 text-amber-700 ring-amber-200">on hold</Pill>;
}

// ── KPI card ───────────────────────────────────────────────────────────────

type KpiTone = 'default' | 'success' | 'warning' | 'accent' | 'danger' | 'teal';

interface KpiProps {
  label: string;
  value: string | number;
  sub: string;
  tone?: KpiTone;
  onHold?: boolean;
}

export function Kpi({ label, value, sub, tone = 'default', onHold = false }: KpiProps) {
  const valueColor: Record<KpiTone, string> = {
    default: 'text-slate-900',
    success: 'text-emerald-700',
    warning: 'text-amber-700',
    accent: 'text-accent-700',
    danger: 'text-rose-700',
    teal: 'text-teal-700',
  };
  const dot: Record<KpiTone, string> = {
    default: 'bg-slate-200',
    success: 'bg-emerald-500',
    warning: 'bg-amber-500',
    accent: 'bg-accent-500',
    danger: 'bg-rose-500',
    teal: 'bg-teal-500',
  };
  return (
    <div className="relative rounded-lg border border-slate-200 bg-white px-4 py-3 transition-colors hover:border-slate-300">
      <span className={`absolute right-3 top-3 block h-1.5 w-1.5 rounded-full ${dot[tone]}`} aria-hidden />
      <div className="flex items-center gap-1.5">
        <div className="truncate text-[10px] font-semibold uppercase tracking-widest text-slate-500">{label}</div>
        {onHold && (
          <span className="rounded bg-amber-50 px-1 text-[9px] font-semibold uppercase tracking-wider text-amber-700 ring-1 ring-inset ring-amber-200" title="No data available yet">
            on hold
          </span>
        )}
      </div>
      <div className={`mt-1 text-[28px] font-semibold leading-none tracking-tight tabular-nums ${onHold ? 'text-slate-400' : valueColor[tone]}`}>
        {value}
      </div>
      <div className="mt-1.5 truncate text-[11px] text-slate-500">{sub}</div>
    </div>
  );
}

// ── Section heading ────────────────────────────────────────────────────────

export function SectionHeading({ label }: { label: string }) {
  return <h4 className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-slate-500">{label}</h4>;
}

// ── Mini stat (for sub-pages) ──────────────────────────────────────────────

type MiniTone = 'default' | 'success' | 'warning' | 'danger' | 'accent';

export function MiniStat({ label, value, tone = 'default' }: { label: string; value: string; tone?: MiniTone }) {
  const color: Record<MiniTone, string> = {
    default: 'text-slate-900',
    success: 'text-emerald-700',
    warning: 'text-amber-700',
    danger: 'text-rose-700',
    accent: 'text-accent-700',
  };
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">{label}</div>
      <div className={`mt-0.5 text-lg font-semibold tabular-nums ${color[tone]}`}>{value}</div>
    </div>
  );
}

// ── Avatar helpers ─────────────────────────────────────────────────────────

const OWNER_TONES = [
  'bg-accent-100 text-accent-700',
  'bg-emerald-100 text-emerald-700',
  'bg-amber-100 text-amber-700',
  'bg-sky-100 text-sky-700',
  'bg-rose-100 text-rose-700',
  'bg-accent-100 text-accent-700',
];

export function ownerTone(userId: string): string {
  let hash = 5381;
  for (let i = 0; i < userId.length; i++) hash = ((hash << 5) + hash + userId.charCodeAt(i)) | 0;
  return OWNER_TONES[Math.abs(hash) % OWNER_TONES.length]!;
}

export function ownerInitials(userId: string): string {
  return userId.replace(/[^A-Za-z0-9]/g, '').slice(0, 2).toUpperCase() || '??';
}

// ── Page header bar (eyebrow + title + actions) ────────────────────────────

export function OpsPageActions({ days, onDaysChange, onExport }: { days: number; onDaysChange: (d: number) => void; onExport?: () => void }) {
  return (
    <div className="flex items-center gap-2">
      <select
        value={days}
        onChange={(e) => onDaysChange(Number(e.target.value))}
        className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
      >
        <option value={7}>Last 7 days</option>
        <option value={30}>Last 30 days</option>
        <option value={90}>Last 90 days</option>
      </select>
      <Button unstyled
        type="button"
        onClick={onExport ?? (() => alert('Export — not yet wired'))}
        className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
      >
        ⇣ Export
      </Button>
    </div>
  );
}
