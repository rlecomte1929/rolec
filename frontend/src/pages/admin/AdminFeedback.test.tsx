/**
 * "Feedback & Work" tab — the Inbox is now the only view.
 *
 * AIQ-1565 (BUG-260716-BB94) retired the Work board sub-view and its toggle. These tests
 * pin the new contract: no tabs, Inbox always, and a stale `?view=work` bookmark still
 * lands on the Inbox rather than a blank screen. FeedbackTab is stubbed to keep its API
 * and the supabase client out of jsdom.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

expect.extend(matchers);

vi.mock('../../components/admin/FeedbackTab', () => ({
  FeedbackTab: () => <div data-testid="inbox-view">inbox</div>,
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
  it('renders the Inbox', () => {
    renderAt('/admin/feedback');
    expect(screen.getByTestId('inbox-view')).toBeInTheDocument();
  });

  it('shows no sub-view tabs — the Inbox is the only view', () => {
    renderAt('/admin/feedback');
    expect(screen.queryByRole('tablist')).toBeNull();
    expect(screen.queryByRole('tab')).toBeNull();
    expect(screen.queryByText(/work board/i)).toBeNull();
  });

  it('a stale ?view=work bookmark still lands on the Inbox, not a blank screen', () => {
    renderAt('/admin/feedback?view=work');
    expect(screen.getByTestId('inbox-view')).toBeInTheDocument();
    expect(screen.queryByText(/work board/i)).toBeNull();
  });
});
