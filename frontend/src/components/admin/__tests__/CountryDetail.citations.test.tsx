import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { CountryDetail } from '../CountryDetail';
import type { AdminRequirementReview } from '../../../api/admin';
import type { CountryProfileDTO } from '../../../types';

/**
 * The review surface has to render every citation shape `citations_json` holds.
 *
 * It used to type `citations` as `string[]` and call `c.startsWith('http')` on each entry. Since
 * #1941 the promoter writes citations as OBJECTS, so that threw `c.startsWith is not a function`
 * at render time and keyed the list on `[object Object]`. The backend 500 masked it — once that
 * is fixed, this is the next thing that breaks, on the same screen, for the same rows.
 *
 * The unresolved case is not hypothetical: FRANCE holds 14 non-URL string citations of which only
 * 4 resolve in `source_records`. Those must stay VISIBLE here. Dropping them the way the employee
 * reader does would hide a missing source from the one person deciding whether to publish.
 */

const PROFILE: CountryProfileDTO = {
  countryCode: 'IRELAND',
  lastUpdatedAt: '2026-08-21T09:26:57Z',
  confidenceScore: 0.9,
  sources: [],
  requirementGroups: [],
};

function requirement(overrides: Partial<AdminRequirementReview> = {}): AdminRequirementReview {
  return {
    id: 'a114fd40-f8d1-5562-aba4-d0e83e127670',
    purpose: 'employment',
    pillar: 'RESIDENCE',
    title: "Spouse's Stamp 1G — work without a separate permit",
    description: 'The spouse of a CSEP holder is registered on a Stamp 1G on arrival.',
    severity: 'WARN',
    owner: 'EMPLOYEE',
    verificationStatus: 'representative',
    reviewStatus: 'pending',
    appliesToNationalityClasses: ['THIRD_COUNTRY'],
    citations: [],
    ...overrides,
  };
}

function renderDetail(requirements: AdminRequirementReview[]) {
  render(
    <CountryDetail
      profile={PROFILE}
      requirements={requirements}
      pendingCount={requirements.filter((r) => r.reviewStatus === 'pending').length}
      busyId={null}
      onRerun={vi.fn()}
      onReview={vi.fn()}
    />
  );
}

describe('CountryDetail citations', () => {
  it('renders a resolved citation as a link labelled by its source name', () => {
    renderDetail([
      requirement({
        citations: [
          {
            id: 'https://www.citizensinformation.ie/en/moving-country/visas-for-ireland/',
            url: 'https://www.citizensinformation.ie/en/moving-country/visas-for-ireland/',
            title: 'Citizens Information — Visa requirements for entering Ireland',
            publisherDomain: 'www.citizensinformation.ie',
          },
        ],
      }),
    ]);

    const link = screen.getByRole('link', {
      name: 'Citizens Information — Visa requirements for entering Ireland',
    });
    expect(link).toHaveAttribute(
      'href',
      'https://www.citizensinformation.ie/en/moving-country/visas-for-ireland/'
    );
  });

  it('shows an unresolved reference instead of silently dropping it', () => {
    renderDetail([
      requirement({
        citations: [
          {
            id: 'fr-src-0007-not-in-source-records',
            url: null,
            title: 'fr-src-0007-not-in-source-records',
            publisherDomain: null,
          },
        ],
      }),
    ]);

    expect(screen.getByText(/fr-src-0007-not-in-source-records/)).toBeInTheDocument();
    expect(screen.getByText(/unresolved source/i)).toBeInTheDocument();
    // No link, because there is nothing to link to.
    expect(screen.queryByRole('link', { name: /fr-src-0007/ })).not.toBeInTheDocument();
  });

  it('renders a whole country of rows without throwing', () => {
    // The real IRELAND shape: object-derived citations beside legacy resolved ones. The old
    // renderer threw on the first object and took the entire list down.
    const rows = [
      ...Array.from({ length: 9 }, (_, i) =>
        requirement({
          id: `object-row-${i}`,
          citations: [
            {
              id: `https://www.irishimmigration.ie/${i}`,
              url: `https://www.irishimmigration.ie/${i}`,
              title: 'Immigration Service Delivery',
              publisherDomain: 'www.irishimmigration.ie',
            },
          ],
        })
      ),
      ...Array.from({ length: 20 }, (_, i) =>
        requirement({
          id: `legacy-row-${i}`,
          reviewStatus: 'approved',
          citations: [
            {
              id: `1f0e8a2c-0000-4000-8000-00000000000${i}`,
              url: 'https://enterprise.gov.ie/permits/',
              title: 'DETE — employment permits',
              publisherDomain: 'enterprise.gov.ie',
            },
          ],
        })
      ),
    ];

    renderDetail(rows);

    expect(screen.getAllByRole('link', { name: 'Immigration Service Delivery' })).toHaveLength(9);
    expect(screen.getAllByRole('link', { name: 'DETE — employment permits' })).toHaveLength(20);
  });
});

describe('CountryDetail bulk review', () => {
  it('publishes every ticked requirement in one action', () => {
    const onReviewBatch = vi.fn();
    const rows = [
      requirement({ id: 'req-a', title: 'Employment Pass' }),
      requirement({ id: 'req-b', title: 'MOM medical' }),
    ];
    render(
      <CountryDetail
        profile={PROFILE}
        requirements={rows}
        pendingCount={2}
        busyId={null}
        onRerun={vi.fn()}
        onReview={vi.fn()}
        onReviewBatch={onReviewBatch}
      />
    );

    fireEvent.click(screen.getByLabelText('Select all requirements'));
    fireEvent.click(screen.getByRole('button', { name: /Publish selected \(2\)/ }));

    expect(onReviewBatch).toHaveBeenCalledWith(['req-a', 'req-b'], 'approved');
  });
});
