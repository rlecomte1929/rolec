/**
 * ServicesRfqNew — wired "Send quotation requests" button.
 * Clicking Send posts a quote request (case_id + shortlisted service keys) and
 * shows the sent confirmation.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

expect.extend(matchers);
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const mockCreate = vi.fn();

vi.mock('../../../api/client', () => ({
  employeeAPI: { createQuoteRequest: (...a: unknown[]): unknown => mockCreate(...a) },
}));
vi.mock('../../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock('../../../features/services/ServicesNavRibbon', () => ({ ServicesNavRibbon: () => null }));
vi.mock('../../../features/services/RfqWorkflowDiagram', () => ({ RfqWorkflowDiagram: () => null }));
vi.mock('../../../components/employee/EmployeeScopedAssignmentPicker', () => ({
  EmployeeScopedAssignmentPicker: () => null,
}));
vi.mock('../../../contexts/EmployeeAssignmentContext', () => ({
  useEmployeeAssignment: () => ({ assignmentId: 'case-1', linkedSummaries: [], isLoading: false }),
}));
vi.mock('../../../utils/employeeAssignmentScope', () => ({
  parseAssignmentSearchParam: () => null,
  resolveScopedAssignmentId: () => ({ effectiveId: 'case-1', needsPicker: false }),
  withAssignmentQuery: (p: string) => p,
  // AIQ-1334: ServicesRfqNew now resolves a case_id for in-flow nav targets.
  caseIdForAssignment: (_rows: unknown, id: string | null) => id,
}));
vi.mock('../../../features/services/ServicesFlowContext', () => ({
  useServicesFlow: () => ({
    recommendations: {
      living_areas: { recommendations: [{ item_id: 'v1', name: 'Acme Housing' }] },
      movers: { recommendations: [{ item_id: 'v2', name: 'Move It' }] },
    },
    // [AIQ-1520] shortlist is now category -> MANY item_ids.
    shortlist: new Map([['living_areas', ['v1']], ['movers', ['v2']]]),
  }),
}));

import { ServicesRfqNew } from '../ServicesRfqNew';

describe('ServicesRfqNew send', () => {
  beforeEach(() => { mockCreate.mockReset(); mockCreate.mockResolvedValue({ id: 'q1', status: 'pending' }); });

  it('posts a quote request with the shortlisted service keys and confirms', async () => {
    render(<MemoryRouter><ServicesRfqNew /></MemoryRouter>);

    const btn = await screen.findByRole('button', { name: /send quotation requests/i });
    fireEvent.click(btn);

    await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1));
    const payload = mockCreate.mock.calls[0][0] as { case_id: string; service_categories: string[] };
    expect(payload.case_id).toBe('case-1');
    expect(payload.service_categories).toEqual(['living_areas', 'movers']);

    expect(await screen.findByTestId('rfq-sent')).toBeInTheDocument();
  });
});
