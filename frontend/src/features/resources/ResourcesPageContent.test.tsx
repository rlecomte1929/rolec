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
