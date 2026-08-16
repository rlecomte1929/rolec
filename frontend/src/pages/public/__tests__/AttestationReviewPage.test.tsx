/**
 * `/attest/:token` — the public counsel reviewer view.
 *
 * The behaviours worth pinning are the ones a careless edit would quietly break: the
 * sign button staying disabled until every gate is satisfied, and a bad token showing a
 * message that reveals nothing about WHY it failed.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as api from '../../../api/attestation';
import { AttestationReviewPage } from '../AttestationReviewPage';

vi.mock('../../../api/attestation');

const view = (overrides: Partial<api.AttestationPublicView> = {}): api.AttestationPublicView => ({
  corridor_label: 'NORWAY',
  purpose: 'employment',
  scope: 'legal',
  status: 'sent',
  title: 'Norway — legal compliance attestation',
  disclaimer_version: 'v1',
  disclaimer_text: 'By signing, I confirm that I am a qualified legal professional…',
  content_hash: 'a'.repeat(64),
  expires_at: '2026-12-01T00:00:00Z',
  signed_at: null,
  items: [
    {
      id: 'item-1', title: 'Tax deduction card (skattekort)',
      claim: 'Obtain a skattekort before first salary.',
      source_url: 'https://www.skatteetaten.no/en/example',
      evidence: 'quote', pillar: 'EMPLOYMENT', validity: 'Before first salary',
      confidence: 'verified', decision: 'pending',
      reviewer_comment: null, proposed_amendment: null,
    },
  ],
  ...overrides,
});

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/attest/tok_abcdefghijklmnopqrstuvwxyz012345']}>
      <Routes>
        <Route path="/attest/:token" element={<AttestationReviewPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe('AttestationReviewPage', () => {
  beforeEach(() => vi.resetAllMocks());

  it('renders the checklist with claim, source and timing', async () => {
    vi.mocked(api.fetchAttestationByToken).mockResolvedValue(view());
    renderPage();

    expect(await screen.findByText('Tax deduction card (skattekort)')).toBeInTheDocument();
    expect(screen.getByText('Obtain a skattekort before first salary.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /skatteetaten\.no/ })).toHaveAttribute(
      'href', 'https://www.skatteetaten.no/en/example',
    );
    expect(screen.getByText(/Before first salary/)).toBeInTheDocument();
  });

  it('shows one uninformative message for a bad token', async () => {
    // The backend returns an identical 404 for unknown / expired / not-yet-sent so the
    // page cannot be used to probe which tokens exist. The UI must not undo that by
    // distinguishing the cases in its copy.
    vi.mocked(api.fetchAttestationByToken).mockRejectedValue(new Error('404'));
    renderPage();

    expect(await screen.findByText('Attestation unavailable')).toBeInTheDocument();
    const body = document.body.textContent || '';
    expect(body).toContain('not valid, or it has expired');
    expect(body).not.toMatch(/expired on|already signed|revoked|not yet sent|draft/i);
  });

  it('keeps Sign disabled until every item is decided', async () => {
    vi.mocked(api.fetchAttestationByToken).mockResolvedValue(view());
    renderPage();

    await screen.findByText('Tax deduction card (skattekort)');
    expect(screen.getByRole('button', { name: /Sign & attest/i })).toBeDisabled();
    expect(screen.getByText(/must be approved, amended or rejected/i)).toBeInTheDocument();
  });

  it('still keeps Sign disabled when decided but the disclaimer is unchecked', async () => {
    const decided = view({ items: [{ ...view().items[0], decision: 'approved' }] });
    vi.mocked(api.fetchAttestationByToken).mockResolvedValue(decided);
    renderPage();

    await screen.findByText('Tax deduction card (skattekort)');
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Full name/i), 'Kari Nordmann');
    await user.type(screen.getByLabelText(/^Email/i), 'kari@example.no');

    // Everything supplied except the attestation checkbox.
    expect(screen.getByRole('button', { name: /Sign & attest/i })).toBeDisabled();

    await user.click(screen.getByRole('checkbox'));
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Sign & attest/i })).toBeEnabled(),
    );
  });

  it('sends the content hash it was shown, so a stale checklist is rejected server-side', async () => {
    const decided = view({ items: [{ ...view().items[0], decision: 'approved' }] });
    vi.mocked(api.fetchAttestationByToken).mockResolvedValue(decided);
    vi.mocked(api.signAttestation).mockResolvedValue({ ...decided, status: 'signed', signed_at: '2026-08-16T10:00:00Z' });
    renderPage();

    await screen.findByText('Tax deduction card (skattekort)');
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Full name/i), 'Kari Nordmann');
    await user.type(screen.getByLabelText(/^Email/i), 'kari@example.no');
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: /Sign & attest/i }));

    await waitFor(() => expect(api.signAttestation).toHaveBeenCalled());
    const [, body] = vi.mocked(api.signAttestation).mock.calls[0];
    expect(body.content_hash).toBe('a'.repeat(64));
    expect(body.agreed_to_disclaimer).toBe(true);
  });

  it('shows the immutability confirmation once signed and hides the sign panel', async () => {
    vi.mocked(api.fetchAttestationByToken).mockResolvedValue(
      view({ status: 'signed', signed_at: '2026-08-16T10:00:00Z',
             items: [{ ...view().items[0], decision: 'approved' }] }),
    );
    renderPage();

    expect(await screen.findByText('Attestation recorded')).toBeInTheDocument();
    expect(screen.getByText(/immutable/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Sign & attest/i })).not.toBeInTheDocument();
  });
});
