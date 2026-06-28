/**
 * IntakeWizard.tsx — ReloPass Case Intake Wizard (S1n)
 * ─────────────────────────────────────────────────────────────────────────────
 * 6 questions across 3 sections:
 *   Basics     — origin country · destination country + city
 *   Employment — purpose · employee type · contract duration
 *   Family     — family configuration
 *
 * On submit: POST /cases (CreateCaseRequest) → redirect to /cases/:id/discovery
 *
 * Features:
 *  - Country searchable dropdown with flag emoji
 *  - AI tooltip per question (ai: string from INTAKE_QUESTIONS)
 *  - Progress dots + percentage bar
 *  - "Quick fill" demo preset
 *  - Validation blocks Next when required field is empty
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Input } from '../../../components/antigravity/Input';
import { Button } from '../../../components/antigravity/Button';
import { countryFlag } from '../shared';
import type { CreateCaseRequest } from '../../../types/relopass-api-contracts';

// ─── Types ────────────────────────────────────────────────────────────────────

type QuestionKind = 'country' | 'country_city' | 'choice' | 'select';

interface IntakeOption {
  id: string;
  label: string;
  description?: string;
  icon?: string;
}

interface IntakeQuestion {
  id: string;
  section: 'basics' | 'employment' | 'family';
  label: string;
  hint: string;
  /** Tooltip shown by AI indicator */
  ai: string;
  kind: QuestionKind;
  required: boolean;
  options?: IntakeOption[];
}

type IntakeAnswers = Record<string, string | null>;

// ─── INTAKE_QUESTIONS ─────────────────────────────────────────────────────────

const INTAKE_QUESTIONS: IntakeQuestion[] = [
  {
    id: 'origin_country',
    section: 'basics',
    label: 'Where is the employee relocating from?',
    hint: 'The country they currently live and work in.',
    ai: 'This determines which documents are required, bilateral treaties that apply, and the origin-side checklist for tax and deregistration.',
    kind: 'country',
    required: true,
  },
  {
    id: 'destination',
    section: 'basics',
    label: 'Where are they moving to?',
    hint: 'Country and city of the destination.',
    ai: 'The destination country and city determines the visa pathway, right-to-work rules, housing market, and all local service vendors we can assign.',
    kind: 'country_city',
    required: true,
  },
  {
    id: 'purpose',
    section: 'employment',
    label: 'What is the reason for the relocation?',
    hint: 'Select the primary employment purpose.',
    ai: 'The relocation purpose changes which immigration pathway applies — work permit, intra-company transfer, EU free movement, or self-employment each have distinct tracks.',
    kind: 'choice',
    required: true,
    options: [
      { id: 'work_permit',     label: 'New work permit',       description: 'Applying for a work permit in the destination country', icon: '📋' },
      { id: 'ict',             label: 'Intra-company transfer', description: 'Moving within the same company or group',                icon: '🏢' },
      { id: 'eu_mobility',     label: 'EU free movement',      description: 'EU/EEA citizen exercising free movement rights',         icon: '🇪🇺' },
      { id: 'self_employed',   label: 'Self-employed / freelance', description: 'Registering as self-employed in the destination',     icon: '💼' },
    ],
  },
  {
    id: 'employee_type',
    section: 'employment',
    label: 'What type of employment contract do they have?',
    hint: 'The employment structure affects which policy tier applies.',
    ai: 'Permanent employees often receive full relocation packages; fixed-term and contractors have different policy entitlements and tax treatment.',
    kind: 'choice',
    required: true,
    options: [
      { id: 'permanent',    label: 'Permanent employee',   icon: '👤' },
      { id: 'fixed_term',   label: 'Fixed-term contract',  icon: '📅' },
      { id: 'contractor',   label: 'Contractor / C2C',     icon: '🤝' },
      { id: 'intern',       label: 'Intern / Apprentice',  icon: '🎓' },
    ],
  },
  {
    id: 'contract_duration',
    section: 'employment',
    label: 'How long is the assignment?',
    hint: 'Approximate duration of the relocation.',
    ai: 'Assignment length determines whether a temporary or permanent visa is appropriate, and triggers different tax equalisation and repatriation provisions.',
    kind: 'choice',
    required: true,
    options: [
      { id: 'lt_3m',   label: 'Under 3 months',   description: 'Short-term assignment', icon: '⚡' },
      { id: '3_12m',   label: '3 – 12 months',    description: 'Medium assignment',      icon: '📆' },
      { id: '1_3y',    label: '1 – 3 years',      description: 'Standard assignment',    icon: '🗓️' },
      { id: 'gt_3y',   label: 'More than 3 years', description: 'Long-term / permanent', icon: '🏠' },
    ],
  },
  {
    id: 'family_config',
    section: 'family',
    label: 'Who is relocating with the employee?',
    hint: 'Accompanying family members affect visa requirements, housing, and schooling.',
    ai: 'Accompanying dependants require their own visa applications, school enrollment, and insurance coverage. Knowing this upfront lets me pre-build the right roadmap tracks.',
    kind: 'choice',
    required: true,
    options: [
      { id: 'solo',          label: 'Just the employee',             icon: '🧳' },
      { id: 'partner',       label: 'Employee + partner',            icon: '👫' },
      { id: 'partner_kids',  label: 'Employee + partner + children', icon: '👨‍👩‍👧' },
      { id: 'kids',          label: 'Employee + children (no partner)', icon: '👨‍👧' },
    ],
  },
];

