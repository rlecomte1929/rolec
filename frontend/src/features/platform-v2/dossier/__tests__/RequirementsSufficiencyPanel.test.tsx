/**
 * [AIQ-1821] RequirementsSufficiencyPanel.
 *
 * The endpoint answers HTTP 200 for BOTH degraded states, so the risk this panel carries is
 * not a crash — it is quietly telling a relocating employee that nothing is required of them
 * while the backend is broken or while we simply hold no data. Every test below exists to
 * pin a state as *distinguishable*, and `test_no_state_ever_claims_completeness` asserts the
 * negative directly.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const mockGetSufficiency = vi.fn();

// api/client pulls the Supabase singleton, which calls createClient() at module load and
// throws "supabaseUrl is required" with no env (established pattern in this repo).
vi.mock('../../../../api/supabase', () => ({ supabase: {} }));
vi.mock('../../../../api/supabaseAuth', () => ({ signOutSupabase: vi.fn() }));
vi.mock('../../../../api/client', () => ({
  requirementsAPI: { getSufficiency: (...a: unknown[]) => mockGetSufficiency(...a) },
}));

import { RequirementsSufficiencyPanel } from '../RequirementsSufficiencyPanel';

const CASE_ID = 'case-1';

const ok = (over: Record<string, unknown> = {}) => ({
  compute_status: 'ok',
  message: null,
  destination_country: 'NO',
  missing_fields: [],
  supporting_requirements: [],
  ...over,
});

const FACT = {
  fact_id: 'f1',
  fact_text: 'You must provide a certified copy of your proof of identity when requested.',
  source_url: 'https://www.skatteetaten.no/en/person/foreign/norwegian-identification-number/d-number/',
  required_fields: [],
  citation_status: 'verified' as const,
};

/** Same shape, but nobody has ever opened the source to check the quote. */
const UNVERIFIED_FACT = {
  ...FACT,
  fact_id: 'f2',
  fact_text: 'You must register your move with the population register within eight days.',
  source_url: 'https://www.udi.no/en/word-definitions/registration-certificate/',
  citation_status: 'unverified' as const,
};

/**
 * Wording that would tell someone they have no obligations.
 *
 * Deliberately does NOT include "nothing is required of you": the panel says that phrase on
 * purpose, negated ("this does not mean nothing is required of you"). A naive regex flags the
 * honest copy as the dishonest claim — so the negated form is asserted separately below.
 */
const COMPLETENESS_CLAIMS = /you'?re all set|no requirements apply|all complete|everything is complete|you have no obligations/i;

/** Any mention of the phrase must be negated. */
const expectPhraseIsNegated = (text: string) => {
  const idx = text.toLowerCase().indexOf('nothing is required of you');
  if (idx === -1) return;
  expect(text.slice(Math.max(0, idx - 40), idx).toLowerCase()).toMatch(/not|does not|doesn’t/);
};

beforeEach(() => {
  mockGetSufficiency.mockReset();
});

const renderPanel = () => render(<RequirementsSufficiencyPanel caseId={CASE_ID} />);

describe('loading', () => {
  it('marks the region busy while fetching', async () => {
    mockGetSufficiency.mockReturnValue(new Promise(() => {}));
    renderPanel();
    expect(await screen.findByText(/loading the requirements on record/i)).toBeInTheDocument();
  });
});

