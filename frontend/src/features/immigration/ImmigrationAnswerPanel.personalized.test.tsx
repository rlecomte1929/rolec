/**
 * Relocation-assistant MVP — the panel pre-fills the corridor from the employee's
 * case (caseContext) so they never hand-type From/To. Proves the wiring: case
 * context → personalized banner → the case-derived corridor in the request.
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../../api/immigrationAnswer', () => ({ askImmigrationQuestion: vi.fn() }));
vi.mock('../../api/policyAssistantQuery', () => ({ getPolicyAnswer: vi.fn() }));
vi.mock('../../api/assistantRoute', () => ({ routeAssistantDomain: vi.fn(() => Promise.resolve('immigration')) }));
vi.mock('../../api/aiFeedback', () => ({ submitAiFeedback: vi.fn() }));

import { askImmigrationQuestion } from '../../api/immigrationAnswer';
import { ImmigrationAnswerPanel } from './ImmigrationAnswerPanel';

const mockAsk = askImmigrationQuestion as unknown as ReturnType<typeof vi.fn>;

afterEach(cleanup);
beforeEach(() => mockAsk.mockReset());

describe('ImmigrationAnswerPanel — personalized corridor (MVP)', () => {
  it('shows the personalized banner and hides the From/To form when given a case', () => {
    render(<ImmigrationAnswerPanel caseContext={{ from: 'IN', to: 'DE', label: 'IN → DE' }} />);
    expect(screen.getByText(/your IN → DE move/i)).toBeInTheDocument();
    expect(screen.queryByLabelText('From country')).toBeNull();
    expect(screen.queryByLabelText('To country')).toBeNull();
  });

  it('"Edit corridor" reveals the manual form to override', () => {
    render(<ImmigrationAnswerPanel caseContext={{ from: 'IN', to: 'DE' }} />);
    fireEvent.click(screen.getByRole('button', { name: /different corridor/i }));
    expect(screen.getByLabelText('From country')).toBeInTheDocument();
    expect(screen.getByLabelText('To country')).toBeInTheDocument();
  });

  it('falls back to the manual form when there is no case', () => {
    render(<ImmigrationAnswerPanel />);
    expect(screen.getByLabelText('From country')).toBeInTheDocument();
  });

  it('sends the case-derived corridor in the request (no hand-typing)', async () => {
    mockAsk.mockResolvedValue({ answer_text: 'ok', answer_kind: 'answer', cited_sources: [], trace_id: 't1' });
    render(<ImmigrationAnswerPanel caseContext={{ from: 'IN', to: 'DE' }} />);
    // corridor is pre-filled from the case; the user only confirms nationality + permit + asks.
    fireEvent.change(screen.getByLabelText('Nationality'), { target: { value: 'IN' } });
    fireEvent.change(screen.getByLabelText('Permit type'), { target: { value: 'Blue Card' } });
    fireEvent.change(screen.getByLabelText('Your question'), { target: { value: 'What documents do I need?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    await waitFor(() => expect(mockAsk).toHaveBeenCalledTimes(1));
    expect(mockAsk.mock.calls[0][0]).toMatchObject({
      corridor_from: 'IN',
      corridor_to: 'DE',
      nationality: 'IN',
      permit_type: 'Blue Card',
      query: 'What documents do I need?',
    });
  });
});
