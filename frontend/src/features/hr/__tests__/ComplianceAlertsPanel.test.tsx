/**
 * BL-Compliance follow-up · Phase B2 — inline "fill compliance fields" form
 * lives at the top of ComplianceAlertsPanel and PATCHes the two HR endpoints
 * that feed the rule engine.
 */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

const listComplianceAlerts = vi.fn();
const evaluateCompliance = vi.fn();
const setEmployerRegNumber = vi.fn();
const setExpectedStartDate = vi.fn();

vi.mock('../../../api/compliance', () => ({
  listComplianceAlerts: (...args: unknown[]) => listComplianceAlerts(...args),
  evaluateCompliance: (...args: unknown[]) => evaluateCompliance(...args),
  resolveComplianceAlert: vi.fn(),
  setEmployerRegNumber: (...args: unknown[]) => setEmployerRegNumber(...args),
  setExpectedStartDate: (...args: unknown[]) => setExpectedStartDate(...args),
}));

import ComplianceAlertsPanel from '../ComplianceAlertsPanel';

beforeEach(() => {
  vi.clearAllMocks();
  listComplianceAlerts.mockResolvedValue({ alerts: [], counts_by_severity: {} });
  evaluateCompliance.mockResolvedValue({
    cases_evaluated: 0,
    alerts_created: 0,
    alerts_skipped_existing: 0,
  });
  setEmployerRegNumber.mockResolvedValue(undefined);
  setExpectedStartDate.mockResolvedValue(undefined);
});

describe('ComplianceAlertsPanel — fill compliance fields form', () => {
  it('renders the case id, employer reg number, and expected start date inputs', async () => {
    render(<ComplianceAlertsPanel />);
    await screen.findByText(/Compliance alerts/i);
    expect(screen.getByLabelText(/case id/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/employer registration/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/expected start date/i)).toBeInTheDocument();
  });

  it('PATCHes only the fields that are filled, then re-runs the evaluator', async () => {
    render(<ComplianceAlertsPanel />);
    await screen.findByText(/Compliance alerts/i);

    fireEvent.change(screen.getByLabelText(/case id/i), {
      target: { value: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' },
    });
    fireEvent.change(screen.getByLabelText(/employer registration/i), {
      target: { value: 'DE-HRB-99' },
    });
    // Leave expected_start_date empty — only employer_reg should be PATCHed.
    fireEvent.click(screen.getByRole('button', { name: /save fields/i }));

    await waitFor(() => {
      expect(setEmployerRegNumber).toHaveBeenCalledWith(
        'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        'DE-HRB-99',
      );
    });
    expect(setExpectedStartDate).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(evaluateCompliance).toHaveBeenCalledTimes(1);
    });
  });

  it('disables submit when no case id is entered', async () => {
    render(<ComplianceAlertsPanel />);
    await screen.findByText(/Compliance alerts/i);
    expect(screen.getByRole('button', { name: /save fields/i })).toBeDisabled();
  });

  it('disables submit when case id is set but no field is filled', async () => {
    render(<ComplianceAlertsPanel />);
    await screen.findByText(/Compliance alerts/i);
    fireEvent.change(screen.getByLabelText(/case id/i), {
      target: { value: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' },
    });
    expect(screen.getByRole('button', { name: /save fields/i })).toBeDisabled();
  });
});