describe('populated', () => {
  it('renders each approved fact with a working source link', async () => {
    mockGetSufficiency.mockResolvedValue(ok({ supporting_requirements: [FACT] }));
    renderPanel();

    expect(await screen.findByText(FACT.fact_text)).toBeInTheDocument();
    const link = screen.getByRole('link', { name: /skatteetaten\.no/i });
    expect(link).toHaveAttribute('href', FACT.source_url);
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('shows the mandatory immigration disclaimer alongside facts (AIQ-1349)', async () => {
    mockGetSufficiency.mockResolvedValue(ok({ supporting_requirements: [FACT] }));
    const { container } = renderPanel();
    await screen.findByText(FACT.fact_text);
    // Alert maps warning → role="status" (AIQ-397), so assert on the shared copy itself.
    const { IMMIGRATION_DISCLAIMER_TITLE } = await import(
      '../../../immigration/immigrationDisclaimerContent'
    );
    expect(container.textContent).toContain(IMMIGRATION_DISCLAIMER_TITLE);
  });

  it('omits the disclaimer when there is nothing to disclaim', async () => {
    mockGetSufficiency.mockResolvedValue(ok());
    const { container } = renderPanel();
    await screen.findByTestId('sufficiency-empty');
    const { IMMIGRATION_DISCLAIMER_TITLE } = await import(
      '../../../immigration/immigrationDisclaimerContent'
    );
    expect(container.textContent).not.toContain(IMMIGRATION_DISCLAIMER_TITLE);
  });
});

/**
 * [AIQ-2132] Provenance is the product. `list_approved_requirement_facts` serves two evidence
 * states side by side — PR #1851 excludes only `evidence_verified = FALSE`, so NULL ("never
 * checked") still serves. Measured on production 2026-08-22: of the 205 served facts, 121 are
 * verified and 84 have never been checked, and this panel rendered both with the identical
 * "Source: host" anchor.
 *
 * These tests fail against the pre-fix render, which had one anchor for both.
 */
describe('verified vs unverified citations', () => {
  it('labels a verified citation as verified', async () => {
    mockGetSufficiency.mockResolvedValue(ok({ supporting_requirements: [FACT] }));
    renderPanel();

    const link = await screen.findByTestId('sufficiency-source-verified');
    expect(link).toHaveTextContent(/verified source/i);
    expect(link).toHaveAttribute('href', FACT.source_url);
    expect(screen.queryByTestId('sufficiency-source-unverified')).not.toBeInTheDocument();
  });

  it('says plainly that an unchecked citation was not independently verified', async () => {
    mockGetSufficiency.mockResolvedValue(ok({ supporting_requirements: [UNVERIFIED_FACT] }));
    renderPanel();

    const link = await screen.findByTestId('sufficiency-source-unverified');
    expect(link).toHaveTextContent(/not independently verified/i);
    expect(link).toHaveAttribute('href', UNVERIFIED_FACT.source_url);
    expect(screen.queryByTestId('sufficiency-source-verified')).not.toBeInTheDocument();
  });

  it('never renders the two states identically', async () => {
    mockGetSufficiency.mockResolvedValue(
      ok({ supporting_requirements: [FACT, UNVERIFIED_FACT] }),
    );
    renderPanel();

    await screen.findByText(FACT.fact_text);
    const verified = screen.getByTestId('sufficiency-source-verified').textContent ?? '';
    const unverified = screen.getByTestId('sufficiency-source-unverified').textContent ?? '';
    expect(verified).not.toEqual(unverified);
    // The weaker claim must not contain the stronger word standing on its own.
    expect(unverified).toMatch(/not independently verified/i);
  });

  it('a fact with no citation_status is never claimed as verified', async () => {
    // Absent evidence is not evidence: an older payload, or a row predating the evidence
    // ledger, must fall to the weaker treatment rather than borrow the stronger one.
    const { citation_status: _drop, ...bare } = FACT;
    mockGetSufficiency.mockResolvedValue(ok({ supporting_requirements: [bare] }));
    renderPanel();

    expect(await screen.findByTestId('sufficiency-source-unverified')).toBeInTheDocument();
    expect(screen.queryByTestId('sufficiency-source-verified')).not.toBeInTheDocument();
  });

  it('still serves every fact — the label changes, the list does not', async () => {
    mockGetSufficiency.mockResolvedValue(
      ok({ supporting_requirements: [FACT, UNVERIFIED_FACT] }),
    );
    renderPanel();

    await screen.findByText(FACT.fact_text);
    expect(screen.getAllByTestId('sufficiency-fact')).toHaveLength(2);
    expect(screen.getByText(UNVERIFIED_FACT.fact_text)).toBeInTheDocument();
  });
});

describe('the two claims stay separate', () => {
  it('labels gaps as OUR intake, never as an authority requirement', async () => {
    mockGetSufficiency.mockResolvedValue(
      ok({ supporting_requirements: [FACT], missing_fields: ['employer_country'] }),
    );
    renderPanel();

    const gaps = await screen.findByTestId('sufficiency-gaps');
    expect(gaps).toHaveTextContent(/not requirements from the authorities/i);
    // Human label, not the raw snake_case key.
    expect(gaps).toHaveTextContent('Country your employer is in');
    expect(gaps).not.toHaveTextContent('employer_country');
  });

  it('suppresses fields the profile can never satisfy', async () => {
    // passport_expiry_date is not a profile-snapshot key, so it sits in missing_fields
    // forever. Rows written before AIQ-1821 still carry it. Showing it would be a
    // to-do the employee can never complete.
    mockGetSufficiency.mockResolvedValue(
      ok({ missing_fields: ['passport_expiry_date', 'nationality'] }),
    );
    renderPanel();

    const gaps = await screen.findByTestId('sufficiency-gaps');
    expect(gaps).toHaveTextContent('Your nationality');
    expect(gaps).not.toHaveTextContent(/passport/i);
  });

  it('renders no gaps block when the only gap was suppressed', async () => {
    mockGetSufficiency.mockResolvedValue(ok({ missing_fields: ['passport_expiry_date'] }));
    renderPanel();
    await screen.findByTestId('sufficiency-empty');
    expect(screen.queryByTestId('sufficiency-gaps')).not.toBeInTheDocument();
  });
});

describe('states that must never read as "complete"', () => {
  it('empty result says we hold no data, not that nothing is required', async () => {
    mockGetSufficiency.mockResolvedValue(ok());
    renderPanel();

    const empty = await screen.findByTestId('sufficiency-empty');
    expect(empty).toHaveTextContent(/we don’t yet hold reviewed requirements/i);
    expect(empty).toHaveTextContent(/not.*that nothing is required of you/i);
  });

  it('distinguishes "no destination set" from "no data for this destination"', async () => {
    mockGetSufficiency.mockResolvedValue(ok({ destination_country: null }));
    renderPanel();

    expect(await screen.findByTestId('sufficiency-no-destination')).toHaveTextContent(
      /destination isn’t set/i,
    );
    expect(screen.queryByTestId('sufficiency-empty')).not.toBeInTheDocument();
  });

  it.each(['insufficient_data', 'unavailable'])(
    'surfaces compute_status=%s as degraded even though HTTP was 200',
    async (status) => {
      mockGetSufficiency.mockResolvedValue(
        ok({ compute_status: status, message: 'More case information is needed.' }),
      );
      renderPanel();

      const degraded = await screen.findByTestId('sufficiency-degraded');
      expect(degraded).toHaveTextContent(/more case information is needed/i);
      expect(degraded).toHaveTextContent(/does not mean nothing is required of you/i);
      expect(screen.queryByTestId('sufficiency-empty')).not.toBeInTheDocument();
    },
  );

  it('a network failure offers a retry and refetches', async () => {
    mockGetSufficiency.mockRejectedValueOnce(new Error('boom'));
    renderPanel();

    const err = await screen.findByTestId('sufficiency-error');
    expect(err).toHaveTextContent(/problem on our side/i);
    expect(err).toHaveTextContent(/does not mean nothing is required of you/i);

    mockGetSufficiency.mockResolvedValueOnce(ok({ supporting_requirements: [FACT] }));
    await userEvent.click(screen.getByRole('button', { name: /retry/i }));
    await waitFor(() => expect(screen.getByText(FACT.fact_text)).toBeInTheDocument());
  });

  it.each([
    [403, /don’t have access/i],
    [404, /couldn’t find this case/i],
  ])('distinguishes HTTP %s from a generic failure', async (status, copy) => {
    mockGetSufficiency.mockRejectedValue({ response: { status } });
    renderPanel();
    expect(await screen.findByTestId('sufficiency-error')).toHaveTextContent(copy);
  });

  it('no state ever claims completeness', async () => {
    const states = [
      ok(),
      ok({ destination_country: null }),
      ok({ compute_status: 'unavailable', message: 'x' }),
      ok({ supporting_requirements: [FACT] }),
    ];
    for (const payload of states) {
      mockGetSufficiency.mockReset();
      mockGetSufficiency.mockResolvedValue(payload);
      const { container, unmount } = renderPanel();
      await waitFor(() =>
        expect(container.querySelector('[aria-busy="true"]')).not.toBeInTheDocument(),
      );
      const text = container.textContent ?? '';
      expect(text).not.toMatch(COMPLETENESS_CLAIMS);
      expectPhraseIsNegated(text);
      unmount();
    }
  });
});
