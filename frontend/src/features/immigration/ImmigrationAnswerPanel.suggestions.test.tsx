/**
 * Slice 4 — guided suggested questions reduce the blank-page barrier on the
 * immigration Q&A: clicking a chip fills the question box; the chips disappear
 * once the box has text.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../../api/immigrationAnswer', () => ({ askImmigrationQuestion: vi.fn() }));
vi.mock('../../api/policyAssistantQuery', () => ({ getPolicyAnswer: vi.fn() }));
vi.mock('../../api/assistantRoute', () => ({ routeAssistantDomain: vi.fn(() => Promise.resolve('immigration')) }));
vi.mock('../../api/aiFeedback', () => ({ submitAiFeedback: vi.fn() }));
vi.mock('../../api/immigrationAuthority', () => ({ getDestinationImmigrationAuthority: vi.fn().mockResolvedValue(null) }));

import { ImmigrationAnswerPanel } from './ImmigrationAnswerPanel';

afterEach(cleanup);

describe('ImmigrationAnswerPanel — suggested questions', () => {
  it('clicking a suggestion fills the question box', () => {
    render(<ImmigrationAnswerPanel />);
    fireEvent.click(screen.getByRole('button', { name: 'How long does the visa process usually take?' }));
    expect(screen.getByLabelText('Your question')).toHaveValue('How long does the visa process usually take?');
  });

  it('hides the suggestions once the question box has text', () => {
    render(<ImmigrationAnswerPanel />);
    expect(screen.getByRole('button', { name: 'What documents do I need for the visa application?' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Your question'), { target: { value: 'my own question' } });
    expect(screen.queryByRole('button', { name: 'What documents do I need for the visa application?' })).toBeNull();
  });
});
