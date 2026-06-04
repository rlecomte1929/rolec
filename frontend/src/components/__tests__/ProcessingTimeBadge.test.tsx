/**
 * ProcessingTimeBadge — P2-04c.
 *
 * Covers the Validation Criteria:
 *   1. platform_data branch renders correct copy + the sample size is visible.
 *   2. official_only branch renders correct copy + a source citation.
 *   3. The two sources are visually distinguishable (different confidence indicator).
 *   4. A null estimate renders nothing (never a processing time without a source).
 */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect, afterEach } from 'vitest';

import {
  ProcessingTimeBadge,
  type ProcessingTimeEstimate,
} from '../ProcessingTimeBadge';

afterEach(cleanup);

const platformEstimate: ProcessingTimeEstimate = {
  p50_days: 14, // 2 weeks
  p90_days: 21, // 3 weeks
  source: 'platform_data',
  sample_size: 25,
  last_updated: '2026-06-04',
  source_url: null,
};

const officialEstimate: ProcessingTimeEstimate = {
  p50_days: 28, // 4 weeks
  p90_days: 84, // 12 weeks
  source: 'official_only',
  sample_size: 0,
  last_updated: '2026-05-30',
  source_url: 'https://www.make-it-in-germany.com/en/visa-residence/types/eu-blue-card',
};

describe('ProcessingTimeBadge — platform_data branch', () => {
  it('renders the week range and makes the sample size visible', () => {
    render(<ProcessingTimeBadge estimate={platformEstimate} />);
    expect(screen.getByText(/Est\. processing:/)).toBeInTheDocument();
    expect(screen.getByText('2–3 weeks')).toBeInTheDocument();
    expect(screen.getByText(/based on 25 similar cases/)).toBeInTheDocument();
    expect(screen.getByTestId('processing-time-badge')).toHaveAttribute(
      'data-source',
      'platform_data',
    );
  });

  it('uses the singular "case" when the sample size is 1', () => {
    render(<ProcessingTimeBadge estimate={{ ...platformEstimate, sample_size: 1 }} />);
    expect(screen.getByText(/based on 1 similar case\)/)).toBeInTheDocument();
  });
});

describe('ProcessingTimeBadge — official_only branch', () => {
  it('renders the week range with the official-estimate disclaimer', () => {
    render(<ProcessingTimeBadge estimate={officialEstimate} />);
    expect(screen.getByText('4–12 weeks')).toBeInTheDocument();
    expect(screen.getByText(/insufficient platform data/)).toBeInTheDocument();
    expect(screen.queryByText(/similar case/)).not.toBeInTheDocument();
  });

  it('links the source citation when source_url is present', () => {
    render(<ProcessingTimeBadge estimate={officialEstimate} />);
    const link = screen.getByRole('link', { name: 'official estimate' });
    expect(link).toHaveAttribute('href', officialEstimate.source_url);
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'));
  });

  it('shows plain text (no link) when source_url is missing', () => {
    render(<ProcessingTimeBadge estimate={{ ...officialEstimate, source_url: null }} />);
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.getByText(/official estimate/)).toBeInTheDocument();
  });
});

describe('ProcessingTimeBadge — confidence distinction & guards', () => {
  it('marks the two sources differently via data-source for at-a-glance distinction', () => {
    const { rerender } = render(<ProcessingTimeBadge estimate={platformEstimate} />);
    expect(screen.getByTestId('processing-time-badge')).toHaveAttribute(
      'data-source',
      'platform_data',
    );
    rerender(<ProcessingTimeBadge estimate={officialEstimate} />);
    expect(screen.getByTestId('processing-time-badge')).toHaveAttribute(
      'data-source',
      'official_only',
    );
  });

  it('renders nothing when there is no estimate', () => {
    const { container } = render(<ProcessingTimeBadge estimate={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('floors sub-week ranges at 1 week rather than showing "0 weeks"', () => {
    render(
      <ProcessingTimeBadge
        estimate={{ ...platformEstimate, p50_days: 1, p90_days: 4 }}
      />,
    );
    expect(screen.getByText('1 week')).toBeInTheDocument();
  });
});