const SECTIONS = [
  { key: 'basics',      label: 'Basics' },
  { key: 'employment',  label: 'Employment' },
  { key: 'family',      label: 'Family' },
] as const;

// Country list (seeded from DB)
const COUNTRIES = [
  { code: 'FR', name: 'France' }, { code: 'DE', name: 'Germany' },
  { code: 'GB', name: 'United Kingdom' }, { code: 'US', name: 'United States' },
  { code: 'NL', name: 'Netherlands' }, { code: 'ES', name: 'Spain' },
  { code: 'IT', name: 'Italy' }, { code: 'PT', name: 'Portugal' },
  { code: 'BE', name: 'Belgium' }, { code: 'SE', name: 'Sweden' },
  { code: 'CH', name: 'Switzerland' }, { code: 'AE', name: 'UAE' },
  { code: 'SG', name: 'Singapore' }, { code: 'AU', name: 'Australia' },
  { code: 'CA', name: 'Canada' }, { code: 'JP', name: 'Japan' },
];

// Quick-fill demo preset
const QUICK_FILL: IntakeAnswers = {
  origin_country: 'FR',
  destination_country: 'DE',
  destination_city: 'Berlin',
  purpose: 'ict',
  employee_type: 'permanent',
  contract_duration: '1_3y',
  family_config: 'partner',
};

// ─── Props ────────────────────────────────────────────────────────────────────

export interface IntakeWizardProps {
  /** ID of the case being created, or null to create a new case on submit */
  case_id?: string | null;
  employee_id: string;
  onComplete: (caseId: string) => void;
  onCancel?: () => void;
}

// ─── CountryDropdown ──────────────────────────────────────────────────────────

