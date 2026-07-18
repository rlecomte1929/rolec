/**
 * "Feedback & Work" — Inbox + Product metrics tabs.
 *
 * AIQ-1565 (BUG-260716-BB94) retired the old Work board sub-view. The page later
 * gained two content tabs — Inbox (default) and Product metrics (mirrored PostHog
 * events). These tests pin: Inbox renders by default, both content tabs exist, the
 * Work board stays retired, and a stale `?view=work` bookmark still lands on the
 * Inbox. FeedbackTab and ProductMetricsTab are stubbed to keep their APIs — and the
 * supabase client — out of jsdom.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

expect.extend(matchers);

vi.mock('../../components/admin/FeedbackTab', () => ({
  FeedbackTab: () => <div data-testid="inbox-view">inbox</div>,
}));
vi.mock('../../components/admin/ProductMetricsTab', () => ({
  ProductMetricsTab: () => <div data-testid="metrics-view">metrics</div>,
}));
vi.mock('./AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import AdminFeedback from './AdminFeedback';

afterEach(cleanup);

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AdminFeedback />
    </MemoryRouter>,
  );
}

describe('AdminFeedback (Feedback & Work)', () => {
  it('renders the Inbox by default', () => {
    renderAt('/admin/feedback');
    expect(screen.getByTestId('inbox-view')).toBeInTheDocument();
    // Product metrics tab exists but its panel is not the default view.
    expect(screen.queryByTestId('metrics-view')).toBeNull();
  });

  it('exposes Inbox + Product metrics tabs; the Work board stays retired', () => {
    renderAt('/admin/feedback');
    expect(screen.getByRole('tablist')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /inbox/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /product metrics/i })).toBeInTheDocument();
    expect(screen.queryByText(/work board/i)).toBeNull();
  });

  it('a stale ?view=work bookmark still lands on the Inbox, not a blank screen', () => {
    renderAt('/admin/feedback?view=work');
    expect(screen.getByTestId('inbox-view')).toBeInTheDocument();
    expect(screen.queryByText(/work board/i)).toBeNull();
  });
});
