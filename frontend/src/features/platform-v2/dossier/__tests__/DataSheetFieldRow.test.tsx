/**
 * [AIQ-1756] FR→NO Personal Relocation Data Sheet — dossier field rendering.
 *
 * Golden-fixture accuracy gate + the four data-sheet states:
 *   - value + source badge (intake / passport-OCR / prior-form / contract)
 *   - NEEDS INPUT for unsourced fields
 *   - CONSULT PROFESSIONAL (no value, no input) for the 5 flagged determinations
 *   - EN⇄NO toggle switches LABELS only; identifier VALUES stay verbatim
 *
 * FieldRow is a leaf UI component (antigravity primitives + a type-only import),
 * so no api-client mock is required.
 */
import { describe, it, expect, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup } from '@testing-library/react';
import type { FieldValueItem } from '../../../../api/formEditor';
import { FieldRow, type FieldLang } from '../../form-editor/FieldRow';

expect.extend(matchers);
afterEach(cleanup);

function field(o: Partial<FieldValueItem> = {}): FieldValueItem {
  return {
    field_id: o.field_id ?? 'f',
    label: o.label ?? 'Label',
    label_nb: o.label_nb ?? null,
    field_type: o.field_type ?? 'text',
    required: o.required ?? false,
    position: o.position ?? 1,
    prefill_source: o.prefill_source ?? null,
    requires_original: o.requires_original ?? false,
    consult_professional: o.consult_professional ?? false,
    options: o.options ?? null,
    value: o.value ?? null,
    filled_by: o.filled_by ?? null,
    ai_confidence: o.ai_confidence ?? null,
    source: o.source ?? null,
    reviewed: o.reviewed ?? false,
    overridden: o.overridden ?? false,
    section: o.section ?? null,
  };
}

function renderField(f: FieldValueItem, lang: FieldLang = 'en') {
  return render(
    <FieldRow field={f} liveValue={f.value ?? ''} onValueChange={() => {}} lang={lang} />,
  );
}

/** The input's current display value (works across text/date/number inputs). */
function inputValue(container: HTMLElement): string | undefined {
  return container.querySelector('input')?.value;
}

// ---------------------------------------------------------------------------
// Golden FR→NO case — known-correct answers (identifier values must be exact).
// Mirrors the seeded RP-NO-DATASHEET fields with one known relocating person.
// ---------------------------------------------------------------------------

const GOLDEN: FieldValueItem[] = [
  field({ field_id: 'full_name', label: 'Full legal name', label_nb: 'Fullt juridisk navn',
    prefill_source: 'profile.legal_full_name', value: 'Sophie Leblanc', source: 'intake_profile', filled_by: 'system', required: true }),
  field({ field_id: 'date_of_birth', label: 'Date of birth', label_nb: 'Fødselsdato', field_type: 'date',
    value: '1990-03-14', source: 'passport_ocr', filled_by: 'system', required: true }),
  field({ field_id: 'nationality', label: 'Nationality', label_nb: 'Statsborgerskap',
    value: 'FRA', source: 'passport_ocr', filled_by: 'system', required: true }),
  field({ field_id: 'id_document_number', label: 'Passport or EEA ID card number',
    value: '18AB56789', source: 'passport_ocr', filled_by: 'system', required: true, requires_original: true }),
  field({ field_id: 'id_document_expiry', label: 'ID document expiry date', field_type: 'date',
    value: '2031-07-22', source: 'passport_ocr', filled_by: 'system', required: true }),
  field({ field_id: 'employer_name', label: 'Employer in Norway',
    value: 'Statkraft AS', source: 'contract', filled_by: 'system', required: true }),
  field({ field_id: 'employer_org_number', label: 'Employer organisation number',
    value: '987654321', source: 'contract', filled_by: 'system', required: true }),
  field({ field_id: 'job_title', label: 'Job title',
    value: 'Ingénieur', source: 'contract', filled_by: 'system', required: true }),
  field({ field_id: 'employment_start_date', label: 'Employment start date', field_type: 'date',
    value: '2026-09-01', source: 'prior_form', filled_by: 'system', required: true }),
  field({ field_id: 'salary_amount_nok', label: 'Gross annual salary (NOK)', field_type: 'number',
    value: '780000', source: 'contract', filled_by: 'system', required: true }),
];

