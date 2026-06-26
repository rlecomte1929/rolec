import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ResourcesPageContent, EMPTY_RESOURCES_FILTERS } from '../ResourcesPageContent';
import type { ResourcesPagePayload } from '../../../types';

vi.mock('../../../components/antigravity', async () => {
  const actual = await vi.importActual<typeof import('../../../components/antigravity')>(
    '../../../components/antigravity',
  );
  return actual;
});

const payload: ResourcesPagePayload = {
  context: {
    caseId: 'case-1',
    countryCode: 'CA',
    countryName: null,
    cityName: null,
    familyType: 'single',
    hasChildren: false,
    childAges: [],
    recommendedTags: [],
  },
  categories: [],
  resources: [],
  events: [],
  recommended: {
    recommendedForYou: [],
    firstSteps: [],
    familyEssentials: [],
    thisWeekend: [],
  },
  hints: { priorities: [], recommendations: [] },
  filtersApplied: {},
};

describe('ResourcesPageContent', () => {
  it('uses a full country name when context only has a country code', () => {
    render(
      <ResourcesPageContent
        payload={payload}
        filters={EMPTY_RESOURCES_FILTERS}
        updateFilters={() => {}}
        clearFilters={() => {}}
      />,
    );

    expect(screen.getByRole('heading', { name: 'Welcome to Canada' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Events in Canada' })).toBeInTheDocument();
    expect(screen.queryByText('Welcome to CA')).not.toBeInTheDocument();
  });
});
