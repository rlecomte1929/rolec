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
// The unified panel (Slice 5) imports the policy-query + routing modules → api/client
// → supabase. Mock them so this immigration-only suite stays out of jsdom's supabase
// client, and route every question to the immigration engine.
vi.mock('../../api/policyAssistantQuery', () => ({ getPolicyAnswer: vi.fn() }));
vi.mock('../../api/assistantRoute', () => ({ routeAssistantDomain: vi.fn().mockResolvedValue('immigration') }));
vi.mock('../../api/immigrationAuthority', () => ({ getDestinationImmigrationAuthority: vi.fn().mockResolvedValue(null) }));

import { askImmigrationQuestion } from '../../api/immigrationAnswer';
import { submitAiFeedback } from '../../api/aiFeedback';
import { getDestinationImmigrationAuthority } from '../../api/immigrationAuthority';
import { ImmigrationAnswerPanel } from './ImmigrationAnswerPanel';

const mockAsk = askImmigrationQuestion as unknown as ReturnType<typeof vi.fn>;
const mockFeedback = submitAiFeedback as unknown as ReturnType<typeof vi.fn>;
const mockAuthority = getDestinationImmigrationAuthority as unknown as ReturnType<typeof vi.fn>;

afterEach(cleanup);
beforeEach(() => {
  mockAsk.mockReset();
  mockFeedback.mockReset();
  mockAuthority.mockReset();
  mockAuthority.mockResolvedValue(null);
});

// AIQ-1476: corridor + nationality now pre-fill from the case (nationality is a
// multi-value chip select, permit type is optional). Provide caseContext so the ask
// gate is satisfied the way it is in production, then just type the question.
const CASE_CTX = { from: 'IN', to: 'DE', nationalities: ['IN'] } as const;
function fillQuestion(q = 'What documents?') {
  fireEvent.change(screen.getByLabelText('Your question'), { target: { value: q } });
}

describe('ImmigrationAnswerPanel', () => {
  it('disables Ask until a question is entered', () => {
    render(<ImmigrationAnswerPanel caseContext={{ ...CASE_CTX }} />);
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
    render(<ImmigrationAnswerPanel caseContext={{ ...CASE_CTX }} />);
    fillQuestion();
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));
    await waitFor(() => expect(mockAsk).toHaveBeenCalledTimes(1));
    expect(mockAsk.mock.calls[0][0]).toMatchObject({ corridor_from: 'IN', corridor_to: 'DE', nationality: 'IN', query: 'What documents?' });
    await waitFor(() => expect(screen.getByText(/passport and a contract/i)).toBeInTheDocument());
    expect(screen.getByText(/Make it in Germany/)).toBeInTheDocument();
    expect(screen.getByText(/high confidence/i)).toBeInTheDocument();
  });

  it('POSTs an approved verdict on 👍 and shows thanks', async () => {
    mockAsk.mockResolvedValue({ answer_text: 'Ans', answer_kind: 'answer', cited_sources: [], confidence: 'medium', trace_id: 'tr-9' });
    mockFeedback.mockResolvedValue({ verdict: 'approved' });
    render(<ImmigrationAnswerPanel caseContext={{ ...CASE_CTX }} />);
    fillQuestion();
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));
    await waitFor(() => expect(screen.getByTestId('immigration-answer-verdict')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Helpful' }));
    await waitFor(() => expect(mockFeedback).toHaveBeenCalledWith({ trace_session_id: 'tr-9', verdict: 'approved' }));
    await waitFor(() => expect(screen.getByText(/feedback recorded/i)).toBeInTheDocument());
  });

  it('shows the refusal state for an insufficient-context answer', async () => {
    mockAsk.mockResolvedValue({ answer_text: '', answer_kind: 'refusal_insufficient_context', cited_sources: [], trace_id: 'tr-r' });
    render(<ImmigrationAnswerPanel caseContext={{ ...CASE_CTX }} />);
    fillQuestion();
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));
    await waitFor(() => expect(screen.getByText(/enough official, corridor-specific/i)).toBeInTheDocument());
  });

  it('renders the answer as markdown — headings, bold, GFM tables — not raw source (AIQ-1869)', async () => {
    mockAsk.mockResolvedValue({
      answer_text: [
        '## Work Permit Requirements',
        '',
        'You need a **Blue Card**.',
        '',
        '| Step | Action |',
        '| --- | --- |',
        '| 1 | Apply online |',
      ].join('\n'),
      answer_kind: 'answer',
      cited_sources: [],
      confidence: 'high',
      trace_id: 'tr-md',
    });
    render(<ImmigrationAnswerPanel caseContext={{ ...CASE_CTX }} />);
    fillQuestion();
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    // Heading is a real element, not a literal "##".
    const heading = await screen.findByText('Work Permit Requirements');
    expect(heading.tagName).toMatch(/^H[1-6]$/);
    expect(screen.queryByText(/## Work Permit/)).toBeNull();

    // Bold renders as <strong>, not literal "**".
    expect(screen.getByText('Blue Card').tagName).toBe('STRONG');

    // GFM table renders, not literal pipes.
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('Apply online')).toBeInTheDocument();
    expect(screen.queryByText(/\| Step \|/)).toBeNull();
  });

  it('shows a standing authority link before any question when curated data exists', async () => {
    mockAuthority.mockResolvedValue({ name: 'Ausländerbehörde', url: 'https://www.bamf.de' });
    render(<ImmigrationAnswerPanel caseContext={{ ...CASE_CTX }} />);
    const link = await screen.findByTestId('destination-authority-link');
    expect(link).toHaveAttribute('href', 'https://www.bamf.de');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(link).toHaveTextContent(/Official immigration site: Ausländerbehörde/);
  });

  it('renders no standing authority link when none is curated', async () => {
    mockAuthority.mockResolvedValue(null);
    render(<ImmigrationAnswerPanel caseContext={{ ...CASE_CTX }} />);
    await waitFor(() => expect(mockAuthority).toHaveBeenCalledWith('DE'));
    expect(screen.queryByTestId('destination-authority-link')).toBeNull();
  });
});
