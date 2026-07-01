import '@testing-library/jest-dom/vitest';
import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { hrAPI } from '../../../api/client';
import { CasePredictionCard } from '../CasePredictionCard';

vi.mock('../../../api/client', () => ({ hrAPI: { getCasePredictedDuration: vi.fn() } }));

const mocked = <T,>(fn: T) => fn as T & ReturnType<typeof vi.fn>;

const renderCard = (caseId = 'case-1') =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <CasePredictionCard caseId={caseId} />
    </QueryClientProvider>,
  );

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('CasePredictionCard', () => {
  it('renders the predicted duration, confidence range, and sample size', async () => {
    mocked(hrAPI.getCasePredictedDuration).mockResolvedValue({
      median_days: 42.4,
      p20_days: 30.2,
      p80_days: 55.8,
      model_version: '1.0.0',
      n_training_cases: 128,
    });

    renderCard();

    await waitFor(() => expect(screen.getByText('~42 days')).toBeInTheDocument());
    expect(screen.getByText('30–56 day range')).toBeInTheDocument();
    expect(screen.getByText(/128 comparable cases/)).toBeInTheDocument();
  });

  it('renders nothing when the endpoint 404s (canary off / no model / no access)', async () => {
    mocked(hrAPI.getCasePredictedDuration).mockRejectedValue(
      Object.assign(new Error('Not Found'), { response: { status: 404 } }),
    );

    const { container } = renderCard();

    await waitFor(() => expect(mocked(hrAPI.getCasePredictedDuration)).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
