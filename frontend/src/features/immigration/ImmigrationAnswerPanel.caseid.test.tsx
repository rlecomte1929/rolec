/**
 * Slice 3 — when the panel has a caseId, it includes case_id in the /answer
 * request so the backend can tailor the answer to the applicant's context.
 * Omitted when there's no case.
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

function fill() {
  fireEvent.change(screen.getByLabelText('From country'), { target: { value: 'IN' } });
  fireEvent.change(screen.getByLabelText('To country'), { target: { value: 'DE' } });
  fireEvent.change(screen.getByLabelText('Nationality'), { target: { value: 'IN' } });
  fireEvent.change(screen.getByLabelText('Permit type'), { target: { value: 'blue_card' } });
  fireEvent.change(screen.getByLabelText('Your question'), { target: { value: 'What do I need?' } });
}

describe('ImmigrationAnswerPanel — case_id passthrough', () => {
  it('includes case_id when a caseId is provided', async () => {
    mockAsk.mockResolvedValue({ answer_text: 'ok', answer_kind: 'answer', cited_sources: [], trace_id: 't' });
    render(<ImmigrationAnswerPanel caseId="case-123" />);
    fill();
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    await waitFor(() => expect(mockAsk).toHaveBeenCalledTimes(1));
    expect(mockAsk.mock.calls[0][0]).toMatchObject({ case_id: 'case-123' });
  });

  it('omits case_id when there is no case', async () => {
    mockAsk.mockResolvedValue({ answer_text: 'ok', answer_kind: 'answer', cited_sources: [], trace_id: 't' });
    render(<ImmigrationAnswerPanel />);
    fill();
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    await waitFor(() => expect(mockAsk).toHaveBeenCalledTimes(1));
    expect(mockAsk.mock.calls[0][0].case_id).toBeUndefined();
  });
});
