/**
 * VisaExpiryNudge — [AIQ-1860]
 *
 * Covers the task's Validation Criteria: the card renders for a case nearing
 * visa expiry, shows a confidence badge, has a working CTA, and is HIDDEN when
 * not applicable. The hidden-when-not-applicable cases get the most coverage —
 * a nudge that fires on the wrong case is worse than one that never fires.
 */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  VisaExpiryNudge,
  selectNudgeAlert,
  confidenceForAlert,
  subjectForAlert,
  URGENT_WITHIN_DAYS,
} from '../VisaExpiryNudge';
import {
  listComplianceAlerts,
  resolveComplianceAlert,
  type ComplianceAlert,
} from '../../../api/compliance';

// vi.mock is hoisted above the imports, so the bindings above resolve to these.
vi.mock('../../../api/compliance', () => ({
  listComplianceAlerts: vi.fn(),
  resolveComplianceAlert: vi.fn().mockResolvedValue(undefined),
}));

const mockList = listComplianceAlerts as ReturnType<typeof vi.fn>;
const mockResolve = resolveComplianceAlert as ReturnType<typeof vi.fn>;

const CASE = 'case-1';

function alert(over: Partial<ComplianceAlert> = {}): ComplianceAlert {
  return {
    id: 'a1',
    case_id: CASE,
    status: 'open',
    severity: 'high',
    category: 'immigration',
    description: 'Residence or work permit is approaching its expiry date.',
    detail: { field: 'permit_expiry_date', days_until: 14, threshold: 60 },
    fired_at: '2026-08-01T00:00:00Z',
    employee_id: null,
    host_country: 'IE',
    home_country: 'ES',
    ...over,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockResolve.mockResolvedValue(undefined);
});

describe('confidenceForAlert — provenance of the date, not a model score', () => {
  it('treats the HR-maintained immigration record as HIGH', () => {
    expect(confidenceForAlert(alert({ detail: { field: 'permit_expiry_date' } }))).toBe('HIGH');
  });

  it('treats a self-declared or OCR-extracted profile field as MEDIUM', () => {
    expect(confidenceForAlert(alert({ detail: { field: 'existing_visa_expiry' } }))).toBe('MEDIUM');
    expect(confidenceForAlert(alert({ detail: { field: 'passport_expiry' } }))).toBe('MEDIUM');
  });

  it('falls back to UNKNOWN rather than guessing when the field is absent', () => {
    expect(confidenceForAlert(alert({ detail: {} }))).toBe('UNKNOWN');
    expect(confidenceForAlert(alert({ detail: { field: 42 } }))).toBe('UNKNOWN');
  });
});

describe('subjectForAlert — name the right document', () => {
  it('calls a permit a permit, not a visa', () => {
    expect(subjectForAlert(alert({ detail: { field: 'permit_expiry_date' } }))).toBe('Permit');
  });

  it('distinguishes a visa and a passport', () => {
    expect(subjectForAlert(alert({ detail: { field: 'existing_visa_expiry' } }))).toBe('Visa');
    expect(subjectForAlert(alert({ detail: { field: 'passport_expiry' } }))).toBe('Passport');
  });

  it('hedges rather than guessing when the field is unknown', () => {
    expect(subjectForAlert(alert({ detail: {} }))).toBe('Permit or visa');
  });

  it('does not branch on category, which is always "immigration" for this rule family', () => {
    // Both of these are category='immigration'; the label must still differ,
    // which is exactly what a category-based ternary could not do.
    expect(subjectForAlert(alert({ category: 'immigration', detail: { field: 'permit_expiry_date' } })))
      .not.toBe(subjectForAlert(alert({ category: 'immigration', detail: { field: 'existing_visa_expiry' } })));
  });
});

describe('selectNudgeAlert — the threshold logic', () => {
  it('picks the soonest expiry when several are open', () => {
    const picked = selectNudgeAlert(
      [
        alert({ id: 'far', detail: { field: 'permit_expiry_date', days_until: 50 } }),
        alert({ id: 'near', detail: { field: 'permit_expiry_date', days_until: 3 } }),
      ],
      CASE,
    );
    expect(picked?.id).toBe('near');
  });

  it('ignores alerts belonging to another case', () => {
    expect(selectNudgeAlert([alert({ case_id: 'someone-else' })], CASE)).toBeNull();
  });

  it('ignores alerts that are not about a visa or permit', () => {
    const tax = alert({ category: 'tax', description: 'Employee nearing 183-day tax residency.' });
    expect(selectNudgeAlert([tax], CASE)).toBeNull();
  });

  it('ignores alerts already resolved or dismissed', () => {
    expect(selectNudgeAlert([alert({ status: 'dismissed' })], CASE)).toBeNull();
    expect(selectNudgeAlert([alert({ status: 'resolved' })], CASE)).toBeNull();
  });

  it('ignores an alert with no days_until rather than rendering a blank countdown', () => {
    expect(selectNudgeAlert([alert({ detail: { field: 'permit_expiry_date' } })], CASE)).toBeNull();
  });

  it('ignores an expiry already in the past', () => {
    const past = alert({ detail: { field: 'permit_expiry_date', days_until: -5 } });
    expect(selectNudgeAlert([past], CASE)).toBeNull();
  });
});

