import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import type { ResourcesPagePayload } from '../../types';
import { EMPTY_RESOURCES_FILTERS, ResourcesPageContent } from './ResourcesPageContent';

const getCityActivities = vi.fn();

vi.mock('../../api/client', () => ({
  resourcesAPI: {
    getCityActivities: (...a: unknown[]) => getCityActivities(...a),
  },
}));

const payload: ResourcesPagePayload = {
  context: {
    caseId: 'c1',
    countryCode: 'ES',
    countryName: 'Spain',
    cityName: 'Madrid',
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

function renderContent() {
  return render(
    <ResourcesPageContent
      payload={payload}
      filters={EMPTY_RESOURCES_FILTERS}
      updateFilters={() => undefined}
      clearFilters={() => undefined}
    />,
  );
}

beforeEach(() => {
  getCityActivities.mockReset();
});
afterEach(cleanup);

describe('ResourcesPageContent · settling guide', () => {
  it('renders cultural awareness, first steps, and community when the catalog is empty', () => {
    getCityActivities.mockResolvedValue([]);
    render(
      <ResourcesPageContent
        payload={{
          ...payload,
          settlingGuide: {
            culturalAwareness: {
              intro: 'Norway values work-life balance and punctuality.',
              tips: ['Arrive on time', 'Informal but professional communication'],
              workCulture: ['Typical hours: 37.5/week'],
            },
            firstSteps: [
              {
                title: 'Residence registration (Folkeregisteret)',
                timeline: 'Within 7 days',
                url: 'https://www.skatteetaten.no/',
              },
            ],
            community: {
              overview: 'Expat communities and professional networks.',
              groups: [{ title: 'Internations Oslo', url: 'https://www.internations.org/oslo-expats', description: 'Expat meetups' }],
            },
            practicalTips: ['Keep emergency numbers in phone'],
            emergency: '113',
          },
        }}
        filters={EMPTY_RESOURCES_FILTERS}
        updateFilters={() => undefined}
        clearFilters={() => undefined}
      />,
    );
    expect(screen.getByRole('heading', { name: /cultural awareness/i })).toBeInTheDocument();
    expect(screen.getByText(/work-life balance/i)).toBeInTheDocument();
    expect(screen.getByText(/Arrive on time/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /first steps to settle in/i })).toBeInTheDocument();
    expect(screen.getByText(/Folkeregisteret/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /communities/i })).toBeInTheDocument();
    expect(screen.getByText(/Internations Oslo/)).toBeInTheDocument();
    expect(screen.queryByText(/No resources available for this destination yet/i)).not.toBeInTheDocument();
  });
});

describe('ResourcesPageContent · city activities', () => {
  it('surfaces an error when the city activities request fails', async () => {
    getCityActivities.mockRejectedValue(new Error('Could not load city activities.'));
    renderContent();
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Could not load city activities.'));
  });

  it('does not show an error when the city activities list is genuinely empty', async () => {
    getCityActivities.mockResolvedValue([]);
    renderContent();
    await waitFor(() => expect(getCityActivities).toHaveBeenCalled());
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.queryByText(/Things to do in Madrid/i)).not.toBeInTheDocument();
  });
});
