/**
 * [AIQ-686] OutcomeSharingOptIn.test.tsx
 *
 * The optional outcome-sharing opt-in: hydrates from GET, POSTs on toggle, and
 * reverts on a failed write. API module is mocked (avoids importing api/client →
 * api/supabase, the jsdom "supabaseUrl is required" trap).
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../../../api/outcomeConsent', () => ({
  getOutcomeConsent: vi.fn(),
  setOutcomeConsent: vi.fn(),
}));

import { getOutcomeConsent, setOutcomeConsent } from '../../../api/outcomeConsent';
import { OutcomeSharingOptIn } from './OutcomeSharingOptIn';

const mockGet = getOutcomeConsent as unknown as ReturnType<typeof vi.fn>;
const mockSet = setOutcomeConsent as unknown as ReturnType<typeof vi.fn>;

afterEach(cleanup);
beforeEach(() => {
  mockGet.mockReset();
  mockSet.mockReset();
});

describe('OutcomeSharingOptIn', () => {
  it('renders an unchecked, optional opt-in by default', async () => {
    mockGet.mockResolvedValue({ consented: null });
    render(<OutcomeSharingOptIn caseId="case-1" />);
    const box = screen.getByTestId('outcome-consent-optin').querySelector('input')!;
    await waitFor(() => expect(mockGet).toHaveBeenCalledWith('case-1'));
    expect(box).not.toBeChecked();
    expect(screen.getByText(/optional/i)).toBeInTheDocument();
  });

  it('hydrates the checked state from the GET', async () => {
    mockGet.mockResolvedValue({ consented: true });
    render(<OutcomeSharingOptIn caseId="case-9" />);
    const box = screen.getByTestId('outcome-consent-optin').querySelector('input')!;
    await waitFor(() => expect(box).toBeChecked());
  });

  it('POSTs the consent on toggle', async () => {
    mockGet.mockResolvedValue({ consented: null });
    mockSet.mockResolvedValue({ consented: true, consent_version: 'v1' });
    render(<OutcomeSharingOptIn caseId="case-1" />);
    const box = screen.getByTestId('outcome-consent-optin').querySelector('input')!;
    fireEvent.click(box);
    await waitFor(() => expect(mockSet).toHaveBeenCalledWith('case-1', true));
    expect(box).toBeChecked();
  });

  it('reverts the box if the write fails', async () => {
    mockGet.mockResolvedValue({ consented: null });
    mockSet.mockRejectedValue(new Error('boom'));
    render(<OutcomeSharingOptIn caseId="case-1" />);
    const box = screen.getByTestId('outcome-consent-optin').querySelector('input')!;
    fireEvent.click(box);
    await waitFor(() => expect(screen.getByText(/couldn’t save/i)).toBeInTheDocument());
    expect(box).not.toBeChecked();
  });
});
