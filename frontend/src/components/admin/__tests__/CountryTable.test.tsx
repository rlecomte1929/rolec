import '@testing-library/jest-dom/vitest';
import { describe, it, expect } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { CountryTable } from '../CountryTable';
import type { CountryListDTO } from '../../../types';
import {
  catalogConfidenceScore,
  confidenceLevel,
  confidencePercent,
  countRequirementStatuses,
  displayCatalogLabel,
  displayCountryName,
  filterCatalog,
  filterRequirements,
  formatUpdatedLabel,
  groupRequirementsByPillar,
  isCatalogStale,
  sortCatalog,
  summarizeCatalog,
} from '../countryCatalog';

const DATA: CountryListDTO = {
  countries: [
    {
      countryCode: 'DE',
      lastUpdatedAt: '2026-08-01T00:00:00Z',
      requirementsCount: 12,
      confidenceScore: 0.9,
      topDomains: ['bamf.de', 'make-it-in-germany.com'],
    },
    {
      countryCode: 'FR',
      lastUpdatedAt: '2025-01-01T00:00:00Z',
      requirementsCount: 0,
      confidenceScore: 0.2,
      topDomains: [],
    },
    {
      countryCode: 'NO',
      lastUpdatedAt: '2026-09-01T00:00:00Z',
      requirementsCount: 4,
      confidenceScore: 0.55,
      topDomains: ['udi.no'],
    },
  ],
};

describe('countryCatalog helpers', () => {
  it('treats 0–1 scores as percents', () => {
    expect(confidencePercent(0.9)).toBe(90);
    expect(confidenceLevel(0.9)).toBe('high');
    expect(confidenceLevel(0.55)).toBe('medium');
    expect(confidenceLevel(0.2)).toBe('low');
    expect(confidenceLevel(undefined)).toBe('unknown');
  });

  it('flags missing or old catalogs as needing refresh', () => {
    const now = new Date('2026-09-08T00:00:00Z');
    expect(isCatalogStale(undefined, now)).toBe(true);
    expect(isCatalogStale('2026-08-01T00:00:00Z', now)).toBe(false);
    expect(isCatalogStale('2025-01-01T00:00:00Z', now)).toBe(true);
  });

  it('summarizes coverage so empty and stale rows are countable', () => {
    const now = new Date('2026-09-08T00:00:00Z');
    expect(summarizeCatalog(DATA.countries, now)).toEqual({
      countries: 3,
      requirements: 16,
      empty: 1,
      needsRefresh: 1,
    });
  });

  it('filters by name, code, domain, and attention', () => {
    const now = new Date('2026-09-08T00:00:00Z');
    expect(filterCatalog(DATA.countries, 'germany', 'all', now).map((r) => r.countryCode)).toEqual(['DE']);
    expect(filterCatalog(DATA.countries, 'udi.no', 'all', now).map((r) => r.countryCode)).toEqual(['NO']);
    expect(filterCatalog(DATA.countries, '', 'empty', now).map((r) => r.countryCode)).toEqual(['FR']);
    expect(filterCatalog(DATA.countries, '', 'refresh', now).map((r) => r.countryCode)).toEqual(['FR']);
  });

  it('sorts by name by default and by requirements descending', () => {
    expect(sortCatalog(DATA.countries, 'name').map((r) => r.countryCode)).toEqual(['FR', 'DE', 'NO']);
    expect(sortCatalog(DATA.countries, 'requirements').map((r) => r.countryCode)).toEqual(['DE', 'NO', 'FR']);
  });

  it('formats relative update labels', () => {
    const now = new Date('2026-09-08T12:00:00Z');
    expect(formatUpdatedLabel('2026-09-08T00:00:00Z', now).relative).toBe('Today');
    expect(formatUpdatedLabel(undefined, now).relative).toBe('Never updated');
  });

  it('groups requirements by pillar with pending first', () => {
    const grouped = groupRequirementsByPillar([
      {
        id: 'a',
        purpose: 'employment',
        pillar: 'TAX',
        title: 'Tax card',
        description: 'Apply for a skattekort.',
        severity: 'WARN',
        owner: 'EMPLOYEE',
        reviewStatus: 'approved',
        citations: [],
      },
      {
        id: 'b',
        purpose: 'employment',
        pillar: 'RESIDENCE',
        title: 'Residence permit',
        description: 'Register after arrival.',
        severity: 'BLOCK',
        owner: 'EMPLOYEE',
        reviewStatus: 'pending',
        citations: [],
      },
    ]);
    expect(grouped.map((g) => g.pillar)).toEqual(['RESIDENCE', 'TAX']);
    expect(grouped[0].items[0].title).toBe('Residence permit');
    expect(countRequirementStatuses(grouped.flatMap((g) => g.items))).toEqual({
      all: 2,
      pending: 1,
      approved: 1,
      rejected: 0,
    });
    expect(filterRequirements(grouped.flatMap((g) => g.items), '', 'pending')).toHaveLength(1);
    expect(displayCatalogLabel('THIRD_COUNTRY')).toBe('Third Country');
  });

  it('resolves catalog full names to a single English label', () => {
    expect(displayCountryName('FRANCE')).toBe('France');
    expect(displayCountryName('AUSTRALIA')).toBe('Australia');
  });

  it('does not treat an empty catalog as high confidence', () => {
    expect(
      catalogConfidenceScore({
        requirementsCount: 0,
        confidenceScore: 0.95,
        topDomains: [],
      }),
    ).toBeNull();
    expect(confidenceLevel(null)).toBe('unknown');
  });
});

