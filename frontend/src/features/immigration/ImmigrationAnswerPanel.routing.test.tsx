/**
 * Slice 5 (policy bridge) — the unified panel routes each question (via the
 * canonical backend router, mocked here) to the right grounded engine, asking the
 * user when ambiguous. All API modules are mocked.
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../../api/immigrationAnswer', () => ({ askImmigrationQuestion: vi.fn() }));
vi.mock('../../api/policyAssistantQuery', () => ({ getPolicyAnswer: vi.fn() }));
vi.mock('../../api/assistantRoute', () => ({ routeAssistantDomain: vi.fn() }));
vi.mock('../../api/aiFeedback', () => ({ submitAiFeedback: vi.fn() }));
vi.mock('../../api/immigrationAuthority', () => ({ getDestinationImmigrationAuthority: vi.fn().mockResolvedValue(null) }));

import { askImmigrationQuestion } from '../../api/immigrationAnswer';
import { getPolicyAnswer } from '../../api/policyAssistantQuery';
import { routeAssistantDomain } from '../../api/assistantRoute';
import { ImmigrationAnswerPanel } from './ImmigrationAnswerPanel';

const mockImm = askImmigrationQuestion as unknown as ReturnType<typeof vi.fn>;
const mockPol = getPolicyAnswer as unknown as ReturnType<typeof vi.fn>;
const mockRoute = routeAssistantDomain as unknown as ReturnType<typeof vi.fn>;

afterEach(cleanup);
beforeEach(() => { mockImm.mockReset(); mockPol.mockReset(); mockRoute.mockReset(); });

function setQuestion(v: string) {
  fireEvent.change(screen.getByLabelText('Your question'), { target: { value: v } });
}
// AIQ-1476: corridor + nationality pre-fill from the case; provide it via caseContext.
const CASE_CTX = { from: 'IN', to: 'DE', nationalities: ['IN'] } as const;

describe('ImmigrationAnswerPanel — unified routing (policy bridge)', () => {
  it('routes a policy-classified question to the policy engine and renders it', async () => {
    mockRoute.mockResolvedValue('policy');
    mockPol.mockResolvedValue({
      answer_type: 'status_summary', answer_text: 'Housing is covered for 60 days.',
      cited_chunks: [{ id: 'c1', source_type: 'policy_document', source_ref: 'Policy §4.2', chunk_text: 'x' }],
      refusal: null,
    });
    render(<ImmigrationAnswerPanel />);
    setQuestion('Does my company cover temporary housing?');
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    await waitFor(() => expect(mockPol).toHaveBeenCalledWith('Does my company cover temporary housing?'));
    expect(mockImm).not.toHaveBeenCalled();
    expect(await screen.findByTestId('policy-answer')).toBeInTheDocument();
    expect(screen.getByText(/Housing is covered/)).toBeInTheDocument();
  });

  it('routes an immigration-classified question to the immigration engine', async () => {
    mockRoute.mockResolvedValue('immigration');
    mockImm.mockResolvedValue({ answer_text: 'You need a passport.', answer_kind: 'answer', cited_sources: [], trace_id: 't' });
    render(<ImmigrationAnswerPanel caseContext={{ ...CASE_CTX }} />);
    setQuestion('What documents do I need for my visa?');
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    await waitFor(() => expect(mockImm).toHaveBeenCalledTimes(1));
    expect(mockPol).not.toHaveBeenCalled();
    expect(await screen.findByTestId('immigration-answer')).toBeInTheDocument();
  });

  it('asks the user to clarify an ambiguous question, then routes on their choice', async () => {
    mockRoute.mockResolvedValue('ambiguous');
    mockPol.mockResolvedValue({ answer_type: 'status_summary', answer_text: 'Covered.', cited_chunks: [], refusal: null });
    render(<ImmigrationAnswerPanel />);
    setQuestion('Can you help me?');
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    expect(await screen.findByTestId('assistant-clarifier')).toBeInTheDocument();
    expect(mockImm).not.toHaveBeenCalled();
    expect(mockPol).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'About my benefits' }));
    await waitFor(() => expect(mockPol).toHaveBeenCalledWith('Can you help me?'));
  });

  it('falls back to the clarifier when routing fails (no silent misroute)', async () => {
    mockRoute.mockRejectedValue(new Error('network'));
    render(<ImmigrationAnswerPanel />);
    setQuestion('What documents do I need for my visa?');
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    expect(await screen.findByTestId('assistant-clarifier')).toBeInTheDocument();
    expect(mockImm).not.toHaveBeenCalled();
    expect(mockPol).not.toHaveBeenCalled();
  });

  it('blocks an immigration question with no corridor and explains why', async () => {
    mockRoute.mockResolvedValue('immigration');
    render(<ImmigrationAnswerPanel />);
    setQuestion('What documents do I need for my visa?'); // corridor left blank
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    expect(await screen.findByText(/Add your move corridor/)).toBeInTheDocument();
    expect(mockImm).not.toHaveBeenCalled();
  });
});
