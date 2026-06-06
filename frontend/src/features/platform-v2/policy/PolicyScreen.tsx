/**
 * PolicyScreen.tsx — T09 Policy Screen (S5) /policy
 * Employee-facing. Policy tier + benefits + exception requests.
 */

import { useState } from 'react';
import { Input } from '../../../components/antigravity/Input';
import { Button } from '../../../components/antigravity/Button';
import type {
  PolicyTier,
  PolicyBenefit,
  PolicyException,
  BenefitValueType,
  ExceptionStatus,
} from '../../../types/relopass-api-contracts';
import { Pill, EmptyState, DateFormatter } from '../shared';
import type { PillVariant } from '../shared';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface PolicyScreenProps {
  tier: PolicyTier;
  benefits: PolicyBenefit[];
  exceptions: PolicyException[];
  onRequestException: (request: { benefit_name: string; requested_value: string; justification: string }) => Promise<void>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Benefit formatting
// ─────────────────────────────────────────────────────────────────────────────

function formatBenefitValue(value: string, type: BenefitValueType, currency?: string | null): string {
  if (type === 'boolean') return value === 'true' ? 'Yes' : 'No';
  if (type === 'days') return `${value} days`;
  if (type === 'currency') {
    const num = parseFloat(value);
    if (!isNaN(num)) {
      return new Intl.NumberFormat(undefined, { style: 'currency', currency: currency ?? 'EUR', maximumFractionDigits: 0 }).format(num);
    }
    return value;
  }
  return value;
}

const BENEFIT_CATEGORY_ICONS: Record<string, string> = {
  housing: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6',
  transport: 'M8 17a2 2 0 100-4 2 2 0 000 4zm8 0a2 2 0 100-4 2 2 0 000 4zM5 9l1.333-4H17.667L19 9H5zm0 0H3m16 0h2',
  school: 'M12 14l9-5-9-5-9 5 9 5zm0 0l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055',
  financial: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1',
  default: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
};

const EXCEPTION_STATUS_PILL: Record<ExceptionStatus, PillVariant> = {
  pending: 'warning',
  approved: 'success',
  denied: 'danger',
};

// ─────────────────────────────────────────────────────────────────────────────
// Benefit Table
// ─────────────────────────────────────────────────────────────────────────────

interface BenefitTableProps {
  benefits: PolicyBenefit[];
}

function BenefitTable({ benefits }: BenefitTableProps) {
  if (benefits.length === 0) {
    return <p style={{ fontSize: '14px', color: 'var(--text-muted)' }}>No benefits defined for this tier.</p>;
  }

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
      <thead>
        <tr style={{ borderBottom: '1px solid var(--border)' }}>
          {['Benefit', 'Value'].map(h => (
            <th key={h} style={{ padding: '10px 12px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {benefits.map(b => {
          const iconPath = BENEFIT_CATEGORY_ICONS[b.category] ?? BENEFIT_CATEGORY_ICONS.default;
          return (
            <tr key={b.id} style={{ borderBottom: '1px solid var(--border)' }}>
              <td style={{ padding: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d={iconPath} />
                  </svg>
                  <div>
                    <p style={{ margin: 0, fontWeight: 600, color: 'var(--text)' }}>{b.name}</p>
                    {b.description && (
                      <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-muted)' }}>{b.description}</p>
                    )}
                  </div>
                </div>
              </td>
              <td style={{ padding: '12px', fontWeight: 600, color: 'var(--text)', whiteSpace: 'nowrap' }}>
                {formatBenefitValue(b.benefit_value, b.value_type, b.currency)}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Exception Request Form
// ─────────────────────────────────────────────────────────────────────────────

interface ExceptionFormProps {
  benefits: PolicyBenefit[];
  onSubmit: (req: { benefit_name: string; requested_value: string; justification: string }) => Promise<void>;
  onCancel: () => void;
}

function ExceptionForm({ benefits, onSubmit, onCancel }: ExceptionFormProps) {
  const [benefitName, setBenefitName] = useState(benefits[0]?.name ?? '');
  const [requestedValue, setRequestedValue] = useState('');
  const [justification, setJustification] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!benefitName || !requestedValue || !justification) return;
    setSubmitting(true);
    try {
      await onSubmit({ benefit_name: benefitName, requested_value: requestedValue, justification });
    } finally {
      setSubmitting(false);
    }
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '8px 10px',
    borderRadius: 'var(--radius-md, 8px)',
    border: '1px solid var(--border)',
    background: 'var(--surface)',
    color: 'var(--text)',
    fontSize: '14px',
    outline: 'none',
    boxSizing: 'border-box',
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      <div>
        <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
          Benefit
        </label>
        <select value={benefitName} onChange={e => setBenefitName(e.target.value)} style={inputStyle}>
          {benefits.map(b => (
            <option key={b.id} value={b.name}>{b.name}</option>
          ))}
        </select>
      </div>
      <div>
        <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
          Requested value
        </label>
        <Input unstyled
          type="text"
          value={requestedValue}
          onChange={v => setRequestedValue(v)}
          placeholder="e.g. 90 days, €5000"
          required
          style={inputStyle}
        />
      </div>
      <div>
        <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
          Justification
        </label>
        <textarea
          value={justification}
          onChange={e => setJustification(e.target.value)}
          rows={4}
          placeholder="Explain why you need an exception to the standard policy…"
          required
          style={{ ...inputStyle, resize: 'vertical' }}
        />
      </div>
      <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
        <Button unstyled type="button" onClick={onCancel} style={{ padding: '8px 16px', borderRadius: 'var(--radius-md, 8px)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text-secondary)', fontSize: '14px', cursor: 'pointer' }}>
          Cancel
        </Button>
        <Button unstyled
          type="submit"
          disabled={submitting || !benefitName || !requestedValue || !justification}
          style={{ padding: '8px 16px', borderRadius: 'var(--radius-md, 8px)', border: 'none', background: 'var(--accent)', color: '#fff', fontWeight: 600, fontSize: '14px', cursor: submitting ? 'not-allowed' : 'pointer', opacity: submitting ? 0.7 : 1 }}
        >
          {submitting ? 'Submitting…' : 'Submit request'}
        </Button>
      </div>
    </form>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function PolicyScreen({ tier, benefits, exceptions, onRequestException }: PolicyScreenProps) {
  const [showForm, setShowForm] = useState(false);

  async function handleSubmitException(req: { benefit_name: string; requested_value: string; justification: string }) {
    await onRequestException(req);
    setShowForm(false);
  }

  return (
    <div style={{ padding: '24px', maxWidth: '1100px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ margin: '0 0 4px', fontSize: '22px', fontWeight: 700, color: 'var(--text)' }}>
          My Policy
        </h1>
        <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-muted)' }}>
          Your entitlements and benefit details for this relocation.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px', alignItems: 'start' }}>
        {/* Left: tier + benefits */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Tier card */}
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg, 12px)', padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
              <div style={{ width: '44px', height: '44px', borderRadius: 'var(--radius-md, 8px)', background: 'var(--accent-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
                </svg>
              </div>
              <div>
                <p style={{ margin: '0 0 2px', fontWeight: 700, fontSize: '18px', color: 'var(--text)' }}>
                  {tier.name}
                </p>
                <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-muted)' }}>
                  Rank {tier.rank} policy tier
                </p>
              </div>
            </div>
            {tier.description && (
              <p style={{ margin: '12px 0 0', fontSize: '14px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                {tier.description}
              </p>
            )}
            {tier.max_budget_eur !== null && (
              <p style={{ margin: '10px 0 0', fontSize: '14px', color: 'var(--text-secondary)' }}>
                <strong>Max budget:</strong>{' '}
                {new Intl.NumberFormat(undefined, { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(tier.max_budget_eur)}
              </p>
            )}
          </div>

          {/* Benefits */}
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg, 12px)', padding: '20px' }}>
            <h2 style={{ margin: '0 0 16px', fontSize: '15px', fontWeight: 700, color: 'var(--text)' }}>
              Benefits
            </h2>
            <BenefitTable benefits={benefits} />
          </div>
        </div>

        {/* Right: exceptions */}
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg, 12px)', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: 'var(--text)' }}>
              Exception Requests
            </h2>
            {!showForm && (
              <Button unstyled
                onClick={() => setShowForm(true)}
                style={{ padding: '6px 12px', borderRadius: 'var(--radius-md, 8px)', background: 'var(--accent)', color: '#fff', fontWeight: 600, fontSize: '12px', border: 'none', cursor: 'pointer' }}
              >
                + Request exception
              </Button>
            )}
          </div>

          {showForm && (
            <ExceptionForm
              benefits={benefits}
              onSubmit={handleSubmitException}
              onCancel={() => setShowForm(false)}
            />
          )}

          {!showForm && (
            <>
              {exceptions.length === 0 ? (
                <EmptyState
                  icon="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"
                  title="No exception requests"
                  description="Submit a request if your situation requires a benefit exception."
                />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {exceptions.map(ex => (
                    <div key={ex.id} style={{ padding: '12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-md, 8px)', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <p style={{ margin: 0, fontWeight: 600, fontSize: '13px', color: 'var(--text)' }}>
                          {ex.benefit_name}
                        </p>
                        <Pill variant={EXCEPTION_STATUS_PILL[ex.status]} size="sm">
                          {ex.status.charAt(0).toUpperCase() + ex.status.slice(1)}
                        </Pill>
                      </div>
                      <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-muted)' }}>
                        Requested: <strong style={{ color: 'var(--text-secondary)' }}>{ex.requested_value}</strong>
                        {' '}vs policy: <strong style={{ color: 'var(--text-secondary)' }}>{ex.approved_value ?? '—'}</strong>
                      </p>
                      <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                        {ex.justification}
                      </p>
                      {ex.created_at && (
                        <p style={{ margin: 0, fontSize: '11px', color: 'var(--text-disabled)' }}>
                          Submitted <DateFormatter date={ex.created_at} format="relative" />
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default PolicyScreen;
