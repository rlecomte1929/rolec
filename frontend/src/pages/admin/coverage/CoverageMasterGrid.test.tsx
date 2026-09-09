import '@testing-library/jest-dom/vitest';
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';
import type { CoverageSummary } from '../../../api/coverage';
import { CoverageMasterGrid } from './CoverageMasterGrid';

const SAMPLE: CoverageSummary = {
  generated_at: '2026-09-08T12:00:00.000Z',
  serving_categories: ['banks', 'movers', 'schools', 'legal_admin', 'tax_finance', 'housing_agencies'],
  extra_categories: ['healthcare_ipmi'],
  totals: {
    destinations: 1,
    facts_approved: 3,
    facts_pending: 1,
    facts_rejected: 0,
    facts_total: 4,
    caps_total: 4,
    caps_approved: 2,
    caps_pending: 2,
    suppliers: 2,
    expert_verified: 1,
  },
  countries: [
    {
      iso: 'IE',
      name: 'Ireland',
      flag: '🇮🇪',
      catalog_name: 'IRELAND',
      facts: { approved: 3, pending: 1, rejected: 0, total: 4 },
      providers: {
        by_cat: { banks: 2, movers: 1, schools: 0, legal_admin: 0, tax_finance: 0, housing_agencies: 0 },
        by_cat_detail: {
          banks: { approved: 2, pending: 0, total: 2 },
          movers: { approved: 0, pending: 1, total: 1 },
          healthcare_ipmi: { approved: 0, pending: 1, total: 1 },
        },
        approved: 2,
        pending: 2,
        total: 4,
      },
    },
  ],
};

afterEach(() => cleanup());

function RegistryLanded() {
  const loc = useLocation();
  return <div>{`${loc.pathname}${loc.search}`}</div>;
}

describe('CoverageMasterGrid', () => {
  it('renders live destination and service counts from the payload', () => {
    render(
      <MemoryRouter>
        <CoverageMasterGrid data={SAMPLE} lens="catalog" />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('coverage-master-grid')).toBeInTheDocument();
    expect(screen.getByText('Ireland')).toBeInTheDocument();
    expect(screen.getByTitle('Ireland: 3 approved / 1 pending facts')).toHaveTextContent('3');
    expect(screen.getByTitle('Ireland · Banks: 2 approved / 0 pending')).toHaveTextContent('2');
  });

  it('opens the supplier registry with country and category from a cell click', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/admin/suppliers']}>
        <Routes>
          <Route path="/admin/suppliers" element={<CoverageMasterGrid data={SAMPLE} lens="suppliers" />} />
          <Route path="/admin/suppliers/registry" element={<RegistryLanded />} />
        </Routes>
      </MemoryRouter>,
    );
    await user.click(screen.getByTitle('Ireland · Banks: 2 approved / 0 pending'));
    expect(screen.getByText('/admin/suppliers/registry?country=IE&category=banks')).toBeInTheDocument();
  });
});
