import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CountryTable } from '../CountryTable';
import type { CountryListDTO } from '../../../types';

const DATA: CountryListDTO = {
  countries: [
    {
      countryCode: 'SINGAPORE',
      countryName: 'Singapore',
      isoCode: 'SG',
      lastUpdatedAt: '2026-08-01T00:00:00Z',
      requirementsCount: 11,
      publishedCount: 0,
      pendingCount: 11,
      confidenceScore: 0.8,
      topDomains: ['mom.gov.sg'],
    },
    {
      countryCode: 'GERMANY',
      countryName: 'Germany',
      isoCode: 'DE',
      lastUpdatedAt: '2026-07-01T00:00:00Z',
      requirementsCount: 4,
      publishedCount: 4,
      pendingCount: 0,
      confidenceScore: 0.5,
      topDomains: ['bamf.de'],
    },
    {
      countryCode: 'DENMARK',
      countryName: 'Denmark',
      isoCode: 'DK',
      requirementsCount: 2,
      publishedCount: 2,
      pendingCount: 0,
      topDomains: [],
    },
  ],
};

describe('CountryTable', () => {
  it('renders a real table with full country names, not a second ISO-only row', () => {
    render(<CountryTable data={DATA} onSelect={vi.fn()} />);

    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText('Singapore')).toBeInTheDocument();
    expect(screen.getByText('Germany')).toBeInTheDocument();
    expect(screen.getByText('Denmark')).toBeInTheDocument();
    expect(screen.queryByText('SG')).toBeInTheDocument();
    expect(screen.getByText('11 pending')).toBeInTheDocument();
  });

  it('renders a flag glyph for ISO codes that were previously unmapped', () => {
    const { container } = render(<CountryTable data={DATA} onSelect={vi.fn()} />);
    expect(container.querySelector('.fi.fi-sg')).toBeTruthy();
    expect(container.querySelector('.fi.fi-de')).toBeTruthy();
    expect(container.querySelector('.fi.fi-dk')).toBeTruthy();
  });

  it('opens the catalog key for the row, not the ISO code', async () => {
    const onSelect = vi.fn();
    render(<CountryTable data={DATA} onSelect={onSelect} />);
    screen.getByText('Singapore').closest('tr')?.click();
    expect(onSelect).toHaveBeenCalledWith('SINGAPORE');
  });
});
