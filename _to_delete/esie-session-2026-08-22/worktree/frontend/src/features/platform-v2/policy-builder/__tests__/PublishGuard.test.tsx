/**
 * AIQ-1642: publishing a policy is slow (~20–40s), so a first-time HR user concluded it
 * had failed and clicked Publish again — the second call 409'd server-side (the F7
 * double-publish). handlePublish now rejects a re-click while one publish is in flight
 * CLIENT-SIDE (a synchronous ref guard), and shows honest "can take up to a minute" copy.
 * This pins that a second click while one is in flight never reaches the server.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// The page module transitively constructs the Supabase client at import time.
vi.mock('../../../../api/supabase', () => ({
  supabase: {
    auth: {
      getSession: () => Promise.resolve({ data: { session: null } }),
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
    },
    from: () => ({ select: () => ({}) }),
  },
}));

const mocks = vi.hoisted(() => ({
  hrGet: vi.fn(),
  hrPostDraft: vi.fn(),
  hrPutDraft: vi.fn(),
  hrPublish: vi.fn(),
}));

vi.mock('../../../../api/client', () => ({
  policyConfigMatrixAPI: {
    hrGet: mocks.hrGet,
    hrPostDraft: mocks.hrPostDraft,
    hrPutDraft: mocks.hrPutDraft,
    hrPublish: mocks.hrPublish,
    hrImportExtraction: vi.fn(),
  },
  policyDocumentsAPI: { upload: vi.fn(), get: vi.fn() },
}));

// Keep the render lean + deterministic: the assistant shell just renders the builder;
// the pure converters yield exactly one tier + a non-empty draft so Publish is reachable.
vi.mock('../../../../features/policy/PolicyAssistantDockedShell', () => ({
  PolicyAssistantDockedShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock('../../../../perf/hrOnboardingInstrumentation', () => ({ trackPolicyPublished: vi.fn() }));
vi.mock('../configDraftToCanvasPolicy', () => ({
  configDraftToCanvasPolicy: () => ({
    tiers: [
      { name: 'Standard', mode: 'caps', lump: 0, targeting: { level: [], type: [], family: [] }, benefits: {} },
    ],
    warnings: [],
    rowCount: 1,
  }),
}));
vi.mock('../canvasPolicyToConfigDraft', () => ({
  canvasPolicyToConfigDraft: () => ({ body: { policy_version: 'pv-1', rows: [] }, rowCount: 1 }),
}));

import { HrPolicyBuilderV2Page } from '../HrPolicyBuilderV2Page';

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <HrPolicyBuilderV2Page embedded />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('HrPolicyBuilderV2Page — publish double-click guard (AIQ-1642)', () => {
  it('rejects a second publish while one is in flight — client-side, never a server 409', async () => {
    // No policy_version on load → ensureDraftId() calls hrPostDraft, which we PARK so the
    // first publish is genuinely in flight when the second click lands.
    mocks.hrGet.mockResolvedValue({ status: 'draft', policy_version: null, categories: {} });
    mocks.hrPutDraft.mockResolvedValue({});
    mocks.hrPublish.mockResolvedValue({});
    let releasePost!: (v: unknown) => void;
    mocks.hrPostDraft.mockReturnValue(new Promise((res) => { releasePost = res; }));

    renderPage();

    // Wait for the mount hydration to load the tier so Publish is enabled.
    const publishBtn = await screen.findByRole('button', { name: /^publish$/i });
    await waitFor(() => expect(publishBtn).not.toBeDisabled());

    fireEvent.click(publishBtn); // first publish → parks at hrPostDraft
    fireEvent.click(publishBtn); // second click → must be a client-side no-op

    // Honest progress copy is shown so the user waits instead of re-clicking.
    expect(screen.getByText(/this can take up to a minute/i)).toBeInTheDocument();
    // Only ONE draft-create fired despite two clicks — the second was rejected client-side.
    await waitFor(() => expect(mocks.hrPostDraft).toHaveBeenCalledTimes(1));

    // Let the first publish finish; the guard must have kept it to a single publish call.
    releasePost({ policy_version: 'pv-1' });
    await waitFor(() => expect(mocks.hrPublish).toHaveBeenCalledTimes(1));
    expect(mocks.hrPostDraft).toHaveBeenCalledTimes(1);
  });
});
