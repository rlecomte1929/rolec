/**
 * Slice 5 (policy bridge) — the unified panel routes each question to the right
 * grounded engine, asking the user when ambiguous. Both API modules are mocked.
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../../api/immigrationAnswer', () => ({ askImmigrationQuestion: vi.fn() }));
vi.mock('../../api/policyAssistantQuery', () => ({ getPolicyAnswer: vi.fn() }));
vi.mock('../../api/aiFeedback', () => ({ submitAiFeedback: vi.fn() }));

import { askImmigrationQuestion } from '../../api/immigrationAnswer';
import { getPolicyAnswer } from '../../api/policyAssistantQuery';
import { ImmigrationAnswerPanel } from './ImmigrationAnswerPanel';

const mockImm = askImmigrationQuestion as unknown as ReturnType<typeof vi.fn>;
const mockPol = getPolicyAnswer as unknown as ReturnType<typeof vi.fn>;

afterEach(cleanup);
beforeEach(() => { mockImm.mockReset(); mockPol.mockReset(); });

function setQuestion(v: string) {
  fireEvent.change(screen.getByLabelText('Your question'), { target: { value: v } });
}
function fillCorridor() {
  fireEvent.change(screen.getByLabelText('From country'), { target: { value: 'IN' } });
  fireEvent.change(screen.getByLabelText('To country'), { target: { value: 'DE' } });
  fireEvent.change(screen.getByLabelText('Nationality'), { target: { value: 'IN' } });
  fireEvent.change(screen.getByLabelText('Permit type'), { target: { value: 'blue_card' } });
}

describe('ImmigrationAnswerPanel — unified routing (policy bridge)', () => {
  it('routes a benefits question to the policy engine and renders it', async () => {
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

  it('routes an immigration question to the immigration engine', async () => {
    mockImm.mockResolvedValue({ answer_text: 'You need a passport.', answer_kind: 'answer', cited_sources: [], trace_id: 't' });
    render(<ImmigrationAnswerPanel />);
    fillCorridor();
    setQuestion('What documents do I need for my visa?');
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    await waitFor(() => expect(mockImm).toHaveBeenCalledTimes(1));
    expect(mockPol).not.toHaveBeenCalled();
    expect(await screen.findByTestId('immigration-answer')).toBeInTheDocument();
  });

  it('asks the user to clarify an ambiguous question, then routes on their choice', async () => {
    mockPol.mockResolvedValue({ answer_type: 'status_summary', answer_text: 'Covered.', cited_chunks: [], refusal: null });
    render(<ImmigrationAnswerPanel />);
    setQuestion('Can you help me?');
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    expect(screen.getByTestId('assistant-clarifier')).toBeInTheDocument();
    expect(mockImm).not.toHaveBeenCalled();
    expect(mockPol).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'About my benefits' }));
    await waitFor(() => expect(mockPol).toHaveBeenCalledWith('Can you help me?'));
  });

  it('blocks an immigration question with no corridor and explains why', () => {
    render(<ImmigrationAnswerPanel />);
    setQuestion('What documents do I need for my visa?'); // corridor left blank
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    expect(screen.getByText(/Add your corridor/)).toBeInTheDocument();
    expect(mockImm).not.toHaveBeenCalled();
  });
});
