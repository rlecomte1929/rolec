/**
 * AIQ-1723 — the ?payment=success return path must always terminate, and must never
 * show someone who just paid the buy button again.
 *
 * What the ticket assumed vs what the code does: the entitlement poll was NOT unbounded
 * (`maxAttempts = justPaid ? 6 : 1`, and `fetchRoadmapUnlocked` swallows every rejection),
 * so there is no infinite spinner to remove. The real defect is what happens when the
 * Stripe webhook outlives that ~15s grace: the page fell through to `RoadmapPaywallGate`
 * — a €800 buy CTA — with no acknowledgement of the payment. At the highest-anxiety
 * moment in the funnel that reads as "my money vanished".
 *
 * The gate stays fail-CLOSED throughout: the roadmap is never unlocked by this state, it
 * only tells the truth about why it is still locked.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { EmployeeCaseRoadmapPage } from '../EmployeeCaseRoadmapPage';

// The data sheet is orthogonal to roadmap behaviour and pulls in React Query; stub it so this
// page test needs no QueryClientProvider. DataSheetView has its own coverage in features/datasheet.
vi.mock('../../../features/datasheet/DataSheetView', () => ({ DataSheetView: () => null }));
vi.mock('../../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
// The page imports ExplainTermPopover → api/client → the Supabase singleton, which
// throws at module load with no env. Same stub the sibling integration test uses.
vi.mock('../../../api/supabase', () => ({ supabase: {} }));
vi.mock('../../../api/supabaseAuth', () => ({ signOutSupabase: vi.fn() }));
vi.mock('../../../api/relocationPlanView', () => ({
  fetchRelocationPlanView: vi.fn().mockResolvedValue(null),
}));
vi.mock('../../../api/caseDetails', () => ({
  getCaseDetailsByAssignmentId: vi.fn().mockResolvedValue({ data: null, error: null }),
}));
vi.mock('../../../api/cases', () => ({
  validateRoadmap: vi.fn().mockResolvedValue({ roadmap_validated_at: null }),
}));

// [AIQ-2142] No featureFlags mock — the build flag is gone. Gating is purely server-driven
// (fetchRoadmapUnlocked reads the entitlement served by /api/payment/status), so these tests
// drive that directly and the page always consults it.

// A marker so "did we show the buy CTA?" is unambiguous.
vi.mock('../../../features/employee-journey/RoadmapPaywallGate', () => ({
  RoadmapPaywallGate: () => <div>BUY_CTA_PAYWALL</div>,
}));

const fetchRoadmapUnlocked = vi.fn();
vi.mock('../../../utils/paymentStatus', () => ({
  fetchRoadmapUnlocked: (...a: unknown[]) => fetchRoadmapUnlocked(...a),
}));

const trackPaymentCompleted = vi.fn();
vi.mock('../../../analyticsEvents', () => ({
  trackCaseCompleted: vi.fn(),
  trackCaseRoadmapReviewed: vi.fn(),
  trackPaymentCompleted: (...a: unknown[]) => trackPaymentCompleted(...a),
}));

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/employee/case/case-1/roadmap']}>
      <Routes>
        <Route path="/employee/case/:caseId/roadmap" element={<EmployeeCaseRoadmapPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

/** The page reads window.location.search directly (not useSearchParams). */
function setQuery(search: string) {
  window.history.replaceState(null, '', `/employee/case/case-1/roadmap${search}`);
}

/** Drive the 2.5s poll cadence to exhaustion (6 attempts when just-paid). */
async function drainPoll() {
  for (let i = 0; i < 8; i += 1) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2600);
    });
  }
}

describe('AIQ-1723 · ?payment=success return path', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    fetchRoadmapUnlocked.mockReset();
    trackPaymentCompleted.mockReset();
  });
  afterEach(() => {
    vi.useRealTimers();
    setQuery('');
  });

  it('shows payment-aware copy while confirming, not a generic spinner', async () => {
    setQuery('?payment=success');
    fetchRoadmapUnlocked.mockReturnValue(new Promise(() => {})); // never settles yet
    renderPage();
    await act(async () => {});

    expect(screen.getByText(/confirming your payment/i)).toBeTruthy();
    expect(screen.queryByText(/loading roadmap/i)).toBeNull();
  });

  it('terminates in a "still confirming" state — never the buy CTA — when the webhook lags', async () => {
    setQuery('?payment=success');
    fetchRoadmapUnlocked.mockResolvedValue(false); // entitlement never lands
    renderPage();
    await drainPoll();

    // THE FIX: a just-paid user is not asked to pay again.
    expect(screen.getByText(/still confirming it/i)).toBeTruthy();
    expect(screen.queryByText('BUY_CTA_PAYWALL')).toBeNull();
    // …and it TERMINATED — no spinner left running.
    expect(screen.queryByText(/confirming your payment…/i)).toBeNull();
    // Fail-closed: the roadmap itself is still not rendered.
    expect(screen.queryByText(/what you can do now/i)).toBeNull();
  });

  it('unlocks normally when entitlement lands inside the grace window', async () => {
    setQuery('?payment=success');
    fetchRoadmapUnlocked.mockResolvedValueOnce(false).mockResolvedValue(true);
    renderPage();
    await drainPoll();

    expect(screen.queryByText(/still confirming it/i)).toBeNull();
    expect(screen.queryByText('BUY_CTA_PAYWALL')).toBeNull();
  });

  it('fires payment_completed on ?payment=success without email or name', async () => {
    setQuery('?payment=success');
    fetchRoadmapUnlocked.mockResolvedValue(true);
    renderPage();
    await drainPoll();

    expect(trackPaymentCompleted).toHaveBeenCalledTimes(1);
    const props = trackPaymentCompleted.mock.calls[0][0] as Record<string, unknown>;
    expect(props).toEqual({ assignment_id: 'case-1' });
    expect(JSON.stringify(props)).not.toMatch(/email|@|name/i);
  });

  it('REGRESSION: a normal locked load still shows the buy CTA', async () => {
    setQuery(''); // no payment=success — an ordinary visit to a locked roadmap
    fetchRoadmapUnlocked.mockResolvedValue(false);
    renderPage();
    await drainPoll();

    // The payment-pending state must NOT leak onto users who never paid.
    expect(screen.getByText('BUY_CTA_PAYWALL')).toBeTruthy();
    expect(screen.queryByText(/still confirming it/i)).toBeNull();
    expect(trackPaymentCompleted).not.toHaveBeenCalled();
  });
});