describe('CountryTable', () => {
  it('scrolls wide catalog columns instead of clipping them', () => {
    const { container } = render(<CountryTable data={DATA} onSelect={() => undefined} />);
    expect(container.querySelector('.overflow-x-auto')).toBeTruthy();
  });

  it('renders country names with an ISO chip and coverage stats', () => {
    render(<CountryTable data={DATA} onSelect={() => undefined} />);
    expect(screen.getByTestId('catalog-stat-countries')).toHaveTextContent('3');
    expect(screen.getByTestId('catalog-stat-requirements')).toHaveTextContent('16');
    expect(screen.getByTestId('catalog-stat-empty')).toHaveTextContent('1');
    expect(screen.getAllByText('Germany').length).toBeGreaterThan(0);
    expect(screen.getAllByText('France').length).toBeGreaterThan(0);
    expect(screen.getAllByText('DE').length).toBeGreaterThan(0);
    expect(screen.getAllByText('FR').length).toBeGreaterThan(0);
  });

  it('narrows the list when searching', () => {
    render(<CountryTable data={DATA} onSelect={() => undefined} />);
    fireEvent.change(screen.getByLabelText('Search country catalogs'), { target: { value: 'norway' } });
    expect(screen.getAllByText('Norway').length).toBeGreaterThan(0);
    expect(screen.queryByText('Germany')).not.toBeInTheDocument();
  });

  it('does not present a seed confidence percent as catalog quality on empty destinations', () => {
    render(<CountryTable data={DATA} onSelect={() => undefined} />);
    expect(screen.getAllByText('No evidence').length).toBeGreaterThan(0);
    expect(screen.queryByText('20%')).not.toBeInTheDocument();
    expect(screen.getAllByText('90%').length).toBeGreaterThan(0);
  });

  it('filters to empty catalogs when the empty tile is pressed', () => {
    render(<CountryTable data={DATA} onSelect={() => undefined} />);
    fireEvent.click(screen.getByTestId('catalog-stat-empty'));
    expect(screen.getAllByText('France').length).toBeGreaterThan(0);
    expect(screen.queryByText('Germany')).not.toBeInTheDocument();
  });

  it('does not repeat the catalog key next to the country name', () => {
    render(
      <CountryTable
        data={{
          countries: [
            {
              countryCode: 'FRANCE',
              lastUpdatedAt: '2026-08-01T00:00:00Z',
              requirementsCount: 0,
              confidenceScore: 0.95,
              topDomains: [],
            },
          ],
        }}
        onSelect={() => undefined}
      />,
    );
    expect(screen.getAllByText('France').length).toBeGreaterThan(0);
    expect(screen.queryByText('FRANCE')).not.toBeInTheDocument();
    expect(screen.getAllByText('FR').length).toBeGreaterThan(0);
    expect(screen.queryByText('High')).not.toBeInTheDocument();
    expect(screen.getAllByText('No evidence').length).toBeGreaterThan(0);
  });
});
