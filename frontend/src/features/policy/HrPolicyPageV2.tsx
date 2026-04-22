/**
 * New HR Policy page (PR #1: layout skeleton).
 *
 * Replaces the prior HrPolicy.tsx HR branch with a 5-section progressive-
 * disclosure layout that product approved:
 *
 *   1. Status strip (sticky)        — current state at a glance
 *   2. What employees see today     — topic summary (reuses admin matrix
 *                                     PolicyThemeAccordionList read-only)
 *   3. Build your next version      — two doors: import a document, or
 *                                     start from a template (template CTA
 *                                     deferred to Phase 3)
 *   4. Draft vs Live                — stubbed; diff view lands in a
 *                                     follow-up per product decision
 *   5. Version history              — published/archived audit trail
 *
 * Plus a floating Policy Assistant button (bottom-right) and a collapsed
 * "Detailed review" drawer that keeps the legacy HrPolicyReviewWorkspace
 * accessible for power users without cluttering the default view.
 *
 * Retired sections (per product direction, PDF feedback 2026-04-22):
 *   - "Extracted policy signals"  (noise; moved into doc-level drawer only)
 *   - "Rules on this version"     (long auto-extracted list; replaced by
 *                                  "What to fix before going live" panel
 *                                  that surfaces only actionable items)
 *   - "HR adjustments / effective policy" (hidden behind Detailed review)
 *   - "Policy inversion block"    (superseded by Draft vs Live)
 *   - "Exclusions & evidence" separate section (exclusions now live on
 *                                  the benefit row itself)
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Alert, Badge, Button, Card } from '../../components/antigravity';
import {
  policyConfigMatrixAPI,
  policyDocumentsAPI,
} from '../../api/client';
import type { PolicyConfigWorkingPayload } from '../policy-config/types';
import { HrPolicyReviewWorkspace } from './HrPolicyReviewWorkspace';
import { HrPolicyAssistantPanel } from './HrPolicyAssistantPanel';
import { PolicyAssistantFab } from './PolicyAssistantFab';
import { PolicyDiffView } from './PolicyDiffView';
import { PolicyTopicSummaryList } from './PolicyTopicSummaryList';

// --- Types ------------------------------------------------------------------

type NormalizedPolicy = {
  version?: {
    id?: string;
    version_number?: number;
    status?: string;
    effective_date?: string;
    source_policy_document_id?: string | null;
    policy_id?: string;
  } | null;
  policy?: {
    id?: string;
    title?: string;
    company_id?: string | null;
  } | null;
  benefit_rules?: unknown[];
};

type PolicyDocumentListItem = {
  id: string;
  filename: string;
  processing_status?: string;
  detected_document_type?: string;
  uploaded_at?: string;
};

type HrPolicyPageV2Props = {
  adminCompanyId?: string | null;
};

// --- Status strip -----------------------------------------------------------

type StatusStripProps = {
  normalized: NormalizedPolicy | null;
  matrixPayload: PolicyConfigWorkingPayload | null;
  hasDocument: boolean;
  onPreviewEmployeeView: () => void;
  onPublish: () => void;
  publishEnabled: boolean;
  publishBusy: boolean;
};

const StatusStrip: React.FC<StatusStripProps> = ({
  normalized,
  matrixPayload,
  hasDocument,
  onPreviewEmployeeView,
  onPublish,
  publishEnabled,
  publishBusy,
}) => {
  const canonicalVersion = normalized?.version;
  const canonicalStatus = String(canonicalVersion?.status || '').toLowerCase();
  const canonicalLive = canonicalStatus === 'published';
  const matrixLive = Boolean(
    matrixPayload?.status === 'published' || matrixPayload?.policy_version
  );
  const matrixSource =
    matrixPayload?.source === 'published' || matrixPayload?.source === 'published_clone';

  // "Live" headline follows the surface employees actually see. The matrix
  // bridge takes over when no canonical version exists.
  const liveLabel = canonicalLive
    ? `Live v${canonicalVersion?.version_number ?? '?'}`
    : matrixLive
    ? `Matrix v${matrixPayload?.version_number ?? '?'}`
    : 'No live policy yet';
  const liveVariant: 'success' | 'warning' | 'neutral' =
    canonicalLive || matrixLive ? 'success' : 'warning';

  const draftDelta =
    canonicalStatus === 'draft' || canonicalStatus === 'review_required'
      ? 'draft in progress'
      : matrixPayload?.editable && !matrixSource
      ? 'matrix draft in progress'
      : 'no pending changes';

  const publishedAt = canonicalVersion?.effective_date
    ? `Published ${String(canonicalVersion.effective_date).slice(0, 10)}`
    : matrixPayload?.effective_date
    ? `Matrix effective ${String(matrixPayload.effective_date).slice(0, 10)}`
    : 'Never published';

  const sourceLabel = (() => {
    if (hasDocument && matrixLive) return 'Source: Document + Matrix';
    if (hasDocument) return 'Source: Uploaded document';
    if (matrixLive) return 'Source: Compensation matrix';
    return 'Source: None yet';
  })();

  return (
    <div
      className="sticky top-0 z-30 -mx-6 px-6 py-3 bg-white/95 backdrop-blur border-b border-slate-200"
      data-testid="hr-policy-status-strip"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={liveVariant} size="sm">
          {liveLabel}
        </Badge>
        <Badge variant="neutral" size="sm">{draftDelta}</Badge>
        <Badge variant="neutral" size="sm">{publishedAt}</Badge>
        <Badge variant="neutral" size="sm">{sourceLabel}</Badge>
        <div className="ml-auto flex gap-2">
          <Button size="sm" variant="outline" onClick={onPreviewEmployeeView}>
            Preview employee view
          </Button>
          <Button
            size="sm"
            onClick={onPublish}
            disabled={!publishEnabled || publishBusy}
          >
            {publishBusy ? 'Publishing…' : 'Publish draft'}
          </Button>
        </div>
      </div>
    </div>
  );
};

// --- Topic summary ----------------------------------------------------------
// Per-theme summary + read-only drill-down now lives in
// PolicyTopicSummaryList (PR #2). We wrap it in a Card here so Section 2
// keeps the same visual frame as the rest of the page.

const TopicSummarySection: React.FC<{
  matrixPayload: PolicyConfigWorkingPayload | null;
  onRequestDetails: () => void;
}> = ({ matrixPayload, onRequestDetails }) => (
  <Card padding="lg">
    <PolicyTopicSummaryList
      matrixPayload={matrixPayload}
      onRequestDetails={onRequestDetails}
    />
  </Card>
);

// --- Build next version -----------------------------------------------------

const BuildNextVersionSection: React.FC<{
  documents: PolicyDocumentListItem[];
  hasLivePolicy: boolean;
  onImportClick: () => void;
  adminCompanyId?: string | null;
}> = ({ documents, hasLivePolicy, onImportClick, adminCompanyId: _adminCompanyId }) => {
  const [docsOpen, setDocsOpen] = useState(false);
  return (
    <Card padding="lg">
      <h2 className="text-lg font-semibold text-[#0b2b43]">Build your next version</h2>
      <p className="text-sm text-slate-600 mt-1.5">
        Two ways in. Either upload an approved company policy and let ReloPass extract
        benefit rules from it, or start from a template and edit the values yourself.
      </p>
      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        <button
          type="button"
          onClick={onImportClick}
          className="text-left p-4 rounded-lg border border-slate-200 hover:border-[#0b2b43] hover:bg-slate-50 transition"
        >
          <div className="text-2xl" aria-hidden>📄</div>
          <div className="font-semibold text-[#0b2b43] mt-2">Import a document</div>
          <p className="text-sm text-slate-600 mt-1">
            Upload a PDF or DOCX. ReloPass classifies it, extracts caps and rules, and
            turns it into a draft you can review and publish.
          </p>
          <div className="mt-3 text-xs font-medium text-[#0b2b43]">
            Best when you already have an approved company policy document. →
          </div>
        </button>
        <div className="text-left p-4 rounded-lg border border-dashed border-slate-300 bg-slate-50/50">
          <div className="text-2xl" aria-hidden>✨</div>
          <div className="font-semibold text-slate-700 mt-2">Start from a template</div>
          <p className="text-sm text-slate-600 mt-1">
            Pick Conservative, Standard, or Premium. ReloPass pre-fills the compensation
            matrix with level-tiered caps (C-suite/VP/Director/Manager/Entry).
          </p>
          <div className="mt-3 text-xs font-medium text-slate-500">
            Coming in Phase 3. For now, import a document or edit the matrix directly in
            the admin Policy Workspace.
          </div>
        </div>
      </div>
      {hasLivePolicy && (
        <div className="mt-4 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-sm text-amber-900">
          A version is currently live for employees. Importing a new document creates a
          draft — the live version stays in effect until you publish the replacement.
          Use <strong>Unpublish version</strong> in the detailed review if you want to
          take the current policy down before publishing a new one.
        </div>
      )}

      <div className="mt-5">
        <button
          type="button"
          onClick={() => setDocsOpen((v) => !v)}
          className="text-sm font-medium text-[#0b2b43] hover:underline"
        >
          {docsOpen ? '▾' : '▸'} Uploaded documents ({documents.length})
        </button>
        {docsOpen && (
          <div className="mt-3 border border-slate-200 rounded-lg">
            {documents.length === 0 ? (
              <p className="text-sm text-slate-600 px-3 py-3">
                No documents uploaded yet.
              </p>
            ) : (
              <ul className="divide-y divide-slate-200">
                {documents.map((d) => (
                  <li key={d.id} className="px-3 py-2 text-sm">
                    <div className="font-medium text-[#0b2b43]">{d.filename}</div>
                    <div className="text-xs text-slate-600 mt-0.5">
                      Status: {d.processing_status ?? '—'}
                      {d.detected_document_type ? ` · Type: ${d.detected_document_type}` : ''}
                      {d.uploaded_at ? ` · Uploaded: ${String(d.uploaded_at).slice(0, 10)}` : ''}
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <div className="px-3 py-2 text-xs text-slate-500 bg-slate-50 rounded-b-lg">
              Manage and delete uploaded documents in the Detailed review below.
            </div>
          </div>
        )}
      </div>
    </Card>
  );
};

// Draft vs Live section is now the real diff view — see PolicyDiffView.tsx.

// --- Version history --------------------------------------------------------

const VersionHistorySection: React.FC<{
  normalized: NormalizedPolicy | null;
}> = ({ normalized }) => {
  const rows: Array<{
    id: string;
    label: string;
    status: string;
    effective_date?: string;
  }> = [];
  if (normalized?.version) {
    rows.push({
      id: String(normalized.version.id ?? ''),
      label: `v${normalized.version.version_number ?? '?'}`,
      status: String(normalized.version.status ?? ''),
      effective_date: normalized.version.effective_date,
    });
  }
  const [open, setOpen] = useState(false);
  if (rows.length === 0) return null;
  return (
    <Card padding="lg">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center justify-between w-full"
      >
        <h2 className="text-lg font-semibold text-[#0b2b43]">
          Version history ({rows.length})
        </h2>
        <span className="text-slate-500">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <table className="mt-3 w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-slate-500">
              <th className="py-2 pr-2">Version</th>
              <th className="py-2 pr-2">Status</th>
              <th className="py-2 pr-2">Effective</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-slate-200">
                <td className="py-2 pr-2 font-medium text-[#0b2b43]">{r.label}</td>
                <td className="py-2 pr-2">
                  <Badge variant="neutral" size="sm">
                    {r.status}
                  </Badge>
                </td>
                <td className="py-2 pr-2 text-slate-600">
                  {r.effective_date ? String(r.effective_date).slice(0, 10) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
};

// --- Floating Policy Assistant FAB -----------------------------------------

/**
 * HR-flavored floating assistant. The shared PolicyAssistantFab owns the
 * button + sheet chrome; this wrapper only provides the HR assistant
 * panel as the sheet body. Kept inline here so page-scoped props
 * (policyId) stay local — a future employee equivalent will use the
 * same PolicyAssistantFab with EmployeePolicyAssistantPanel as body.
 */
