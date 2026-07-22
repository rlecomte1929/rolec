/**
 * ServicesRfqNew — "Send quotation requests".
 *
 * [AIQ-1523] This now creates a REAL RFQ (`POST /api/rfqs` -> rfqs + one rfq_recipients row
 * per supplier) instead of a `quote_requests` row. quote_requests was a dead end: no supplier
 * could ever answer it, and the HR payer view reads rfqs/quotes — which nothing wrote to.
 *
 * The two shapes matter and are asserted below:
 *   items         = one per unique SERVICE  (3 movers is ONE item, "movers")
 *   supplier_ids  = one per unique SUPPLIER (3 movers is THREE recipients)
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

expect.extend(matchers);
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const mockCreateRfq = vi.fn();

vi.mock('../../../api/client', () => ({
  servicesAPI: {
    createRfq: (...a: unknown[]): unknown => mockCreateRfq(...a),
  },
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
  caseIdForAssignment: (_rows: unknown, id: string | null) => id,
}));
vi.mock('../../../features/services/ServicesFlowContext', () => ({
  useServicesFlow: () => ({
    recommendations: {
      living_areas: { recommendations: [{ item_id: 'v1', name: 'Acme Housing' }] },
      // TWO movers shortlisted — the case that proves items vs recipients are deduped
      // differently. Getting this wrong sends ["movers","movers"] as two RFQ items.
      movers: {
        recommendations: [
          { item_id: 'v2', name: 'Move It' },
          { item_id: 'v3', name: 'Haul Co' },
        ],
      },
    },
    shortlist: new Map([['living_areas', ['v1']], ['movers', ['v2', 'v3']]]),
  }),
}));

import { ServicesRfqNew } from '../ServicesRfqNew';

describe('ServicesRfqNew send', () => {
  beforeEach(() => {
    mockCreateRfq.mockReset();
    mockCreateRfq.mockResolvedValue({ ok: true, rfq: { id: 'rfq-1', rfq_ref: 'RFQ-1' }, unreachable: [] });
  });

  it('creates a REAL rfq — one item per service, one recipient per supplier', async () => {
    render(<MemoryRouter><ServicesRfqNew /></MemoryRouter>);

    fireEvent.click(await screen.findByRole('button', { name: /send quotation requests/i }));
    await waitFor(() => expect(mockCreateRfq).toHaveBeenCalledTimes(1));

    const [caseId, items, supplierIds] = mockCreateRfq.mock.calls[0] as [
      string,
      Array<{ service_key: string; requirements: Record<string, unknown> }>,
      string[],
    ];
    expect(caseId).toBe('case-1');
    // two movers collapse into ONE "movers" item...
    expect(items.map((i) => i.service_key)).toEqual(['living_areas', 'movers']);
    // ...but stay THREE separate recipients.
    expect(supplierIds).toEqual(['v1', 'v2', 'v3']);

    expect(await screen.findByTestId('rfq-sent')).toBeInTheDocument();
  });

  it('tells the employee when a supplier they picked could not be reached', async () => {
    // The RFQ still goes to the rest — but we must not silently send to fewer suppliers
    // than the employee chose.
    mockCreateRfq.mockResolvedValue({
      ok: true,
      rfq: { id: 'rfq-1', rfq_ref: 'RFQ-1' },
      unreachable: ['Haul Co: no supplier on record'],
    });
    render(<MemoryRouter><ServicesRfqNew /></MemoryRouter>);

    fireEvent.click(await screen.findByRole('button', { name: /send quotation requests/i }));

    const warn = await screen.findByTestId('rfq-unreachable');
    expect(warn).toHaveTextContent(/Haul Co/);
    // [AIQ-1521] Was "couldn't include every vendor". The request now goes to the providers
    // themselves, so the word that matters is REACH.
    expect(warn).toHaveTextContent(/couldn’t reach every provider/i);
  });

  // ───────────────────────────────────────────────────────────────────────────
  // [AIQ-1521] The banner must state what ACTUALLY happened. Claiming "sent to the providers"
  // when nobody was emailed is the same lie AIQ-1515 removed — and so is claiming HR will do it
  // when the suppliers already have the request in their inbox. Both directions are tested.
  // ───────────────────────────────────────────────────────────────────────────

  it('says the providers were contacted — only when they actually were', async () => {
    mockCreateRfq.mockResolvedValue({
      ok: true,
      rfq: { id: 'rfq-1', rfq_ref: 'RFQ-1' },
      unreachable: [],
      contacted: ['Santa Fe Relocation', 'Transworld Relocation'],
      not_contacted: [],
    });
    render(<MemoryRouter><ServicesRfqNew /></MemoryRouter>);

    fireEvent.click(await screen.findByRole('button', { name: /send quotation requests/i }));

    const sent = await screen.findByTestId('rfq-sent');
    expect(sent).toHaveTextContent(/Sent to 2 providers/i);
    expect(sent).toHaveTextContent(/Santa Fe Relocation/);
    // HR is still the payer who validates — that must survive the rewrite.
    expect(sent).toHaveTextContent(/HR team validates/i);
  });

  it('does NOT claim the providers were contacted when dispatch is off', async () => {
    // `contacted: []` means nobody outside ReloPass has seen this request. [AIQ-1668] the
    // honest copy here states only what is true — recorded + on the roadmap — and must NOT
    // claim HR can see the picks or will follow up (no HR surface reads the employee `rfqs`
    // table), nor that any supplier was contacted.
    mockCreateRfq.mockResolvedValue({
      ok: true,
      rfq: { id: 'rfq-1', rfq_ref: 'RFQ-1' },
      unreachable: [],
      contacted: [],
      not_contacted: [],
    });
    render(<MemoryRouter><ServicesRfqNew /></MemoryRouter>);

    fireEvent.click(await screen.findByRole('button', { name: /send quotation requests/i }));

    const sent = await screen.findByTestId('rfq-sent');
    expect(sent).toHaveTextContent(/Request recorded/i);
    expect(sent).toHaveTextContent(/added it to your roadmap/i);
    // The false claims must be gone (AIQ-1668): HR visibility, HR follow-up, supplier contact.
    expect(sent).not.toHaveTextContent(/your HR team can see the providers/i);
    expect(sent).not.toHaveTextContent(/will follow up/i);
    expect(sent).not.toHaveTextContent(/Sent to \d+ provider/i);
  });

  it('names the supplier we hold no address for, instead of dropping them silently', async () => {
    mockCreateRfq.mockResolvedValue({
      ok: true,
      rfq: { id: 'rfq-1', rfq_ref: 'RFQ-1' },
      unreachable: [],
      contacted: ['Move It'],
      not_contacted: [{ supplier: 'Haul Co', reason: 'no contact email on record' }],
    });
    render(<MemoryRouter><ServicesRfqNew /></MemoryRouter>);

    fireEvent.click(await screen.findByRole('button', { name: /send quotation requests/i }));

    const warn = await screen.findByTestId('rfq-unreachable');
    expect(warn).toHaveTextContent(/Haul Co/);
    expect(warn).toHaveTextContent(/no contact email on record/i);
    // ...and the one we DID reach is still reported as reached.
    expect(await screen.findByTestId('rfq-sent')).toHaveTextContent(/Sent to 1 provider/i);
  });
});
