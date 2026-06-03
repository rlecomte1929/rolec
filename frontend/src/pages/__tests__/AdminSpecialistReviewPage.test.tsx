import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AdminSpecialistReviewPage } from '../admin/AdminSpecialistReviewPage';

// AdminLayout pulls in AdminViewingCompanyContext, PlatformShellSidebar and
// auth utils that are not available in isolated unit tests. Stub it out so
// only the page content is exercised.
vi.mock('../../pages/admin/AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('../../api/client', () => ({
  specialistReviewAPI: {
    getRoadmap: vi.fn().mockResolvedValue({
      case_id: 'case-1',
      steps: [
        { step_id: 's1', title: 'Step one', confidence: 0.9, source_url: 'https://x' },
        { step_id: 's2', title: 'Step two', confidence: 0.4 },
      ],
    }),
    submit: vi.fn().mockResolvedValue({ released_to_user: true, regeneration_requested: false }),
  },
}));

import { specialistReviewAPI } from '../../api/client';

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/admin/specialist-review/case-1']}>
      <Routes>
        <Route path="/admin/specialist-review/:case_id" element={<AdminSpecialistReviewPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('AdminSpecialistReviewPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('loads and lists all roadmap steps', async () => {
    renderPage();
    await waitFor(() => expect(specialistReviewAPI.getRoadmap).toHaveBeenCalledWith('case-1'));
    expect(await screen.findByText('Step one')).toBeInTheDocument();
    expect(screen.getByText('Step two')).toBeInTheDocument();
  });

  it('submits an overall approval with per-step items', async () => {
    renderPage();
    await screen.findByText('Step one');
    fireEvent.click(screen.getByRole('button', { name: /approve roadmap/i }));
    await waitFor(() => expect(specialistReviewAPI.submit).toHaveBeenCalledTimes(1));
    const [caseId, body] = (specialistReviewAPI.submit as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(caseId).toBe('case-1');
    expect(body.decision).toBe('approved');
    expect(body.items).toHaveLength(2);
  });
});
