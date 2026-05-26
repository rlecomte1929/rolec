/**
 * DossierScreen.tsx — T08 Dossier Screen (S4) /dossier
 * Employee-facing. 7 form cards in a 2-column grid.
 */

import type { Form, FormType } from '../../../types/relopass-api-contracts';
import { StatusBadge, DateFormatter, EmptyState, Pill } from '../shared';
import { logger } from '../../../lib/logger';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface DossierScreenProps {
  forms: Form[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Form type metadata
// ─────────────────────────────────────────────────────────────────────────────

const FORM_TYPE_LABELS: Record<FormType, string> = {
  personal_info: 'Personal Information',
  family_declaration: 'Family Declaration',
  housing_request: 'Housing Request',
  tax_declaration_intent: 'Tax Declaration Intent',
  school_application: 'School Application',
  bank_account_opening: 'Bank Account Opening',
  vendor_briefing: 'Vendor Briefing',
  custom: 'Custom Form',
};

const FORM_TYPE_ICONS: Record<FormType, string> = {
  personal_info: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
  family_declaration: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z',
  housing_request: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6',
  tax_declaration_intent: 'M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2z',
  school_application: 'M12 14l9-5-9-5-9 5 9 5zm0 0l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z',
  bank_account_opening: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  vendor_briefing: 'M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
  custom: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2',
};

const FORM_TYPE_COLORS: Record<FormType, string> = {
  personal_info: 'var(--accent)',
  family_declaration: 'var(--info)',
  housing_request: 'var(--success)',
  tax_declaration_intent: 'var(--warning)',
  school_application: '#9B8DE8',
  bank_account_opening: 'var(--accent)',
  vendor_briefing: 'var(--info)',
  custom: 'var(--text-muted)',
};

// ─────────────────────────────────────────────────────────────────────────────
// Form Card
// ─────────────────────────────────────────────────────────────────────────────

interface FormCardProps {
  form: Form;
  onOpen: (formId: string) => void;
}

function FormCard({ form, onOpen }: FormCardProps) {
  const label = FORM_TYPE_LABELS[form.form_type] ?? form.form_type;
  const iconPath = FORM_TYPE_ICONS[form.form_type] ?? FORM_TYPE_ICONS.custom;
  const iconColor = FORM_TYPE_COLORS[form.form_type] ?? 'var(--accent)';
  const autoFilled = form.auto_filled_fields?.length ?? 0;

  function handleOpen() {
    const event = new CustomEvent('rp:open-form', { detail: { formId: form.id }, bubbles: true });
    document.dispatchEvent(event);
    onOpen(form.id);
  }

  return (
    <div
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg, 12px)',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        transition: 'border-color 0.15s, box-shadow 0.15s',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLElement).style.borderColor = 'var(--border-2)';
        (e.currentTarget as HTMLElement).style.boxShadow = '0 2px 8px rgba(0,0,0,0.06)';
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLElement).style.borderColor = 'var(--border)';
        (e.currentTarget as HTMLElement).style.boxShadow = 'none';
      }}
    >
      {/* Card header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
        <div style={{
          width: '40px', height: '40px', borderRadius: 'var(--radius-md, 8px)',
          background: `${iconColor}18`,
          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={iconColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d={iconPath} />
          </svg>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ margin: '0 0 4px', fontWeight: 700, fontSize: '15px', color: 'var(--text)' }}>
            {label}
          </p>
          <StatusBadge type="form" status={form.status} size="sm" />
        </div>
      </div>

      {/* Metadata */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
        {autoFilled > 0 && (
          <Pill
            size="sm"
            style={{
              background: 'rgba(29,191,162,0.1)',
              color: 'var(--accent-text)',
              border: '1px solid rgba(29,191,162,0.25)',
            }}
          >
            {autoFilled} field{autoFilled !== 1 ? 's' : ''} pre-filled
          </Pill>
        )}
        {form.updated_at && (
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Updated <DateFormatter date={form.updated_at} format="relative" />
          </span>
        )}
      </div>

      {/* Action */}
      <button
        onClick={handleOpen}
        style={{
          alignSelf: 'flex-start',
          padding: '8px 16px',
          borderRadius: 'var(--radius-md, 8px)',
          background: 'var(--accent)',
          color: '#fff',
          fontWeight: 600,
          fontSize: '13px',
          border: 'none',
          cursor: 'pointer',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          transition: 'background 0.15s',
        }}
        onMouseEnter={e => (e.currentTarget.style.background = 'var(--accent-hover)')}
        onMouseLeave={e => (e.currentTarget.style.background = 'var(--accent)')}
      >
        Open form
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M5 12h14m-7-7l7 7-7 7" />
        </svg>
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function DossierScreen({ forms }: DossierScreenProps) {
  function handleOpenForm(formId: string) {
    // Event already dispatched in FormCard; parent can wire up navigation here.
    logger.debug('[DossierScreen] open form', formId);
  }

  return (
    <div style={{ padding: '24px', maxWidth: '900px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ margin: '0 0 4px', fontSize: '22px', fontWeight: 700, color: 'var(--text)' }}>
          My Dossier
        </h1>
        <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-muted)' }}>
          Smart forms pre-filled from your intake and uploaded documents.
        </p>
      </div>

      {/* Summary row */}
      {forms.length > 0 && (
        <div style={{ display: 'flex', gap: '16px', marginBottom: '24px', flexWrap: 'wrap' }}>
          {[
            { label: 'Total', count: forms.length, color: 'var(--text-secondary)' },
            { label: 'Submitted', count: forms.filter(f => f.status === 'submitted').length, color: 'var(--success)' },
            { label: 'In progress', count: forms.filter(f => f.status === 'in_progress').length, color: 'var(--accent)' },
            { label: 'Not started', count: forms.filter(f => f.status === 'not_started').length, color: 'var(--text-muted)' },
          ].map(s => (
            <div key={s.label} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontWeight: 700, fontSize: '18px', color: s.color }}>{s.count}</span>
              <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>{s.label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Grid */}
      {forms.length === 0 ? (
        <EmptyState
          icon="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"
          title="No forms yet"
          description="Forms are generated once intake is complete."
        />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px' }}>
          {forms.map(form => (
            <FormCard key={form.id} form={form} onOpen={handleOpenForm} />
          ))}
        </div>
      )}
    </div>
  );
}

export default DossierScreen;
