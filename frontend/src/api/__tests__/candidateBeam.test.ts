/**
 * Candidate beam API client — the two calls the import panel depends on.
 *
 * Both tests exist because the safe thing on the server is the dangerous thing on the
 * client, and neither failure mode is visible in the UI:
 *
 *  - `ImportRequest.dry_run` defaults TRUE, so an execute that omits it previews, writes
 *    nothing, and returns a success shape.
 *  - `import-verify` answers 409 WITH the drift report, so letting the rejection propagate
 *    turns "we found drift" into "the request failed".
 *
 * The page tests mock this module, so neither property is observable there. It has to be
 * pinned here or not at all.
 */
import { describe, expect, it, vi, beforeEach, type Mock } from 'vitest';

vi.mock('../client', () => ({ default: { get: vi.fn(), post: vi.fn() } }));

import api from '../client';
import { candidateBeamAPI } from '../candidateBeam';

const post = (api as unknown as { post: Mock }).post;
const get = (api as unknown as { get: Mock }).get;

beforeEach(() => {
  post.mockReset();
  get.mockReset();
});

describe('executeImport', () => {
  it('sends dry_run false explicitly, or the server previews and reports success', async () => {
    post.mockResolvedValue({ data: { run_id: 'r1', imported: 3, skipped: [], written: true } });

    await candidateBeamAPI.executeImport('r1', 'FRANCE');

    const [url, body] = post.mock.calls[0];
    expect(url).toBe('/api/admin/candidate-beam/runs/r1/import');
    expect(body).toMatchObject({ country: 'FRANCE', dry_run: false });
  });

  it('sends no approved_ids — approval is server-side state, not a client selection', async () => {
    post.mockResolvedValue({ data: { run_id: 'r1', imported: 0, skipped: [], written: true } });

    await candidateBeamAPI.executeImport('r1', 'FRANCE');

    expect(post.mock.calls[0][1]).not.toHaveProperty('approved_ids');
  });

  it('encodes the run id rather than interpolating it raw', async () => {
    post.mockResolvedValue({ data: { run_id: 'a/b', imported: 0, skipped: [], written: true } });

    await candidateBeamAPI.executeImport('a/b', 'FRANCE');

    expect(post.mock.calls[0][0]).toBe('/api/admin/candidate-beam/runs/a%2Fb/import');
  });
});

describe('verifyImport', () => {
  it('returns the report on a clean 200', async () => {
    const report = { run_id: 'r1', ok: true, verified: 2, failed: 0, items: [] };
    get.mockResolvedValue({ data: report });

    await expect(candidateBeamAPI.verifyImport('r1')).resolves.toEqual(report);
  });

  it('returns the drift report carried by a 409 instead of throwing it away', async () => {
    const report = {
      run_id: 'r1',
      ok: false,
      verified: 1,
      failed: 1,
      items: [{ candidate_uid: 'b', title: 'Drifted', status: 'content_drift' as const }],
    };
    get.mockRejectedValue({ response: { status: 409, data: report } });

    await expect(candidateBeamAPI.verifyImport('r1')).resolves.toEqual(report);
  });

  it('still throws a real failure — a 500 is not a finding', async () => {
    get.mockRejectedValue({ response: { status: 500 } });

    await expect(candidateBeamAPI.verifyImport('r1')).rejects.toBeDefined();
  });
});
