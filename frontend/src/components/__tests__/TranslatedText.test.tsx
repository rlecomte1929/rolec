/**
 * TranslatedText — Parker-I neural translation wrapper.
 *
 * Covers:
 *   1. Renders the original text immediately (no flash of empty content).
 *   2. Replaces with the translation + shows the "Translated" badge on success.
 *   3. Falls back to the original (no badge) when the API errors.
 *   4. Skips translation when target === source.
 */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';

import { TranslatedText } from '../TranslatedText';
import { translateText } from '../../api/translation';

vi.mock('../../api/translation', () => ({
  translateText: vi.fn(),
}));

const mockedTranslate = vi.mocked(translateText);

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

it('renders the original text immediately', () => {
  mockedTranslate.mockReturnValue(new Promise(() => {})); // never resolves
  render(<TranslatedText text="Welcome to Berlin" src="en" tgt="de" />);
  expect(screen.getByText('Welcome to Berlin')).toBeInTheDocument();
});

it('shows the translation and a Translated badge on success', async () => {
  mockedTranslate.mockResolvedValue({
    text: 'Willkommen in Berlin',
    provider: 'deepl',
    model_version: 'deepl-pro',
    cost_usd: 0.0001,
    cache_hit: false,
  });
  render(<TranslatedText text="Welcome to Berlin" src="en" tgt="de" />);
  await waitFor(() => expect(screen.getByText('Willkommen in Berlin')).toBeInTheDocument());
  expect(screen.getByText('Translated')).toBeInTheDocument();
});

it('falls back to the original on API error, without a badge', async () => {
  mockedTranslate.mockRejectedValue(new Error('boom'));
  render(<TranslatedText text="Welcome to Berlin" src="en" tgt="de" />);
  await waitFor(() => expect(mockedTranslate).toHaveBeenCalled());
  expect(screen.getByText('Welcome to Berlin')).toBeInTheDocument();
  expect(screen.queryByText('Translated')).not.toBeInTheDocument();
});

it('does not translate when target equals source', () => {
  render(<TranslatedText text="Welcome to Berlin" src="en" tgt="en" />);
  expect(mockedTranslate).not.toHaveBeenCalled();
  expect(screen.getByText('Welcome to Berlin')).toBeInTheDocument();
});
