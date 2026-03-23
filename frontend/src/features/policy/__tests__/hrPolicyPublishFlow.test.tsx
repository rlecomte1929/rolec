import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { mockPolicyReviewPayload, mockPolicyState } from './hrPolicyTestUtils';
import { PublishPreflightModal } from '../PublishPreflightModal';
import { HrPolicyReviewWorkspace } from '../HrPolicyReviewWorkspace';

/** Avoid importing real `client.ts` (pulls Supabase) — stub only what `HrPolicyReviewWorkspace` needs. */
const policyClientMocks = vi.hoisted(() => ({
  list: vi.fn(),
  getNormalized: vi.fn(),
  publishLatestVersion: vi.fn(),
  getDownloadUrl: vi.fn(),
  patchBenefitRule: vi.fn(),
  patchLatestVersionStatus: vi.fn(),
  initializeFromTemplate: vi.fn(),
  hrPolicyReviewGet: vi.fn(),
  policyDocumentsList: vi.fn(),
  getClause: vi.fn(),
  normalize: vi.fn(),
  patchHrBenefitOverride: vi.fn(),
  deleteHrBenefitOverride: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  companyPolicyAPI: {
    list: (...args: unknown[]) => policyClientMocks.list(...args),
    getNormalized: (...args: unknown[]) => policyClientMocks.getNormalized(...args),
    publishLatestVersion: (...args: unknown[]) => policyClientMocks.publishLatestVersion(...args),
    getDownloadUrl: (...args: unknown[]) => policyClientMocks.getDownloadUrl(...args),
    patchBenefitRule: (...args: unknown[]) => policyClientMocks.patchBenefitRule(...args),
    patchLatestVersionStatus: (...args: unknown[]) => policyClientMocks.patchLatestVersionStatus(...args),
    initializeFromTemplate: (...args: unknown[]) => policyClientMocks.initializeFromTemplate(...args),
    patchHrBenefitOverride: (...args: unknown[]) => policyClientMocks.patchHrBenefitOverride(...args),
    deleteHrBenefitOverride: (...args: unknown[]) => policyClientMocks.deleteHrBenefitOverride(...args),
  },
  hrPolicyReviewAPI: {
    get: (...args: unknown[]) => policyClientMocks.hrPolicyReviewGet(...args),
  },
  policyDocumentsAPI: {
    list: (...args: unknown[]) => policyClientMocks.policyDocumentsList(...args),
    getClause: (...args: unknown[]) => policyClientMocks.getClause(...args),
    normalize: (...args: unknown[]) => policyClientMocks.normalize(...args),
  },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('PublishPreflightModal', () => {
  it('shows current policy, draft, comparison readiness, and continuity message', () => {
    render(
      <PublishPreflightModal
        open
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        publishBusy={false}
        dataLoading={false}
        activeSummary="Published company policy from an uploaded document."
        activeVersionLabel="1"
        activeComparison="full"
        draftSummary="Working version from your uploaded document."
        draftVersionLabel="2"
        comparisonAfterPublish="partial"
        willReplaceActive
      />
    );
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(
      screen.getByText(/Employees continue seeing the current published policy until this publish action completes/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Published company policy from an uploaded document/i)).toBeInTheDocument();
    expect(screen.getByText(/Working version from your uploaded document/i)).toBeInTheDocument();
    expect(screen.getByText(/Cost comparison today/i)).toBeInTheDocument();
    expect(screen.getByText(/Cost comparison after publish/i)).toBeInTheDocument();
  });

  it('disables confirm while data is still loading', () => {
    render(
      <PublishPreflightModal
        open
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        publishBusy={false}
        dataLoading
        activeSummary="A"
        activeVersionLabel={null}
        activeComparison="informational"
        draftSummary="D"
        draftVersionLabel={null}
        comparisonAfterPublish="informational"
        willReplaceActive={false}
      />
    );
    expect(screen.getByRole('button', { name: 'Confirm publish' })).toBeDisabled();
  });

  it('disables confirm and shows publishing label while publishBusy', () => {
    render(
      <PublishPreflightModal
        open
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        publishBusy
        dataLoading={false}
        activeSummary="A"
        activeVersionLabel={null}
        activeComparison="informational"
        draftSummary="D"
        draftVersionLabel={null}
        comparisonAfterPublish="informational"
        willReplaceActive={false}
      />
    );
    expect(screen.getByRole('button', { name: /publishing/i })).toBeDisabled();
  });
});

describe('HrPolicyReviewWorkspace publish integration (mocked API)', () => {
  beforeEach(() => {
    policyClientMocks.list.mockResolvedValue({ policies: [{ id: 'cp-test-1', title: 'Test policy' }] });
    policyClientMocks.policyDocumentsList.mockResolvedValue({ documents: [] });
    policyClientMocks.getDownloadUrl.mockResolvedValue({ ok: false });
    policyClientMocks.hrPolicyReviewGet.mockResolvedValue(mockPolicyReviewPayload());
    policyClientMocks.getClause.mockResolvedValue({ clause: null });
    policyClientMocks.normalize.mockResolvedValue({});
    policyClientMocks.patchBenefitRule.mockResolvedValue({});
    policyClientMocks.patchLatestVersionStatus.mockResolvedValue({});
    policyClientMocks.initializeFromTemplate.mockResolvedValue({});
    policyClientMocks.patchHrBenefitOverride.mockResolvedValue({});
    policyClientMocks.deleteHrBenefitOverride.mockResolvedValue({});
  });

  it('opens preflight from publish control, confirm calls publish once and refreshes normalized to published shape', async () => {
    const normReady = mockPolicyState('ready_to_publish').normalized!;
    const normPublished = mockPolicyState('published').normalized!;
    let live = false;
    policyClientMocks.getNormalized.mockImplementation(async () => (live ? normPublished : normReady));
    policyClientMocks.publishLatestVersion.mockImplementation(async () => {
      live = true;
      return {};
    });

    render(<HrPolicyReviewWorkspace refreshTrigger={0} />);

    // Primary at-a-glance CTA for ready_to_publish; retry click + modal in one waitFor to absorb load/review races.
    await waitFor(() => {
      const primary = screen.getByRole('button', { name: /^publish policy$/i });
      expect(primary).not.toBeDisabled();
      fireEvent.click(primary);
      expect(screen.getByTestId('publish-preflight-modal')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /confirm publish/i }));

    await waitFor(() => expect(policyClientMocks.publishLatestVersion).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(policyClientMocks.publishLatestVersion).toHaveBeenCalledWith('cp-test-1'));
    expect(policyClientMocks.getNormalized.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it('after replacing a draft, workspace shows live state without replacement warning', async () => {
    const beforeNorm = mockPolicyState('published_replacement_draft').normalized!;
    const afterNorm = mockPolicyState('published').normalized!;
    let live = false;
    policyClientMocks.getNormalized.mockImplementation(async () => (live ? afterNorm : beforeNorm));
    policyClientMocks.publishLatestVersion.mockImplementation(async () => {
      live = true;
      return {};
    });

    render(<HrPolicyReviewWorkspace refreshTrigger={0} />);

    await waitFor(() => expect(screen.getByTestId('hr-policy-replacement-warning')).toBeInTheDocument());
    await waitFor(() => {
      const b = screen.getByRole('button', { name: /^publish version$/i });
      expect(b).not.toBeDisabled();
      fireEvent.click(b);
      expect(screen.getByTestId('publish-preflight-modal')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /confirm publish/i }));

    await waitFor(() => expect(screen.queryByTestId('hr-policy-replacement-warning')).not.toBeInTheDocument());
  });

  it('does not call publish when review payload is missing (publish stays disabled until data ready)', async () => {
    policyClientMocks.getNormalized.mockResolvedValue(mockPolicyState('ready_to_publish').normalized);
    policyClientMocks.hrPolicyReviewGet.mockImplementation(() => new Promise(() => {}));

    render(<HrPolicyReviewWorkspace refreshTrigger={0} />);

    await waitFor(() => expect(screen.getByRole('button', { name: /publish policy/i })).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /publish policy/i })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /publish policy/i }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(policyClientMocks.publishLatestVersion).not.toHaveBeenCalled();
  });
});