/** Every identifier value that must render exactly (0 wrong). */
const EXPECTED_VALUES: Record<string, string> = {
  full_name: 'Sophie Leblanc',
  date_of_birth: '1990-03-14',
  nationality: 'FRA',
  id_document_number: '18AB56789',
  id_document_expiry: '2031-07-22',
  employer_name: 'Statkraft AS',
  employer_org_number: '987654321',
  job_title: 'Ingénieur',
  employment_start_date: '2026-09-01',
  salary_amount_nok: '780000',
};

describe('AIQ-1756 — golden FR→NO data-sheet accuracy gate', () => {
  it('renders every identifier value exactly (0 wrong)', () => {
    for (const f of GOLDEN) {
      const { container, unmount } = renderField(f);
      expect(inputValue(container)).toBe(EXPECTED_VALUES[f.field_id]);
      unmount();
    }
  });

  it('renders every value byte-identical in Norwegian label mode (values never translate)', () => {
    for (const f of GOLDEN) {
      const { container, unmount } = renderField(f, 'nb');
      expect(inputValue(container)).toBe(EXPECTED_VALUES[f.field_id]);
      unmount();
    }
  });
});

// ---------------------------------------------------------------------------
// Source badges
// ---------------------------------------------------------------------------

describe('source badges', () => {
  it.each([
    ['intake_profile', 'From your intake'],
    ['contract', 'From your contract'],
    ['passport_ocr', 'From your passport scan'],
    ['prior_form', 'From a form you completed'],
  ])('shows the %s badge', (source, label) => {
    renderField(field({ value: 'X', source, filled_by: 'system' }));
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it('shows no source badge when source is null', () => {
    renderField(field({ value: 'typed by hand', filled_by: 'employee', source: null }));
    expect(screen.queryByText(/^From /)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// NEEDS INPUT
// ---------------------------------------------------------------------------

describe('NEEDS INPUT state', () => {
  it('shows Needs input + an editable control for an unsourced field', () => {
    const { container } = renderField(
      field({ field_id: 'arrival_date', label: 'Date of arrival in Norway', field_type: 'date',
        value: null, source: null, required: true }),
    );
    expect(screen.getByText('Needs input')).toBeInTheDocument();
    expect(container.querySelector('input')).not.toBeNull();
  });

  it('does NOT show Needs input once a value is present', () => {
    renderField(field({ value: 'FRA', source: 'passport_ocr', filled_by: 'system' }));
    expect(screen.queryByText('Needs input')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// CONSULT PROFESSIONAL
// ---------------------------------------------------------------------------

describe('CONSULT PROFESSIONAL state', () => {
  const consult = field({
    field_id: 'tax_residency_status',
    label: 'Tax-residency status determination',
    label_nb: 'Fastsettelse av skattemessig bosted',
    consult_professional: true,
    value: null,
    required: false,
  });

  it('shows the consult badge and advisor note', () => {
    renderField(consult);
    expect(screen.getByText('Consult a professional')).toBeInTheDocument();
    expect(screen.getByText(/regulated advisor will determine this/i)).toBeInTheDocument();
  });

  it('renders NO input and NO value for a consult field', () => {
    const { container } = renderField(consult);
    expect(container.querySelector('input')).toBeNull();
    expect(container.querySelector('select')).toBeNull();
  });

  it('never shows a source badge or Needs input for a consult field', () => {
    renderField(consult);
    expect(screen.queryByText(/^From /)).toBeNull();
    expect(screen.queryByText('Needs input')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// EN/NO label toggle — labels only
// ---------------------------------------------------------------------------

describe('EN/NO label toggle', () => {
  const f = field({
    field_id: 'full_name', label: 'Full legal name', label_nb: 'Fullt juridisk navn',
    value: 'Sophie Leblanc', source: 'intake_profile', filled_by: 'system',
  });

  it('shows the English label and value in EN mode', () => {
    const { container } = renderField(f, 'en');
    expect(screen.getByText('Full legal name')).toBeInTheDocument();
    expect(inputValue(container)).toBe('Sophie Leblanc');
  });

  it('switches the label to Norwegian while the value stays verbatim', () => {
    const { container } = renderField(f, 'nb');
    expect(screen.getByText('Fullt juridisk navn')).toBeInTheDocument();
    expect(screen.queryByText('Full legal name')).toBeNull();
    // The identifier value is NEVER translated.
    expect(inputValue(container)).toBe('Sophie Leblanc');
  });

  it('falls back to the English label when label_nb is absent', () => {
    const noNb = field({ label: 'Job title', label_nb: null, value: 'Ingénieur', source: 'contract' });
    renderField(noNb, 'nb');
    expect(screen.getByText('Job title')).toBeInTheDocument();
  });
});
