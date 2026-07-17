/**
 * The modal must file EXACTLY what the caller declares.
 *
 * It used to decide two things for itself, and got both wrong for any caller not working in
 * USD: it hardcoded `currency: 'USD'`, and it inferred `exception_type` from `cap === 0`.
 * BenefitComparisonDashboard passes the policy's native numbers, so a 25,000 NOK cap reached
 * HR as $25,000 — ~10x, in the one field HR decides on. Nothing threw; the UI looked right.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import React from 'react';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../../../api/exceptions', () => ({ createExceptionRequest: vi.fn() }));

import { createExceptionRequest } from '../../../api/exceptions';
import { RequestExceptionModal } from '../RequestExceptionModal';

const mockCreate = createExceptionRequest as unknown as ReturnType<typeof vi.fn>;

function renderModal(overrides: Record<string, unknown> = {}) {
  const props = {
    open: true,
    onClose: vi.fn(),
    onSuccess: vi.fn(),
    caseId: 'case-1',
    category: 'housing',
    categoryLabel: 'Housing',
    requestedAmount: 32000,
    capAmount: 25000,
    currency: 'NOK',
    exceptionType: 'cap_override' as const,
    displayRequested: 'kr 32,000',
    displayCap: 'kr 25,000',
    ...overrides,
  };
  render(<RequestExceptionModal {...(props as never)} />);
  return props;
}

async function submitWithReason(reason = 'Central Oslo, family of 4.') {
  const box = screen.getByRole('textbox');
  fireEvent.change(box, { target: { value: reason } });
  const submit = screen.getByRole('button', { name: /send|request|submit/i });
  fireEvent.click(submit);
  await waitFor(() => expect(mockCreate).toHaveBeenCalled());
  return mockCreate.mock.calls[0][1];
}

describe('RequestExceptionModal — files what the caller declares', () => {
  beforeEach(() => {
    mockCreate.mockReset();
    mockCreate.mockResolvedValue({ id: 'r1', category: 'housing', status: 'pending' });
  });
  afterEach(cleanup);

  it('sends the caller currency, not a hardcoded USD', async () => {
    renderModal();
    const body = await submitWithReason();

    expect(body.currency).toBe('NOK');
    // The amount must travel with its own unit — unconverted.
    expect(body.requested_amount).toBe(32000);
    expect(body.cap_amount).toBe(25000);
  });

  it('sends the declared exception_type instead of inferring it from cap === 0', async () => {
    // A cap of 0 used to force 'new_category'. Here the caller knows the benefit exists and
    // is capped-and-exceeded; a 0 cap would be missing data, not a new-benefit request.
    renderModal({ capAmount: 0, exceptionType: 'cap_override' });
    const body = await submitWithReason();

    expect(body.exception_type).toBe('cap_override');
  });

  it('honours a new_category declaration', async () => {
    renderModal({ exceptionType: 'new_category', capAmount: 0, requestedAmount: 0 });
    const body = await submitWithReason();

    expect(body.exception_type).toBe('new_category');
  });

  it('files the category verbatim, so the caller can canonicalise it', async () => {
    renderModal({ category: 'housing' });
    const body = await submitWithReason();

    expect(body.category).toBe('housing');
  });
});
