/**
 * Document Data Sheet UI (Phase 2) — DataSheetFieldRow states + edit, and DataSheetView assembly.
 *
 * The field row is a leaf (antigravity primitives + a type-only import), so no api mock is
 * needed. The view is tested with useDataSheet mocked to a fixture.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';
import { DataSheetFieldRow } from '../DataSheetFieldRow';
import type { DataSheetField } from '../../../api/datasheet';

expect.extend(matchers);
afterEach(cleanup);

function field(o: Partial<DataSheetField> = {}): DataSheetField {
  return {
    fieldId: o.fieldId ?? 'f1',
    factKey: o.factKey ?? null,
    label: o.label ?? 'Label',
    category: o.category ?? null,
    source: o.source ?? 'needs_input',
    value: o.value ?? null,
    confidence: o.confidence ?? null,
    hint: o.hint ?? null,
    guidance: o.guidance ?? null,
    requiresOriginal: o.requiresOriginal ?? false,
    employerActionNote: o.employerActionNote ?? null,
  };
}

describe('DataSheetFieldRow', () => {
  it('consult-professional field shows guidance and no input', () => {
    render(
      <DataSheetFieldRow
        field={field({ source: 'consult_professional', label: 'Tax residency', guidance: 'Ask an advisor.' })}
        audience="employee"
        onSave={vi.fn()}
        saving={false}
      />,
    );
    expect(screen.getByText('Consult a professional')).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.getByText('Ask an advisor.')).toBeInTheDocument();
  });

  it('needs_input field is editable and Save calls onSave with (fieldId, value)', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <DataSheetFieldRow
        field={field({ fieldId: 'norwegian_address', source: 'needs_input', label: 'Address' })}
        audience="employee"
        onSave={onSave}
        saving={false}
      />,
    );
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'Storgata 1' } });
    fireEvent.click(screen.getByRole('button', { name: /Save/ }));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith('norwegian_address', 'Storgata 1'));
  });

  it('sourced value renders verbatim with a provenance badge and an Edit affordance', () => {
    render(
      <DataSheetFieldRow
        field={field({ source: 'intake', value: 'Camille Moreau', label: 'Full name' })}
        audience="employee"
        onSave={vi.fn()}
        saving={false}
      />,
    );
    expect(screen.getByText('Camille Moreau')).toBeInTheDocument();
    expect(screen.getByText('Provided')).toBeInTheDocument();
    // Not in an input until the user clicks Edit.
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Edit/ }));
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('readOnly needs_input field shows no input and no Save — a preview cannot be filled', () => {
    render(
      <DataSheetFieldRow
        field={field({ source: 'needs_input', label: 'Address', hint: 'Within 8 days of arrival' })}
        audience="employee"
        onSave={vi.fn()}
        saving={false}
        readOnly
      />,
    );
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Save/ })).not.toBeInTheDocument();
    expect(screen.getByText(/You'll provide this once the form opens/)).toBeInTheDocument();
    expect(screen.getByText('Within 8 days of arrival')).toBeInTheDocument();
  });

  it('HR audience surfaces the employer-action note; employee does not', () => {
    const f = field({ source: 'intake', value: 'x', employerActionNote: 'Employer retrieves the tax card.' });
    render(<DataSheetFieldRow field={f} audience="hr" onSave={vi.fn()} saving={false} />);
    expect(screen.getByText(/Employer retrieves the tax card\./)).toBeInTheDocument();
    cleanup();
    render(<DataSheetFieldRow field={f} audience="employee" onSave={vi.fn()} saving={false} />);
    expect(screen.queryByText(/Employer retrieves the tax card\./)).not.toBeInTheDocument();
  });
});

// ── DataSheetView with a mocked hook ─────────────────────────────────────────
const mockUseDataSheet = vi.fn();
vi.mock('../useDataSheet', () => ({ useDataSheet: (...args: unknown[]) => mockUseDataSheet(...args) }));
import { DataSheetView } from '../DataSheetView';

const FIXTURE = {
  caseRef: 'c1',
  employeeName: 'Camille Moreau',
  corridor: 'FR_NO',
  corridorLabel: 'FR→NO',
  movementBasis: null,
  generatedAt: '2026-09-09T00:00:00Z',
  completionPct: 92,
  needsInputCount: 1,
  banners: [{ type: 'moat-fact', text: 'Skattekort before first payroll or 50% withholding.' }],
  sections: [
    {
      stepId: 'd_number', title: 'D Number', authority: 'Skatteetaten', sourceUrl: 'https://skatteetaten.no',
      processNote: null, channels: [], order: 0, responsibleParty: null, slaNote: null, deadline: null,
      fields: [field({ fieldId: 'full_name', source: 'intake', value: 'Camille Moreau', label: 'Full name' })],
    },
  ],
  consultProfessional: [{ topic: 'Tax residency status', reason: 'A determination for a tax advisor.' }],
  covered: true,
};

describe('DataSheetView', () => {
  it('renders header, banner, section and consult panel when covered', () => {
    mockUseDataSheet.mockReturnValue({
      data: FIXTURE, loading: false, error: null, refetch: vi.fn(), saveField: vi.fn(), saving: false, saveError: null,
    });
    render(<DataSheetView caseId="c1" audience="employee" />);
    expect(screen.getByText('Your data sheet')).toBeInTheDocument();
    expect(screen.getByText('FR→NO')).toBeInTheDocument();
    expect(screen.getByText(/Skattekort before first payroll/)).toBeInTheDocument();
    expect(screen.getByText('D Number')).toBeInTheDocument();
    expect(screen.getByText('Tax residency status')).toBeInTheDocument();
  });

  it('preview sheet shows the preview notice and renders fields read-only', () => {
    mockUseDataSheet.mockReturnValue({
      data: {
        ...FIXTURE,
        preview: true,
        completionPct: 0,
        sections: [{
          stepId: 'DE:immigration.residence', title: 'Ausländerbehörde',
          authority: null, sourceUrl: 'https://example.gov', processNote: 'Arrival Week',
          channels: [], order: 0, responsibleParty: null, slaNote: null, deadline: null,
          fields: [field({ fieldId: 'DE:immigration.residence', source: 'needs_input', label: 'Register residence' })],
        }],
      },
      loading: false, error: null, refetch: vi.fn(), saveField: vi.fn(), saving: false, saveError: null,
    });
    render(<DataSheetView caseId="c1" audience="employee" />);
    expect(screen.getByText('Preview')).toBeInTheDocument();
    expect(screen.getByText(/guidance preview for FR→NO/)).toBeInTheDocument();
    // Read-only: no editable input for the needs_input field.
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('shows a "not available yet" message when not covered', () => {
    mockUseDataSheet.mockReturnValue({
      data: { ...FIXTURE, covered: false, sections: [] }, loading: false, error: null,
      refetch: vi.fn(), saveField: vi.fn(), saving: false, saveError: null,
    });
    render(<DataSheetView caseId="c1" audience="employee" />);
    expect(screen.getByText(/isn't available for this case yet/)).toBeInTheDocument();
  });
});
