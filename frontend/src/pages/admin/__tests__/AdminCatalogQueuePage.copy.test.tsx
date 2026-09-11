import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../AdminLayout', () => ({
  AdminLayout: ({
    title,
    subtitle,
    children,
  }: {
    title: string;
    subtitle?: string;
    children: React.ReactNode;
  }) => (
    <div>
      <h1>{title}</h1>
      {subtitle ? <p>{subtitle}</p> : null}
      {children}
    </div>
  ),
}));
vi.mock('../DiscoverSection', () => ({ DiscoverSection: () => null }));
vi.mock('../../../api/adminCatalog', () => ({
  listAdminDestinationRequests: vi.fn(),
  listAllowlist: vi.fn(),
  listDemandGaps: vi.fn(),
  listIntakeCorridors: vi.fn(),
  resolveDestinationRequest: vi.fn(),
  addAllowlistEntry: vi.fn(),
  fillDemandGap: vi.fn(),
}));

import {
  fillDemandGap,
  listAdminDestinationRequests,
  listAllowlist,
  listDemandGaps,
  listIntakeCorridors,
} from '../../../api/adminCatalog';
import { AdminCatalogQueuePage } from '../AdminCatalogQueuePage';
import { CATALOG_QUEUE_INTRO_HEADING, FIND_PROVIDERS_LABEL } from '../catalogQueueCopy';

const asMock = (fn: unknown) => fn as ReturnType<typeof vi.fn>;

beforeEach(() => {
  asMock(listAllowlist).mockResolvedValue([]);
  asMock(listDemandGaps).mockResolvedValue([
    {
      category: 'movers',
      city: 'Oslo',
      country: 'Norway',
      demand: 4,
      companies: 1,
      last_seen_at: '2026-09-01T00:00:00Z',
      allowlisted: false,
    },
  ]);
  asMock(listIntakeCorridors).mockResolvedValue([]);
  asMock(listAdminDestinationRequests).mockResolvedValue([]);
  asMock(fillDemandGap).mockResolvedValue({
    allowlisted: true,
    scraped_count: 0,
    lookup_ran: false,
    category: 'movers',
    city: 'Oslo',
    country: 'Norway',
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('AdminCatalogQueuePage operator copy', () => {
  it('shows a plain-English intro and a Find providers action', async () => {
    render(<AdminCatalogQueuePage />);
    expect(await screen.findByRole('heading', { name: CATALOG_QUEUE_INTRO_HEADING })).toBeInTheDocument();
    expect(screen.getByText(/sometimes called the allowlist/i)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /find movers providers in oslo/i }),
    ).toHaveTextContent(FIND_PROVIDERS_LABEL);
  });

  it('does not tell the operator the scraper is disabled', async () => {
    render(<AdminCatalogQueuePage />);
    fireEvent.click(
      await screen.findByRole('button', { name: /find movers providers in oslo/i }),
    );
    await waitFor(() =>
      expect(screen.getByText(/automatic lookup is off/i)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/scraper/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/api key/i)).not.toBeInTheDocument();
  });
});
