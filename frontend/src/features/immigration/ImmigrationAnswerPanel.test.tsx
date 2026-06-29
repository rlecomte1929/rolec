/**
 * [AIQ-856] ImmigrationAnswerPanel — asks the grounded answer endpoint, renders
 * the cited answer, and POSTs a 👍/👎 verdict. API modules mocked (no client/supabase).
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../../api/immigrationAnswer', () => ({ askImmigrationQuestion: vi.fn() }));
vi.mock('../../api/aiFeedback', () => ({ submitAiFeedback: vi.fn() }));

import { askImmigrationQuestion } from '../../api/immigrationAnswer';
import { submitAiFeedback } from '../../api/aiFeedback';
import { ImmigrationAnswerPanel } from './ImmigrationAnswerPanel';

const mockAsk = askImmigrationQuestion as unknown as ReturnType<typeof vi.fn>;
const mockFeedback = submitAiFeedback as unknown as ReturnType<typeof vi.fn>;

afterEach(cleanup);
beforeEach(() => { mockAsk.mockReset(); mockFeedback.mockReset(); });

function fillCorridorAndQuestion() {
  fireEvent.change(screen.getByLabelText('From country'), { target: { value: 'IN' } });
  fireEvent.change(screen.getByLabelText('To country'), { target: { value: 'DE' } });
  fireEvent.change(screen.getByLabelText('Nationality'), { target: { value: 'IN' } });
  fireEvent.change(screen.getByLabelText('Permit type'), { target: { value: 'work' } });
  fireEvent.change(screen.getByLabelText('Your question'), { target: { value: 'What documents?' } });
}

describe('ImmigrationAnswerPanel', () => {
  it('disables Ask until corridor + question are filled', () => {
    render(<ImmigrationAnswerPanel />);
    expect(screen.getByRole('button', { name: /ask/i })).toBeDisabled();
  });

  it('asks the endpoint and renders the cited answer', async () => {
    mockAsk.mockResolvedValue({
      answer_text: 'You need a passport and a contract.',
      answer_kind: 'answer',
      cited_sources: [{ source_url: 'https://make-it-in-germany.com', title: 'Make it in Germany' }],
      confidence: 'high',
      trace_id: 'tr-1',
    });
    render(<ImmigrationAnswerPanel />);
    fillCorridorAndQuestion();
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));
    await waitFor(() => expect(mockAsk).toHaveBeenCalledTimes(1));
    expect(mockAsk.mock.calls[0][0]).toMatchObject({ corridor_from: 'IN', corridor_to: 'DE', nationality: 'IN', permit_type: 'work', query: 'What documents?' });
    await waitFor(() => expect(screen.getByText(/passport and a contract/i)).toBeInTheDocument());
    expect(screen.getByText(/Make it in Germany/)).toBeInTheDocument();
    expect(screen.getByText(/high confidence/i)).toBeInTheDocument();
  });

  it('POSTs an approved verdict on 👍 and shows thanks', async () => {
    mockAsk.mockResolvedValue({ answer_text: 'Ans', answer_kind: 'answer', cited_sources: [], confidence: 'medium', trace_id: 'tr-9' });
    mockFeedback.mockResolvedValue({ verdict: 'approved' });
    render(<ImmigrationAnswerPanel />);
    fillCorridorAndQuestion();
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));
    await waitFor(() => expect(screen.getByTestId('immigration-answer-verdict')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Helpful' }));
    await waitFor(() => expect(mockFeedback).toHaveBeenCalledWith({ trace_session_id: 'tr-9', verdict: 'approved' }));
    await waitFor(() => expect(screen.getByText(/feedback recorded/i)).toBeInTheDocument());
  });

  it('shows the refusal state for an insufficient-context answer', async () => {
    mockAsk.mockResolvedValue({ answer_text: '', answer_kind: 'refusal_insufficient_context', cited_sources: [], trace_id: 'tr-r' });
    render(<ImmigrationAnswerPanel />);
    fillCorridorAndQuestion();
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));
    await waitFor(() => expect(screen.getByText(/enough official, corridor-specific/i)).toBeInTheDocument());
  });
});