function CountryDropdown({
  id,
  value,
  onChange,
  placeholder,
}: {
  id: string;
  value: string;
  onChange: (code: string) => void;
  placeholder?: string;
}) {
  const [search, setSearch] = useState('');
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const filtered = COUNTRIES.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.code.toLowerCase().includes(search.toLowerCase())
  );

  const selected = COUNTRIES.find(c => c.code === value);

  useEffect(() => {
    if (!open) return;
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <Button unstyled
        id={id}
        type="button"
        onClick={() => { setOpen(v => !v); setSearch(''); }}
        style={{
          width: '100%',
          padding: '11px 14px',
          borderRadius: 'var(--radius-md)',
          border: `1px solid ${value ? 'var(--border-default)' : 'var(--border-default)'}`,
          background: 'var(--surface)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          cursor: 'pointer',
          textAlign: 'left',
          fontSize: '14px',
          color: selected ? 'var(--text-primary)' : 'var(--text-tertiary)',
          transition: 'border-color var(--transition-fast)',
        }}
        onFocus={e => (e.currentTarget as HTMLElement).style.borderColor = 'var(--accent-border)'}
        onBlur={e => (e.currentTarget as HTMLElement).style.borderColor = 'var(--border-default)'}
      >
        {selected ? (
          <>
            <span aria-hidden="true" style={{ fontSize: '18px' }}>{countryFlag(selected.code)}</span>
            <span>{selected.name}</span>
            <span style={{ marginLeft: 'auto', fontSize: '12px', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{selected.code}</span>
          </>
        ) : (
          <span>{placeholder ?? 'Select a country…'}</span>
        )}
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ marginLeft: selected ? '0' : 'auto', transform: open ? 'rotate(180deg)' : 'none', transition: 'transform var(--transition-fast)', flexShrink: 0, color: 'var(--text-tertiary)' }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </Button>

      {open && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 4px)',
          left: 0,
          right: 0,
          background: 'var(--surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-lg)',
          zIndex: 200,
          overflow: 'hidden',
        }}>
          <div style={{ padding: '8px' }}>
            {/* eslint-disable jsx-a11y/no-autofocus */}
            {/* dropdown search: focus input when popover opens for keyboard users */}
            <Input unstyled
              autoFocus
              value={search}
              onChange={v => setSearch(v)}
              placeholder="Search countries…"
              style={{
                width: '100%',
                padding: '8px 10px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                background: 'var(--surface-hover)',
                color: 'var(--text-primary)',
                fontSize: '13px',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
            {/* eslint-enable jsx-a11y/no-autofocus */}
          </div>
          <div style={{ maxHeight: '240px', overflowY: 'auto' }}>
            {filtered.length === 0 ? (
              <p style={{ padding: '12px 14px', fontSize: '13px', color: 'var(--text-tertiary)', margin: 0 }}>No countries found</p>
            ) : filtered.map(c => (
              <Button unstyled
                key={c.code}
                type="button"
                onClick={() => { onChange(c.code); setOpen(false); setSearch(''); }}
                style={{
                  width: '100%',
                  padding: '9px 14px',
                  background: c.code === value ? 'var(--accent-soft)' : 'none',
                  border: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  fontSize: '13px',
                  color: c.code === value ? 'var(--accent)' : 'var(--text-primary)',
                  textAlign: 'left',
                  transition: 'background var(--transition-fast)',
                }}
                onMouseEnter={e => { if (c.code !== value) (e.currentTarget as HTMLElement).style.background = 'var(--surface-hover)'; }}
                onMouseLeave={e => { if (c.code !== value) (e.currentTarget as HTMLElement).style.background = 'none'; }}
              >
                <span aria-hidden="true" style={{ fontSize: '18px' }}>{countryFlag(c.code)}</span>
                <span style={{ flex: 1 }}>{c.name}</span>
                <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>{c.code}</span>
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── AITooltip ────────────────────────────────────────────────────────────────

function AITooltip({ text }: { text: string }) {
  const [visible, setVisible] = useState(false);
  return (
    <span style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
      <Button unstyled
        type="button"
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onFocus={() => setVisible(true)}
        onBlur={() => setVisible(false)}
        aria-label="AI explanation"
        style={{
          background: 'var(--accent-soft)',
          border: '1px solid var(--accent-border)',
          borderRadius: 'var(--radius-full)',
          color: 'var(--accent)',
          width: '20px',
          height: '20px',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          flexShrink: 0,
        }}
      >
        {/* Sparkles micro icon */}
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
          <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
        </svg>
      </Button>
      {visible && (
        <div
          role="tooltip"
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 8px)',
            left: '50%',
            transform: 'translateX(-50%)',
            width: '280px',
            padding: '10px 12px',
            background: 'var(--surface)',
            border: '1px solid var(--accent-border)',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-lg)',
            fontSize: '12px',
            color: 'var(--text-secondary)',
            lineHeight: 1.5,
            zIndex: 300,
            pointerEvents: 'none',
          }}
        >
          <span style={{ display: 'block', fontSize: '10px', fontWeight: 700, color: 'var(--accent)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Why we ask this
          </span>
          {text}
        </div>
      )}
    </span>
  );
}

// ─── IntakeWizard ─────────────────────────────────────────────────────────────

export function IntakeWizard({ case_id: _case_id, employee_id, onComplete, onCancel }: IntakeWizardProps) {
  const [step, setStep] = useState(0); // 0–5
  const [answers, setAnswers] = useState<IntakeAnswers>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const totalSteps = INTAKE_QUESTIONS.length;
  // step is clamped to [0, totalSteps-1] by handleNext/handleBack, and
  // INTAKE_QUESTIONS is a non-empty module-level constant, so this is always defined.
  const question = INTAKE_QUESTIONS[step]!;
  const progress = Math.round(((step) / totalSteps) * 100);

  const answer = (key: string) => answers[key] ?? '';

  const setAnswer = useCallback((key: string, val: string) => {
    setAnswers(prev => ({ ...prev, [key]: val }));
    setError('');
  }, []);

  const quickFill = useCallback(() => {
    setAnswers(QUICK_FILL);
  }, []);

  // Validate current step
  const isValid = useCallback((): boolean => {
    if (!question.required) return true;
    if (question.id === 'destination') {
      return !!answers['destination_country'] && !!answers['destination_city']?.trim();
    }
    return !!answers[question.id];
  }, [question, answers]);

  const handleNext = useCallback(() => {
    if (!isValid()) {
      setError('Please complete this field before continuing.');
      return;
    }
    if (step < totalSteps - 1) {
      setStep(s => s + 1);
      setError('');
    }
  }, [isValid, step, totalSteps]);

  const handleBack = useCallback(() => {
    if (step > 0) { setStep(s => s - 1); setError(''); }
  }, [step]);

  const handleSubmit = useCallback(async () => {
    if (!isValid()) { setError('Please complete this field.'); return; }
    setSubmitting(true);
    setError('');

    try {
      const body: CreateCaseRequest = {
        employee_id,
        origin_country_code: answers['origin_country'] ?? '',
        dest_country_code: answers['destination_country'] ?? '',
      };

      const res = await fetch('/api/cases', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({})) as { message?: string };
        throw new Error(err.message ?? `HTTP ${res.status}`);
      }

      const { data } = await res.json() as { data: { id: string } };
      onComplete(data.id);
    } catch (e) {
      setError((e as Error).message ?? 'Submission failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }, [isValid, answers, employee_id, onComplete]);

  // Keyboard next/back
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === 'Enter' && !e.shiftKey) {
        if (step < totalSteps - 1) handleNext();
        else void handleSubmit();
      }
      if (e.key === 'ArrowLeft' || (e.altKey && e.key === 'ArrowLeft')) handleBack();
    }
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [step, totalSteps, handleNext, handleBack, handleSubmit]);

  const currentSection = SECTIONS.find(s => s.key === question.section)!;
  const sectionIndex = SECTIONS.findIndex(s => s.key === question.section);

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'var(--bg)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--spacing-4)',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '720px',
          background: 'var(--surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-lg)',
          overflow: 'hidden',
        }}
      >
        {/* ── Header / Progress ── */}
        <div style={{ padding: 'var(--spacing-5) var(--spacing-6) var(--spacing-4)', borderBottom: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div>
              <p style={{ margin: '0 0 2px', fontSize: '12px', fontWeight: 600, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                {currentSection.label}
              </p>
              <h1 style={{ margin: 0, fontSize: '13px', color: 'var(--text-tertiary)' }}>
                Question {step + 1} of {totalSteps}
              </h1>
            </div>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
              {/* Quick fill */}
              <Button unstyled
                type="button"
                onClick={quickFill}
                style={{
                  padding: '5px 12px',
                  borderRadius: 'var(--radius-full)',
                  background: 'var(--surface-hover)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-secondary)',
                  fontSize: '12px',
                  cursor: 'pointer',
                  fontWeight: 500,
                  transition: 'all var(--transition-fast)',
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLElement).style.background = 'var(--accent-soft)';
                  (e.currentTarget as HTMLElement).style.borderColor = 'var(--accent-border)';
                  (e.currentTarget as HTMLElement).style.color = 'var(--accent)';
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLElement).style.background = 'var(--surface-hover)';
                  (e.currentTarget as HTMLElement).style.borderColor = 'var(--border-subtle)';
                  (e.currentTarget as HTMLElement).style.color = 'var(--text-secondary)';
                }}
              >
                ⚡ Quick fill
              </Button>
              {onCancel && (
                <Button unstyled type="button" onClick={onCancel} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', padding: '4px 8px', borderRadius: 'var(--radius-md)', fontSize: '13px' }}>
                  Cancel
                </Button>
              )}
            </div>
          </div>

          {/* Section breadcrumb dots */}
          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
            {SECTIONS.map((s, i) => (
              <span
                key={s.key}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '12px',
                  fontWeight: i === sectionIndex ? 600 : 400,
                  color: i < sectionIndex ? 'var(--accent)' : i === sectionIndex ? 'var(--text-primary)' : 'var(--text-tertiary)',
                }}
              >
                <span
                  aria-hidden="true"
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background: i < sectionIndex ? 'var(--accent)' : i === sectionIndex ? 'var(--accent)' : 'var(--border-subtle)',
                  }}
                />
                {s.label}
                {i < SECTIONS.length - 1 && (
                  <span style={{ color: 'var(--border-subtle)' }}>·</span>
                )}
              </span>
            ))}
            <span style={{ marginLeft: 'auto', fontSize: '12px', color: 'var(--text-tertiary)' }}>{progress}%</span>
          </div>

          {/* Progress bar */}
          <div style={{ height: '3px', borderRadius: '2px', background: 'var(--surface-hover)', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${Math.round(((step + 1) / totalSteps) * 100)}%`, background: 'var(--accent)', borderRadius: '2px', transition: 'width 0.3s ease' }} />
          </div>
        </div>

        {/* ── Question body ── */}
        <div style={{ padding: 'var(--spacing-6)' }}>
          {/* Question label */}
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', marginBottom: '8px' }}>
            <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.35, flex: 1 }}>
              {question.label}
            </h2>
            <AITooltip text={question.ai} />
          </div>

          <p style={{ margin: '0 0 24px', fontSize: '14px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {question.hint}
          </p>

          {/* ── Input by kind ── */}

          {question.kind === 'country' && (
            <CountryDropdown
              id={`q-${question.id}`}
              value={answer(question.id)}
              onChange={v => setAnswer(question.id, v)}
              placeholder="Search and select a country…"
            />
          )}

          {question.kind === 'country_city' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label htmlFor="dest-country" style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Country
                </label>
                <CountryDropdown
                  id="dest-country"
                  value={answer('destination_country')}
                  onChange={v => setAnswer('destination_country', v)}
                  placeholder="Select destination country…"
                />
              </div>
              <div>
                <label htmlFor="dest-city" style={{ display: 'block', fontSize: '13px', fontWeight: 500, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  City
                </label>
                <Input unstyled
                  id="dest-city"
                  type="text"
                  value={answer('destination_city')}
                  onChange={v => setAnswer('destination_city', v)}
                  placeholder="e.g. Berlin, Munich, Hamburg…"
                  style={{
                    width: '100%',
                    padding: '11px 14px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-default)',
                    background: 'var(--surface)',
                    color: 'var(--text-primary)',
                    fontSize: '14px',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                  onFocus={e => (e.target).style.borderColor = 'var(--accent-border)'}
                  onBlur={e => (e.target).style.borderColor = 'var(--border-default)'}
                />
              </div>
            </div>
          )}

          {(question.kind === 'choice' || question.kind === 'select') && question.options && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px' }}>
              {question.options.map(opt => {
                const selected = answer(question.id) === opt.id;
                return (
                  <Button unstyled
                    key={opt.id}
                    type="button"
                    onClick={() => setAnswer(question.id, opt.id)}
                    style={{
                      padding: '16px',
                      borderRadius: 'var(--radius-lg)',
                      border: `2px solid ${selected ? 'var(--accent)' : 'var(--border-subtle)'}`,
                      background: selected ? 'var(--accent-soft)' : 'var(--surface)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'all var(--transition-fast)',
                    }}
                    onMouseEnter={e => { if (!selected) (e.currentTarget as HTMLElement).style.borderColor = 'var(--accent-border)'; }}
                    onMouseLeave={e => { if (!selected) (e.currentTarget as HTMLElement).style.borderColor = 'var(--border-subtle)'; }}
                  >
                    {opt.icon && (
                      <span aria-hidden="true" style={{ display: 'block', fontSize: '22px', marginBottom: '8px' }}>{opt.icon}</span>
                    )}
                    <span style={{ display: 'block', fontSize: '14px', fontWeight: 600, color: selected ? 'var(--accent)' : 'var(--text-primary)', marginBottom: opt.description ? '4px' : 0 }}>
                      {opt.label}
                    </span>
                    {opt.description && (
                      <span style={{ display: 'block', fontSize: '12px', color: 'var(--text-tertiary)', lineHeight: 1.4 }}>
                        {opt.description}
                      </span>
                    )}
                  </Button>
                );
              })}
            </div>
          )}

          {/* Error */}
          {error && (
            <p role="alert" style={{ marginTop: '12px', color: 'var(--danger, #E53E3E)', fontSize: '13px' }}>
              {error}
            </p>
          )}
        </div>

        {/* ── Footer / Navigation ── */}
        <div
          style={{
            padding: 'var(--spacing-4) var(--spacing-6)',
            borderTop: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Button unstyled
            type="button"
            onClick={handleBack}
            disabled={step === 0}
            style={{
              padding: '9px 20px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-default)',
              background: 'var(--surface)',
              color: step === 0 ? 'var(--text-tertiary)' : 'var(--text-secondary)',
              fontSize: '14px',
              cursor: step === 0 ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              opacity: step === 0 ? 0.4 : 1,
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
            </svg>
            Back
          </Button>

          <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
            Press Enter ↵ to continue
          </span>

          {step < totalSteps - 1 ? (
            <Button unstyled
              type="button"
              onClick={handleNext}
              style={{
                padding: '9px 24px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--accent)',
                border: 'none',
                color: '#fff',
                fontSize: '14px',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              Continue
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
              </svg>
            </Button>
          ) : (
            <Button unstyled
              type="button"
              onClick={handleSubmit}
              disabled={submitting}
              style={{
                padding: '9px 24px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--accent)',
                border: 'none',
                color: '#fff',
                fontSize: '14px',
                fontWeight: 600,
                cursor: submitting ? 'not-allowed' : 'pointer',
                opacity: submitting ? 0.7 : 1,
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              {submitting && (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true" style={{ animation: 'rp-spin 0.8s linear infinite' }}>
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
              )}
              {submitting ? 'Creating case…' : 'Create case →'}
            </Button>
          )}
        </div>
      </div>

      <style>{`@keyframes rp-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

export default IntakeWizard;
