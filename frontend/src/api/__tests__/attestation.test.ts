/**
 * ATT-3.4 — createCaseAttestation wrapper.
 * Proves it POSTs the case attestation endpoint (not the corridor path) and
 * returns the minted reviewer link. apiPost is mocked; no network.
 */
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';

vi.mock('../client', () => ({ apiPost: vi.fn(), apiGet: vi.fn() }));

import { apiPost } from '../client';
import { createAttestation, createCaseAttestation } from '../attestation';

const apiPostMock = apiPost as unknown as Mock;

beforeEach(() => apiPostMock.mockReset());

describe('createCaseAttestation', () => {
  it('POSTs /api/admin/attestations/case with the case id and returns the created payload', async () => {
    const payload = {
      request: { id: 'att-1' },
      review_token: 'tok-once',
      review_url: 'https://relopass.com/review/tok-once',
      token_expires_at: null,
      warning: 'shown once',
    };
    apiPostMock.mockResolvedValue(payload);

    const res = await createCaseAttestation({ case_id: 'case-uuid' });

    expect(apiPostMock).toHaveBeenCalledTimes(1);
    expect(apiPostMock.mock.calls[0][0]).toBe('/api/admin/attestations/case');
    expect(apiPostMock.mock.calls[0][1]).toEqual({ case_id: 'case-uuid' });
    expect(res.review_url).toBe('https://relopass.com/review/tok-once');
    expect(res.review_token).toBe('tok-once');
  });

  it('forwards optional reviewer fields the corridor create path also accepts', async () => {
    apiPostMock.mockResolvedValue({ review_url: 'https://x', review_token: 't' });
    await createCaseAttestation({
      case_id: 'case-uuid',
      reviewer_org: 'Firm',
      reviewer_name: 'Ada',
      reviewer_email: 'ada@firm.example',
      reviewer_credential: 'Bar-1',
      ttl_days: 14,
    });
    expect(apiPostMock.mock.calls[0][1]).toEqual({
      case_id: 'case-uuid',
      reviewer_org: 'Firm',
      reviewer_name: 'Ada',
      reviewer_email: 'ada@firm.example',
      reviewer_credential: 'Bar-1',
      ttl_days: 14,
    });
  });

  it('does not reuse the corridor create path', async () => {
    apiPostMock.mockResolvedValue({});
    await createAttestation({ country_code: 'IE' });
    await createCaseAttestation({ case_id: 'case-uuid' });
    expect(apiPostMock.mock.calls[0][0]).toBe('/api/admin/attestations');
    expect(apiPostMock.mock.calls[1][0]).toBe('/api/admin/attestations/case');
  });
});