describe('VisaExpiryNudge — rendering', () => {
  it('renders nothing when the case has no visa alert', async () => {
    mockList.mockResolvedValue({ alerts: [], counts_by_severity: {} });
    const { container } = render(<VisaExpiryNudge caseId={CASE} onStartRenewal={vi.fn()} />);
    await waitFor(() => expect(mockList).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when the alerts fetch fails, rather than breaking the page', async () => {
    mockList.mockRejectedValue(new Error('boom'));
    const { container } = render(<VisaExpiryNudge caseId={CASE} onStartRenewal={vi.fn()} />);
    await waitFor(() => expect(mockList).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('renders the countdown and a confidence badge for a nearing expiry', async () => {
    mockList.mockResolvedValue({ alerts: [alert()], counts_by_severity: {} });
    render(<VisaExpiryNudge caseId={CASE} onStartRenewal={vi.fn()} />);
    expect(await screen.findByText(/expires in 14 days/i)).toBeInTheDocument();
    // The badge is the shared ConfidenceBadge — assert via its aria-label.
    expect(screen.getByLabelText(/confidence: high/i)).toBeInTheDocument();
  });

  it('says "today" and "in 1 day" rather than "in 0 days"', async () => {
    mockList.mockResolvedValue({
      alerts: [alert({ detail: { field: 'permit_expiry_date', days_until: 0 } })],
      counts_by_severity: {},
    });
    const { unmount } = render(<VisaExpiryNudge caseId={CASE} onStartRenewal={vi.fn()} />);
    expect(await screen.findByText(/expires today/i)).toBeInTheDocument();
    unmount();

    mockList.mockResolvedValue({
      alerts: [alert({ detail: { field: 'permit_expiry_date', days_until: 1 } })],
      counts_by_severity: {},
    });
    render(<VisaExpiryNudge caseId={CASE} onStartRenewal={vi.fn()} />);
    expect(await screen.findByText(/expires in 1 day$/i)).toBeInTheDocument();
  });

  it('mutes an unverifiable date instead of presenting it as urgent', async () => {
    mockList.mockResolvedValue({
      alerts: [alert({ detail: { days_until: 2 } })], // no field -> UNKNOWN
      counts_by_severity: {},
    });
    render(<VisaExpiryNudge caseId={CASE} onStartRenewal={vi.fn()} />);
    const card = await screen.findByTestId('visa-expiry-nudge');
    // Muted wins over the 2-day urgency: no red treatment.
    expect(card.className).toContain('bg-slate-50');
    expect(card.className).not.toContain('bg-red-50');
    expect(screen.getByText(/could not confirm where this expiry date came from/i)).toBeInTheDocument();
  });

  it('reads as urgent inside the urgency window and advisory outside it', async () => {
    mockList.mockResolvedValue({
      alerts: [alert({ detail: { field: 'permit_expiry_date', days_until: URGENT_WITHIN_DAYS } })],
      counts_by_severity: {},
    });
    const { unmount } = render(<VisaExpiryNudge caseId={CASE} onStartRenewal={vi.fn()} />);
    expect((await screen.findByTestId('visa-expiry-nudge')).className).toContain('bg-red-50');
    unmount();

    mockList.mockResolvedValue({
      alerts: [
        alert({ detail: { field: 'permit_expiry_date', days_until: URGENT_WITHIN_DAYS + 1 } }),
      ],
      counts_by_severity: {},
    });
    render(<VisaExpiryNudge caseId={CASE} onStartRenewal={vi.fn()} />);
    expect((await screen.findByTestId('visa-expiry-nudge')).className).toContain('bg-amber-50');
  });

  it('is ambient, not an interruption — role=status, not alert', async () => {
    mockList.mockResolvedValue({ alerts: [alert()], counts_by_severity: {} });
    render(<VisaExpiryNudge caseId={CASE} onStartRenewal={vi.fn()} />);
    const card = await screen.findByTestId('visa-expiry-nudge');
    expect(card).toHaveAttribute('role', 'status');
    expect(card).toHaveAttribute('aria-live', 'polite');
  });
});

describe('VisaExpiryNudge — actions', () => {
  it('fires the CTA', async () => {
    const onStartRenewal = vi.fn();
    mockList.mockResolvedValue({ alerts: [alert()], counts_by_severity: {} });
    render(<VisaExpiryNudge caseId={CASE} onStartRenewal={onStartRenewal} />);
    fireEvent.click(await screen.findByRole('button', { name: /start renewal/i }));
    expect(onStartRenewal).toHaveBeenCalledTimes(1);
  });

  it('dismisses server-side so the dismissal survives a reload', async () => {
    mockList.mockResolvedValue({ alerts: [alert()], counts_by_severity: {} });
    render(<VisaExpiryNudge caseId={CASE} onStartRenewal={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: /dismiss/i }));
    await waitFor(() => expect(mockResolve).toHaveBeenCalledWith('a1', 'dismissed'));
    expect(screen.queryByTestId('visa-expiry-nudge')).not.toBeInTheDocument();
  });

  it('restores the card when the dismiss fails, so it is not silently lost', async () => {
    mockList.mockResolvedValue({ alerts: [alert()], counts_by_severity: {} });
    mockResolve.mockRejectedValue(new Error('network'));
    render(<VisaExpiryNudge caseId={CASE} onStartRenewal={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: /dismiss/i }));
    await waitFor(() => expect(mockResolve).toHaveBeenCalled());
    expect(await screen.findByTestId('visa-expiry-nudge')).toBeInTheDocument();
  });
});
