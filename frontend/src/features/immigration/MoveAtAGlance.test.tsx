/**
 * MoveAtAGlance (relocation-assistant Slice 2) — proactive risk + checklist panel.
 * Fetches the employee's immigration snapshot and renders risk cards; collapses
 * to nothing when there's no case or the corridor is uncovered.
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, waitFor } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../../api/immigrationSnapshot', () => ({ getImmigrationSnapshot: vi.fn() }));

import { getImmigrationSnapshot } from '../../api/immigrationSnapshot';
import { MoveAtAGlance } from './MoveAtAGlance';

const mock = getImmigrationSnapshot as unknown as ReturnType<typeof vi.fn>;

afterEach(cleanup);
beforeEach(() => mock.mockReset());

describe('MoveAtAGlance', () => {
  it('renders the risk flags + checklist summary when covered', async () => {
    mock.mockResolvedValue({
      covered: true,
      corridor_from: 'IN',
      corridor_to: 'DE',
      visa_type: 'blue_card',
      risk_flags: [
        {
          flag_type: 'PASSPORT_EXPIRY_WITHIN_90_DAYS',
          severity: 'critical',
          title: 'Passport expires soon',
          description: 'Your passport expires within 90 days.',
          recommended_action: 'Renew your passport before applying.',
          deadline: '2026-09-01',
        },
      ],
      checklist_summary: { total: 12, required: 8, conditional: 4 },
    });
    render(<MoveAtAGlance caseId="c1" />);
    await waitFor(() => expect(screen.getByText('Passport expires soon')).toBeInTheDocument());
    expect(screen.getByText(/Renew your passport/)).toBeInTheDocument();
    expect(screen.getByText(/12 requirements/)).toBeInTheDocument();
  });

  it('renders nothing when the corridor is not covered', async () => {
    mock.mockResolvedValue({ covered: false, visa_type: 'blue_card', risk_flags: [], checklist_summary: { total: 0 } });
    const { container } = render(<MoveAtAGlance caseId="c1" />);
    await waitFor(() => expect(mock).toHaveBeenCalled());
    expect(container.textContent).toBe('');
  });

  it('does not fetch and renders nothing without a caseId', () => {
    const { container } = render(<MoveAtAGlance caseId={null} />);
    expect(mock).not.toHaveBeenCalled();
    expect(container.textContent).toBe('');
  });
});
