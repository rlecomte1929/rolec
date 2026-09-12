import '@testing-library/jest-dom/vitest';
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { hrAPI } from '../../../api/client';
import type { CaseHealthFlag, CommandCenterCaseRow } from '../../../api/client';
import {
  attentionOpenCaseAriaLabel,
  HrCaseHealthPanel,
  matchAttentionCase,
} from '../HrCaseHealthPanel';

vi.mock('../../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../../api/client')>('../../../api/client');
  return {
    ...actual,
    hrAPI: {
      ...actual.hrAPI,
      getCaseHealth: vi.fn(),
    },
  };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const FLAG: CaseHealthFlag = {
  case_id: 'rel-1',
  stage: 'housing',
  milestone_title: 'Confirm housing',
  owner: 'hr',
  days_behind: 4,
  expected_date: '2026-09-01',
  severity: 'warning',
  suggested_action: 'Chase the housing vendor.',
  draft_reminder: null,
};

const ROW: CommandCenterCaseRow = {
  id: 'asg-1',
  caseId: 'rel-1',
  employeeIdentifier: 'jane@acme.com',
  destCountry: 'ES',
  originCountry: 'IE',
  status: 'awaiting_intake',
  riskStatus: 'yellow',
  tasksDonePercent: 10,
};

function renderPanel(catalog: CommandCenterCaseRow[] = [ROW]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <HrCaseHealthPanel catalog={catalog} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('HrCaseHealthPanel', () => {
  it('matches health flags to command-center rows by case id', () => {
    expect(matchAttentionCase(FLAG, [ROW])?.employeeIdentifier).toBe('jane@acme.com');
  });

  it('names the employee on the open-case control', () => {
    expect(attentionOpenCaseAriaLabel('Jane Doe', 'Spain')).toBe('Open case for Jane Doe (Spain)');
  });

  it('shows employee identity and a named open-case link (AIQ-2342)', async () => {
    vi.mocked(hrAPI.getCaseHealth).mockResolvedValue({ cases: [FLAG] });
    renderPanel();

    await waitFor(() => expect(screen.getByText('jane@acme.com')).toBeInTheDocument());
    const link = screen.getByRole('link', { name: 'Open case for jane@acme.com (Spain)' });
    expect(link).toHaveAttribute('href', '/hr/command-center/cases/asg-1');
    expect(link.className).toMatch(/min-h-6/);
  });
});
