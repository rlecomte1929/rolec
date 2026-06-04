/**
 * PrefillConfirmation — P2-03c.
 * Covers: shows every pre-filled value with source + confidence; lists
 * manual-completion fields; is impossible to skip (only Confirm); confirm fires.
 */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';

import { PrefillConfirmation } from '../PrefillConfirmation';
import type { FieldValueItem } from '../../../../api/formEditor';

afterEach(cleanup);

function field(over: Partial<FieldValueItem>): FieldValueItem {
  return {
    field_id: 'f1',
    label: 'Field',
    field_type: 'text',
    required: false,
    position: 0,
    prefill_source: 'intake.x',
    requires_original: false,
    options: null,
    value: 'v',
    filled_by: 'system',
    ai_confidence: 1,
    reviewed: false,
    overridden: false,
    section: null,
    ...over,
  };
}

const prefilled: FieldValueItem[] = [
  field({ field_id: 'fn', label: 'First name', value: 'Marc', ai_confidence: 1 }),
  field({ field_id: 'nat', label: 'Nationality', value: 'Canadian', ai_confidence: 0.5 }),
];

describe('PrefillConfirmation', () => {
  it('shows every pre-filled value with its intake source', () => {
    render(
      <PrefillConfirmation prefilledFields={prefilled} manualFields={[]} onConfirm={() => {}} />,
    );
    const rows = screen.getAllByTestId('prefill-row');
    expect(rows).toHaveLength(2);
    expect(screen.getByText('First name')).toBeInTheDocument();
    expect(screen.getByText('Marc')).toBeInTheDocument();
    expect(screen.getAllByText(/From your intake:/)).toHaveLength(2);
  });

  it('distinguishes high vs low confidence mappings', () => {
    render(
      <PrefillConfirmation prefilledFields={prefilled} manualFields={[]} onConfirm={() => {}} />,
    );
    expect(screen.getByText('High confidence')).toBeInTheDocument(); // ai_confidence 1
    expect(screen.getByText('Please verify')).toBeInTheDocument(); // ai_confidence 0.5
  });

  it('lists fields that must be completed manually', () => {
    render(
      <PrefillConfirmation
        prefilledFields={prefilled}
        manualFields={[field({ field_id: 'addr', label: 'Address', value: null, prefill_source: null })]}
        onConfirm={() => {}}
      />,
    );
    expect(screen.getByText('Please complete manually')).toBeInTheDocument();
    expect(screen.getByTestId('manual-row')).toHaveTextContent('Address');
  });

  it('is impossible to skip — only a Confirm action exists', () => {
    render(
      <PrefillConfirmation prefilledFields={prefilled} manualFields={[]} onConfirm={() => {}} />,
    );
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(1);
    expect(buttons[0]).toHaveTextContent('Confirm and continue');
    // No close/dismiss affordance.
    expect(screen.queryByLabelText(/close/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /skip|cancel|later/i })).not.toBeInTheDocument();
  });

  it('fires onConfirm when confirmed', () => {
    const onConfirm = vi.fn();
    render(
      <PrefillConfirmation prefilledFields={prefilled} manualFields={[]} onConfirm={onConfirm} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Confirm and continue' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('disables the button and shows a saving label while confirming', () => {
    render(
      <PrefillConfirmation
        prefilledFields={prefilled}
        manualFields={[]}
        onConfirm={() => {}}
        confirming
      />,
    );
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent('Saving…');
  });
});
