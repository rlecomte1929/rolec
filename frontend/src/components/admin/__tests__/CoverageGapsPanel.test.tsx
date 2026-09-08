import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { CoverageGapsPanel } from '../CoverageGapsPanel';
import type { DemandGap } from '../../../api/adminCatalog';

function gap(overrides: Partial<DemandGap> = {}): DemandGap {
  return {
    category: 'movers',
    city: 'Munich',
    country: 'Germany',
    demand: 4,
    companies: 1,
    last_seen_at: null,
    allowlisted: false,
    ...overrides,
  };
}

const GAPS: DemandGap[] = [
  gap({ category: 'movers', city: 'Munich', country: 'Germany', demand: 8 }),
  gap({ category: 'movers', city: 'Oslo', country: 'Norway', demand: 3 }),
  gap({ category: 'housing', city: 'Munich', country: 'Germany', demand: 2 }),
];

describe('CoverageGapsPanel', () => {
  it('groups by service first and can switch to location or country', () => {
    render(<CoverageGapsPanel gaps={GAPS} loading={false} filling={false} onFill={vi.fn()} />);

    expect(screen.getByText('movers')).toBeInTheDocument();
    expect(screen.getAllByText(/Munich/).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: 'Location' }));
    expect(screen.getByText('Munich, Germany')).toBeInTheDocument();
    expect(screen.getByText('housing')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Country' }));
    expect(screen.getByText('Germany')).toBeInTheDocument();
    expect(screen.getByText('Norway')).toBeInTheDocument();
  });

  it('filters by service chip', () => {
    render(<CoverageGapsPanel gaps={GAPS} loading={false} filling={false} onFill={vi.fn()} />);
    fireEvent.click(screen.getByRole('checkbox', { name: 'Filter services: housing' }));
    expect(screen.queryByLabelText('Select all in movers')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Select all in housing')).toBeInTheDocument();
  });

  it('fills every ticked gap in one action', () => {
    const onFill = vi.fn();
    render(<CoverageGapsPanel gaps={GAPS} loading={false} filling={false} onFill={onFill} />);
    fireEvent.click(screen.getByLabelText('Select all visible gaps'));
    fireEvent.click(screen.getByRole('button', { name: /Allowlist & scrape selected \(3\)/ }));
    expect(onFill).toHaveBeenCalledTimes(1);
    expect(onFill.mock.calls[0][0]).toHaveLength(3);
  });
});
