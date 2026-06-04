/**
 * ProcessingTimeCard — P2-04 integration bridge.
 * Fetches the estimate and renders the badge; renders nothing when there's none.
 */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';

import { ProcessingTimeCard } from '../ProcessingTimeCard';
import { getProcessingTime } from '../../../api/processingTime';

vi.mock('../../../api/processingTime', () => ({ getProcessingTime: vi.fn() }));

const mockedGet = vi.mocked(getProcessingTime);

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('ProcessingTimeCard', () => {
  it('renders the labelled card + badge when an estimate is returned', async () => {
    mockedGet.mockResolvedValue({
      p50_days: 28,
      p90_days: 84,
      source: 'official_only',
      sample_size: 0,
      last_updated: '2026-05-30',
      source_url: 'https://example.test/eu-blue-card',
    });
    render(<ProcessingTimeCard caseId="c1" />);
    await waitFor(() => expect(screen.getByText('4–12 weeks')).toBeInTheDocument());
    expect(screen.getByText('Processing time')).toBeInTheDocument();
    expect(mockedGet).toHaveBeenCalledWith('c1');
  });

  it('renders nothing when there is no estimate', async () => {
    mockedGet.mockResolvedValue(null);
    const { container } = render(<ProcessingTimeCard caseId="c1" />);
    await waitFor(() => expect(mockedGet).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
