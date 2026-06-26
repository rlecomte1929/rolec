/**
 * ImmigrationChecklistPage — on-brand (E light language) regression.
 *
 * The page was re-skinned from a dark theme to the navy/teal-on-white E
 * language. This renders it populated with a mock immigration case and asserts:
 *   - it renders (permit context + doc statuses as StatusPill labels),
 *   - the content-honesty disclaimer is present,
 *   - NO dark theme tokens remain in the output (regression lock).
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

expect.extend(matchers);
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const mockGet = vi.fn();

vi.mock('../../../api/client', () => ({ default: { get: (...a: unknown[]) => mockGet(...a) } }));
vi.mock('../../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock('../../../components/case/CaseDocumentsPanel', () => ({
  CaseDocumentsPanel: () => <div data-testid="case-documents-panel" />,
}));

import { ImmigrationChecklistPage } from '../ImmigrationChecklistPage';

const CASE_ID = 'case-1';
const MOCK_CASE = {
  id: 'imm-1',
  case_id: CASE_ID,
  corridor_from: 'India',
  corridor_to: 'Germany',
  permit_type: 'eu_blue_card',
  status: 'in_progress',
  document_statuses: { '0': 'verified', '1': 'uploaded', '2': 'not_started' },
};

// Dark tokens that must NOT survive the re-skin.
const DARK_TOKENS = ['1e293b', '0f172a', '1e3a5f', '475569', '14532d', 'f1f5f9', '94a3b8', '3b82f6', '60a5fa'];

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/employee/case/${CASE_ID}/immigration/checklist`]}>
        <Routes>
          <Route path="/employee/case/:caseId/immigration/checklist" element={<ImmigrationChecklistPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ImmigrationChecklistPage on-brand', () => {
  it('renders populated with StatusPill statuses + the content-honesty disclaimer, and no dark tokens', async () => {
    mockGet.mockResolvedValue({ data: MOCK_CASE });
    const { container } = renderPage();

    // Permit context + corridor render
    expect(await screen.findByText(/EU Blue Card/i)).toBeInTheDocument();

    // Doc statuses surfaced as StatusPill labels (verified→Verified, uploaded→Uploaded, not_started→Action needed)
    expect(screen.getByText('Verified')).toBeInTheDocument();
    expect(screen.getByText('Uploaded')).toBeInTheDocument();
    expect(screen.getAllByText('Action needed').length).toBeGreaterThan(0);

    // Content-honesty disclaimer
    expect(screen.getByText(/Indicative/i)).toBeInTheDocument();
    expect(screen.getByText(/immigration authority/i)).toBeInTheDocument();

    // Regression: no dark-theme tokens remain anywhere in the rendered markup
    const html = container.innerHTML;
    for (const tok of DARK_TOKENS) {
      expect(html.includes(tok)).toBe(false);
    }
  });
});