const FloatingPolicyAssistantButton: React.FC<{
  policyId: string | null;
}> = ({ policyId }) => (
  <PolicyAssistantFab label="Open Policy Assistant — ask about this HR policy">
    {() => <HrPolicyAssistantPanel policyId={policyId} variant="card" />}
  </PolicyAssistantFab>
);

// --- Main page --------------------------------------------------------------

export const HrPolicyPageV2: React.FC<HrPolicyPageV2Props> = ({ adminCompanyId }) => {
  // `setNormalized` is intentionally kept unused in this PR: the canonical
  // version is loaded inside the Detailed review drawer only. A follow-up
  // can hoist it back up here once the diff view ships.
  const [normalized /* setNormalized */] = useState<NormalizedPolicy | null>(null);
  const [matrixPayload, setMatrixPayload] = useState<PolicyConfigWorkingPayload | null>(null);
  const [documents, setDocuments] = useState<PolicyDocumentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [detailedReviewOpen, setDetailedReviewOpen] = useState(false);
  const [postNormalizePolicyId, setPostNormalizePolicyId] = useState<string | null>(null);
  const [workspaceRefreshTrigger, setWorkspaceRefreshTrigger] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const params = adminCompanyId ? { company_id: adminCompanyId } : undefined;
      const [docsRes, matrixRes] = await Promise.all([
        policyDocumentsAPI.list(params).catch(() => ({ documents: [] as PolicyDocumentListItem[] })),
        policyConfigMatrixAPI.hrGet(adminCompanyId ?? undefined).catch(() => null),
      ]);
      setDocuments(Array.isArray(docsRes?.documents) ? (docsRes.documents as PolicyDocumentListItem[]) : []);
      setMatrixPayload((matrixRes as PolicyConfigWorkingPayload | null) ?? null);

      // Canonical (document-normalized) policy status is loaded lazily by
      // the Detailed review drawer when the user opens it. The top-level
      // status strip relies on the matrix payload for the "Live" signal,
      // which is the published surface employees actually resolve against
      // (canonical-only deployments still render via the HrPolicyReviewWorkspace
      // inside the drawer). Keeping the cold-path load minimal here avoids
      // two-version race conditions and a 404 on companies that have only
      // published through the matrix.
    } catch (err) {
      setLoadError('Unable to load your policy. Try again or contact support.');
    } finally {
      setLoading(false);
    }
  }, [adminCompanyId]);

  useEffect(() => {
    void load();
  }, [load, workspaceRefreshTrigger]);

  // Reserved for a follow-up wiring of the document-intake normalize flow
  // back into this page level. The Detailed review drawer still does the
  // right thing for now.
  void useCallback;

  const bump = useCallback(() => setWorkspaceRefreshTrigger((t) => t + 1), []);

  const hasLivePolicy =
    String(normalized?.version?.status || '').toLowerCase() === 'published' ||
    matrixPayload?.status === 'published';

  const publishEnabled = Boolean(normalized?.version?.id) && !hasLivePolicy;
  const [publishBusy, _setPublishBusy] = useState(false);

  const handleImportClick = () => {
    setDetailedReviewOpen(true);
    // Scroll to detailed review; the Document intake card lives at the top
    // of HrPolicyReviewWorkspace so the user lands on the upload controls.
    setTimeout(() => {
      const el = document.getElementById('hr-policy-detailed-review');
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 50);
  };

  const policyId = normalized?.version?.policy_id ?? normalized?.policy?.id ?? null;

  if (loading) {
    return (
      <Card padding="lg">
        <div className="text-sm text-slate-600">Loading your policy…</div>
      </Card>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {loadError && <Alert variant="error">{loadError}</Alert>}

      {/* 1. Status strip */}
      <StatusStrip
        normalized={normalized}
        matrixPayload={matrixPayload}
        hasDocument={documents.length > 0}
        onPreviewEmployeeView={() => {
          // Employee preview lives in the detailed review today; later it
          // becomes a dedicated modal. This keeps the CTA discoverable
          // while we ship the new modal in a follow-up.
          setDetailedReviewOpen(true);
        }}
        onPublish={() => {
          // Publish UX also lives in the detailed review today (PublishControls
          // card). Open the drawer and scroll to it.
          setDetailedReviewOpen(true);
        }}
        publishEnabled={publishEnabled}
        publishBusy={publishBusy}
      />

      {/* 2. What employees see today */}
      <TopicSummarySection
        matrixPayload={matrixPayload}
        onRequestDetails={() => setDetailedReviewOpen(true)}
      />

      {/* 3. Build your next version */}
      <BuildNextVersionSection
        documents={documents}
        hasLivePolicy={hasLivePolicy}
        onImportClick={handleImportClick}
        adminCompanyId={adminCompanyId}
      />

      {/* 4. Draft vs Live — live diff view (PR #4) */}
      <PolicyDiffView
        adminCompanyId={adminCompanyId ?? null}
        refreshTrigger={workspaceRefreshTrigger}
      />

      {/* 5. Version history */}
      <VersionHistorySection normalized={normalized} />

      {/* Detailed review (collapsed progressive disclosure) */}
      <div id="hr-policy-detailed-review">
        <Card padding="lg">
          <button
            type="button"
            onClick={() => setDetailedReviewOpen((v) => !v)}
            className="flex items-center justify-between w-full"
          >
            <div>
              <h2 className="text-lg font-semibold text-[#0b2b43]">Detailed review</h2>
              <p className="text-sm text-slate-600 mt-1 text-left">
                Document intake, per-rule adjustments, publish controls, unpublish.
                Hidden by default — open only when you need to dive in.
              </p>
            </div>
            <span className="text-slate-500 text-lg">{detailedReviewOpen ? '▾' : '▸'}</span>
          </button>
          {detailedReviewOpen && (
            <div className="mt-4 border-t border-slate-200 pt-4">
              <HrPolicyReviewWorkspace
                refreshTrigger={workspaceRefreshTrigger}
                postNormalizePolicyId={postNormalizePolicyId}
                onBindComplete={() => setPostNormalizePolicyId(null)}
                adminCompanyId={adminCompanyId ?? null}
              />
              <div className="mt-4 flex justify-end">
                <Link
                  to="#hr-policy-top"
                  className="text-xs text-slate-500 hover:text-[#0b2b43] underline"
                  onClick={(e) => {
                    e.preventDefault();
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                  }}
                >
                  Back to top
                </Link>
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* Keeps refresh bump wired so the Detailed review's internal actions
          (publish / unpublish / re-normalize) reload the top-level status. */}
      <div aria-hidden className="hidden">
        <button type="button" onClick={bump} />
      </div>

      {/* Floating Policy Assistant */}
      <FloatingPolicyAssistantButton policyId={policyId} />
    </div>
  );
};
