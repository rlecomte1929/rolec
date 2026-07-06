/**
 * Merged "Feedback & Work" tab — the Inbox | Work board toggle picks the sub-view and
 * ?view=work deep-links straight to the board (so the old /admin/mission-control
 * redirect lands correctly). FeedbackTab + WorkBoard are stubbed to keep their APIs
 * and the supabase client out of jsdom.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

expect.extend(matchers);

vi.mock('../../components/admin/FeedbackTab', () => ({
  FeedbackTab: () => <div data-testid="inbox-view">inbox</div>,
}));
vi.mock('./mission-control/WorkBoard', () => ({
  WorkBoard: () => <div data-testid="work-view">work board</div>,
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
  it('defaults to the Inbox sub-view', () => {
    renderAt('/admin/feedback');
    expect(screen.getByTestId('inbox-view')).toBeInTheDocument();
    expect(screen.queryByTestId('work-view')).toBeNull();
  });

  it('?view=work opens the Work board sub-view', () => {
    renderAt('/admin/feedback?view=work');
    expect(screen.getByTestId('work-view')).toBeInTheDocument();
    expect(screen.queryByTestId('inbox-view')).toBeNull();
  });

  it('the toggle switches between sub-views', () => {
    renderAt('/admin/feedback');
    fireEvent.click(screen.getByRole('tab', { name: 'Work board' }));
    expect(screen.getByTestId('work-view')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: 'Inbox' }));
    expect(screen.getByTestId('inbox-view')).toBeInTheDocument();
  });
});
