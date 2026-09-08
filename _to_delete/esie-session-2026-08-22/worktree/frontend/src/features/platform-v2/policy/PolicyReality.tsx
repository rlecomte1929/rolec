/**
 * PolicyReality.tsx — T11 Policy Reality (S5c) /policy/reality
 * Employee-facing. Cost reality view: policy entitlement vs actual estimate.
 */

import type { PolicyBenefit, BenefitValueType, CorridorCode } from '../../../types/relopass-api-contracts';
import { Button } from '../../../components/antigravity/Button';
// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface PolicyRealityRow {
  benefit: PolicyBenefit;
  actual_estimate: string;
  currency?: string | null;
}

export interface PolicyRealityProps {
  corridor: CorridorCode;
  corridorLabel: string;
  rows: PolicyRealityRow[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Value formatting
// ─────────────────────────────────────────────────────────────────────────────

function parseNumeric(value: string): number | null {
  const n = parseFloat(value.replace(/[^0-9.-]/g, ''));
  return isNaN(n) ? null : n;
}

function formatValue(value: string, type: BenefitValueType, currency?: string | null): string {
  if (type === 'boolean') return value === 'true' ? 'Included' : 'Not included';
  if (type === 'days') {
    const n = parseNumeric(value);
    return n !== null ? `${n} days` : value;
  }
  if (type === 'currency') {
    const n = parseNumeric(value);
    if (n !== null) {
      return new Intl.NumberFormat(undefined, {
        style: 'currency', currency: currency ?? 'EUR', maximumFractionDigits: 0,
      }).format(n);
    }
    return value;
  }
  return value;
}

function computeDelta(
  policyValue: string,
  actualValue: string,
  type: BenefitValueType,
  currency?: string | null,
): { formatted: string; positive: boolean } | null {
  if (type === 'boolean' || type === 'text') return null;

  const p = parseNumeric(policyValue);
  const a = parseNumeric(actualValue);
  if (p === null || a === null) return null;

  const diff = a - p;
  const positive = diff >= 0;

  if (type === 'days') {
    return { formatted: `${positive ? '+' : ''}${diff} days`, positive };
  }
  if (type === 'currency') {
    const formatted = new Intl.NumberFormat(undefined, {
      style: 'currency', currency: currency ?? 'EUR', maximumFractionDigits: 0,
    }).format(Math.abs(diff));
    return { formatted: `${positive ? '+' : '-'}${formatted}`, positive };
  }
  return null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Row Component
// ─────────────────────────────────────────────────────────────────────────────

interface RealityRowProps {
  row: PolicyRealityRow;
}

function RealityRow({ row }: RealityRowProps) {
  const { benefit, actual_estimate, currency } = row;
  const policyFormatted = formatValue(benefit.benefit_value, benefit.value_type, benefit.currency ?? currency);
  const actualFormatted = formatValue(actual_estimate, benefit.value_type, benefit.currency ?? currency);
  const delta = computeDelta(benefit.benefit_value, actual_estimate, benefit.value_type, benefit.currency ?? currency);

  return (
    <tr style={{ borderBottom: '1px solid var(--border)' }}>
      <td style={{ padding: '14px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <p style={{ margin: 0, fontWeight: 600, fontSize: '14px', color: 'var(--text)' }}>{benefit.name}</p>
            {benefit.description && (
              <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-muted)' }}>{benefit.description}</p>
            )}
          </div>
        </div>
      </td>

      {/* Policy value */}
      <td style={{ padding: '14px 16px', fontWeight: 600, fontSize: '14px', color: 'var(--text)' }}>
        {policyFormatted}
      </td>

      {/* Actual estimate */}
      <td style={{ padding: '14px 16px', fontWeight: 600, fontSize: '14px', color: 'var(--text-secondary)' }}>
        {actualFormatted}
      </td>

      {/* Difference */}
      <td style={{ padding: '14px 16px', textAlign: 'right' }}>
        {delta ? (
          <span style={{
            fontWeight: 700,
            fontSize: '13px',
            color: delta.positive ? 'var(--success)' : 'var(--danger)',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '3px',
          }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d={delta.positive ? 'M5 15l7-7 7 7' : 'M19 9l-7 7-7-7'} />
            </svg>
            {delta.formatted}
          </span>
        ) : (
          <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>—</span>
        )}
      </td>
    </tr>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Summary totals
// ─────────────────────────────────────────────────────────────────────────────

function SummaryBar({ rows }: { rows: PolicyRealityRow[] }) {
  const currencyRows = rows.filter(r => r.benefit.value_type === 'currency');
  if (currencyRows.length === 0) return null;

  const policyTotal = currencyRows.reduce((sum, r) => sum + (parseNumeric(r.benefit.benefit_value) ?? 0), 0);
  const actualTotal = currencyRows.reduce((sum, r) => sum + (parseNumeric(r.actual_estimate) ?? 0), 0);
  const diff = actualTotal - policyTotal;
  const positive = diff >= 0;

  const fmt = (n: number) => new Intl.NumberFormat(undefined, { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n);

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '32px',
      padding: '16px 20px',
      background: 'var(--surface-2)',
      borderTop: '2px solid var(--border)',
    }}>
      <div style={{ textAlign: 'right' }}>
        <p style={{ margin: '0 0 2px', fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Policy total</p>
        <p style={{ margin: 0, fontWeight: 700, fontSize: '18px', color: 'var(--text)' }}>{fmt(policyTotal)}</p>
      </div>
      <div style={{ textAlign: 'right' }}>
        <p style={{ margin: '0 0 2px', fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Actual estimate</p>
        <p style={{ margin: 0, fontWeight: 700, fontSize: '18px', color: 'var(--text-secondary)' }}>{fmt(actualTotal)}</p>
      </div>
      <div style={{ textAlign: 'right', minWidth: '120px' }}>
        <p style={{ margin: '0 0 2px', fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Difference</p>
        <p style={{ margin: 0, fontWeight: 700, fontSize: '18px', color: positive ? 'var(--success)' : 'var(--danger)' }}>
          {positive ? '+' : ''}{fmt(diff)}
        </p>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function PolicyReality({ corridor, corridorLabel, rows }: PolicyRealityProps) {
  function handleExportPdf() {
    const event = new CustomEvent('rp:export-pdf', {
      detail: { corridor, rows },
      bubbles: true,
    });
    document.dispatchEvent(event);
  }

  return (
    <div style={{ padding: '24px', maxWidth: '1000px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '24px', gap: '16px', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ margin: '0 0 4px', fontSize: '22px', fontWeight: 700, color: 'var(--text)' }}>
            What your relocation actually costs
          </h1>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '4px 10px', background: 'var(--surface-2)', borderRadius: 'var(--radius-full)', border: '1px solid var(--border)' }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)' }}>{corridorLabel}</span>
          </div>
        </div>

        <Button unstyled
          onClick={handleExportPdf}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: '6px',
            padding: '9px 16px',
            borderRadius: 'var(--radius-md, 8px)',
            border: '1px solid var(--border)',
            background: 'var(--surface)',
            color: 'var(--text-secondary)',
            fontWeight: 600, fontSize: '13px', cursor: 'pointer',
            transition: 'border-color 0.15s, background 0.15s',
          }}
          onMouseEnter={e => {
            (e.currentTarget as HTMLElement).style.borderColor = 'var(--accent)';
            (e.currentTarget as HTMLElement).style.color = 'var(--accent)';
          }}
          onMouseLeave={e => {
            (e.currentTarget as HTMLElement).style.borderColor = 'var(--border)';
            (e.currentTarget as HTMLElement).style.color = 'var(--text-secondary)';
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Download as PDF
        </Button>
      </div>

      {/* Table */}
      <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg, 12px)', overflow: 'hidden' }}>
        {rows.length === 0 ? (
          <div style={{ padding: '48px' }}>
            <p style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '15px' }}>
              No data available yet. Estimates are generated once your corridor is confirmed.
            </p>
          </div>
        ) : (
          <>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
              <thead>
                <tr style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                  {[
                    { label: 'Benefit', align: 'left' as const },
                    { label: 'Policy entitlement', align: 'left' as const },
                    { label: 'Actual estimate', align: 'left' as const },
                    { label: 'Difference', align: 'right' as const },
                  ].map(h => (
                    <th key={h.label} style={{ padding: '12px 16px', textAlign: h.align, fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', whiteSpace: 'nowrap' }}>
                      {h.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map(row => (
                  <RealityRow key={row.benefit.id} row={row} />
                ))}
              </tbody>
            </table>
            <SummaryBar rows={rows} />
          </>
        )}
      </div>

      {/* Source note */}
      <p style={{ margin: '16px 0 0', fontSize: '12px', color: 'var(--text-muted)', textAlign: 'center' }}>
        Estimates based on market data for{' '}
        <strong style={{ color: 'var(--text-secondary)' }}>{corridorLabel}</strong>.
        Figures are indicative and may vary depending on local conditions.
      </p>
    </div>
  );
}

export default PolicyReality;
