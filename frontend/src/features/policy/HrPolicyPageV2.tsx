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
import { Alert, Badge, Button, Card } from '../../components/antigravity';
import { HrNoCompanyOnboarding, httpStatusOf, isNoCompanyError } from './hrNoCompanyOnboarding';
import {
  policyConfigMatrixAPI,
  policyDocumentsAPI,
} from '../../api/client';
import type { PolicyConfigWorkingPayload } from '../policy-config/types';
import { HrPolicyReviewWorkspace } from './HrPolicyReviewWorkspace';
import { HrPolicyAssistantPanel } from './HrPolicyAssistantPanel';
import { PolicyAssistantDockedShell } from './PolicyAssistantDockedShell';
import { CanonicalPolicyDiffView } from './CanonicalPolicyDiffView';
import { PolicyDiffView } from './PolicyDiffView';
import { PolicyTemplatePicker } from './PolicyTemplatePicker';
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
    <div className="sticky top-0 z-30" data-testid="hr-policy-status-strip">
      <Card padding="md">
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
      </Card>
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
}> = ({ matrixPayload, onRequestDetails }) => {
  // The HR endpoint hands back EITHER the published clone (read-only)
  // OR the draft (editable, never been published). The accordion has
  // historically said "What employees see today" for both — which is a
  // lie when the payload is a draft, because employees see nothing
  // until HR publishes. Switch the title + subtitle on that flag so
  // HR isn't surprised when the employee surface is empty.
  const isLive =
    matrixPayload?.status === 'published' ||
    matrixPayload?.source === 'published' ||
    matrixPayload?.source === 'published_clone';
  const heading = isLive ? 'What employees see today' : 'Your draft preview (not live yet)';
  const subtitle = isLive
    ? 'Summary of the currently live relocation policy by theme. Click a theme to see its individual benefit rows — read-only here. Edits happen in the Detailed review drawer.'
    : 'This draft is HR-only — employees see nothing from this on /hr/policy until you Publish draft. Click a theme to preview the benefit rows that would go live.';
  return (
    <Card padding="lg">
      <PolicyTopicSummaryList
        matrixPayload={matrixPayload}
        onRequestDetails={onRequestDetails}
        heading={heading}
        subtitle={subtitle}
      />
    </Card>
  );
};

// --- Build next version -----------------------------------------------------

const BuildNextVersionSection: React.FC<{
  documents: PolicyDocumentListItem[];
  hasLivePolicy: boolean;
  onImportClick: () => void;
  onTemplateClick: () => void;
  adminCompanyId?: string | null;
}> = ({ documents, hasLivePolicy, onImportClick, onTemplateClick, adminCompanyId: _adminCompanyId }) => {
  const [docsOpen, setDocsOpen] = useState(false);
  return (
    <Card padding="lg">
      {/* fix: AIQ-LIVE-QA — when a version is already live, this is "create a new
          version", not "start your policy"; the first-run framing is misleading
          next to a published matrix. */}
      <h2 className="text-lg font-semibold text-[#0b2b43]">
        {hasLivePolicy ? 'Create a new policy version' : 'Start your policy'}
      </h2>
      <p className="text-sm text-slate-600 mt-1.5">
        {hasLivePolicy
          ? "Start from a template or import a document to draft a replacement. Your live version stays in effect until you publish it."
          : "Pick a template baseline. You'll edit the caps yourself in the benefit table below — no document upload required."}
      </p>
      {/* PR 0.5 simplification: template is the primary CTA (matrix-first
          authoring). Document import demoted to a quieter secondary link
          beneath the primary action. */}
      <div className="mt-4">
        <Button onClick={onTemplateClick} data-testid="start-from-template-card">
          Start from a template
        </Button>
        <Button unstyled
          type="button"
          onClick={onImportClick}
          className="ml-3 text-sm text-slate-600 hover:text-[#0b2b43] underline"
        >
          Or import a document instead →
        </Button>
        <p className="text-xs text-slate-500 mt-2">
          Templates pre-fill the matrix with level-tiered caps
          (Entry&nbsp;Level / Manager / Director / VP / C-suite). Importing a PDF
          extracts rules from a company policy you already have.
        </p>
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
        <Button unstyled
          type="button"
          onClick={() => setDocsOpen((v) => !v)}
          className="text-sm font-medium text-[#0b2b43] hover:underline"
        >
          {docsOpen ? '▾' : '▸'} Uploaded documents ({documents.length})
        </Button>
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
      <Button unstyled
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center justify-between w-full"
      >
        <h2 className="text-lg font-semibold text-[#0b2b43]">
          Version history ({rows.length})
        </h2>
        <span className="text-slate-500">{open ? '▾' : '▸'}</span>
      </Button>
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
  // [T2.4] HR account not yet linked to a company → every policy endpoint 403s.
  const [noCompany, setNoCompany] = useState(false);
  const [postNormalizePolicyId, setPostNormalizePolicyId] = useState<string | null>(null);
  const [workspaceRefreshTrigger, setWorkspaceRefreshTrigger] = useState(0);
  const [templatePickerOpen, setTemplatePickerOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    setNoCompany(false);
    // [T2.4] Classify per-endpoint failures rather than blanket-swallowing them:
    //   403 → account not linked to a company → onboarding state
    //   404 → benign "no data yet" → keep the empty fallback (starter onboarding)
    //   other (5xx/network) → a real error must still surface, not be hidden
    let companyDenied = false;
    let hardError = false;
    const onErr = <T,>(fallback: T) => (err: unknown): T => {
      const status = httpStatusOf(err);
      if (status === 403) companyDenied = true;
      else if (status !== 404) hardError = true;
      return fallback;
    };
    try {
      const params = adminCompanyId ? { company_id: adminCompanyId } : undefined;
      const [docsRes, matrixRes] = await Promise.all([
        policyDocumentsAPI.list(params).catch(onErr({ documents: [] as PolicyDocumentListItem[] })),
        policyConfigMatrixAPI.hrGet(adminCompanyId ?? undefined).catch(onErr(null)),
      ]);
      if (companyDenied) {
        setNoCompany(true);
        return;
      }
      setDocuments(Array.isArray(docsRes?.documents) ? (docsRes.documents as PolicyDocumentListItem[]) : []);
      setMatrixPayload((matrixRes as PolicyConfigWorkingPayload | null) ?? null);
      if (hardError) setLoadError('Unable to load your policy. Try again or contact support.');

      // Canonical (document-normalized) policy status is loaded lazily by
      // the Detailed review drawer when the user opens it. The top-level
      // status strip relies on the matrix payload for the "Live" signal,
      // which is the published surface employees actually resolve against
      // (canonical-only deployments still render via the HrPolicyReviewWorkspace
      // inside the drawer). Keeping the cold-path load minimal here avoids
      // two-version race conditions and a 404 on companies that have only
      // published through the matrix.
    } catch (err) {
      // Defensive: anything the per-call handlers didn't catch.
      if (isNoCompanyError(err)) setNoCompany(true);
      else setLoadError('Unable to load your policy. Try again or contact support.');
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

  // Canonical lives in normalized.version.status; matrix editable + not
  // sourced from a published clone means HR is mid-draft on the matrix.
  // Used by Section 3 ("Build your next version") to hide the two onboarding
  // doors once HR has any version in flight — no point offering a fresh
  // template when they are already editing one.
  const canonicalLive =
    String(normalized?.version?.status || '').toLowerCase() === 'published';
  const hasDraftInProgress = Boolean(
    matrixPayload?.editable &&
      matrixPayload?.source !== 'published' &&
      matrixPayload?.source !== 'published_clone'
  );

  // Publish gate: matrix-only deployments (the common case) need to be
  // able to publish too. Previously this required a `normalized.version.id`
  // (a document-extracted/canonical policy), which meant matrix-only HR
  // teams had a forever-disabled top "Publish draft" button — and the
  // legacy "Publish version" button further down published a different
  // system (`policy_versions`) that the employee endpoint doesn't read.
  // Result: HR clicked Publish, employee saw "No published policy yet".
  // Enable the top button whenever there's a matrix draft to publish or a
  // canonical version ready to ship; the publish handler picks the right
  // path based on what's available.
  const matrixHasUnpublishedChanges =
    Boolean(matrixPayload?.editable) &&
    matrixPayload?.source !== 'published' &&
    matrixPayload?.source !== 'published_clone';
  const publishEnabled =
    matrixHasUnpublishedChanges || (Boolean(normalized?.version?.id) && !hasLivePolicy);
  const [publishBusy, setPublishBusy] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);

  const publishMatrix = useCallback(async () => {
    if (!matrixHasUnpublishedChanges) {
      // Nothing matrix-side to publish — fall through to scroll-to-detail
      // so the canonical/document-extracted publish controls in the
      // workspace below pick up the action.
      const el = document.getElementById('hr-policy-detailed-review');
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    setPublishBusy(true);
    setPublishError(null);
    try {
      await policyConfigMatrixAPI.hrPublish({}, adminCompanyId ?? undefined);
      // Bump refreshes both the matrix payload and the workspace state so
      // the topic accordion flips from "Your draft preview" to "What
      // employees see today" without a hard reload.
      bump();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setPublishError(
        typeof detail === 'string' && detail
          ? detail
          : 'Could not publish your draft. Try the legacy publish controls in the Detailed review section, or contact support.'
      );
    } finally {
      setPublishBusy(false);
    }
  }, [matrixHasUnpublishedChanges, adminCompanyId, bump]);

  const handleImportClick = () => {
    // Scroll to the workspace; the Document intake card lives at the top
    // of HrPolicyReviewWorkspace so the user lands on the upload controls.
    const el = document.getElementById('hr-policy-detailed-review');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const policyId = normalized?.version?.policy_id ?? normalized?.policy?.id ?? null;

  // Sprint 2: docked-shell open state lifted to the page so the trigger
  // button and the shell share it. Replaces the modal-overlay flow that
  // PolicyAssistantFab + PolicyAssistantSideSheet owned previously.
  const [assistantOpen, setAssistantOpen] = useState(false);

  if (loading) {
    return (
      <Card padding="lg">
        <div className="text-sm text-slate-600">Loading your policy…</div>
      </Card>
    );
  }

  // [T2.4] HR not linked to a company yet (403 from policy endpoints) → show the
  // onboarding state instead of the (misleading) "set up a policy" workspace.
  if (noCompany) {
    return <HrNoCompanyOnboarding />;
  }

  return (
    <PolicyAssistantDockedShell
      open={assistantOpen}
      onOpenChange={setAssistantOpen}
      title="Ask about this policy"
      subtitle="Bounded Q&A on this workspace's policy data."
      titleId="hr-policy-assistant-shell-title"
      assistant={() => (
        <HrPolicyAssistantPanel
          policyId={policyId}
          hasQueryablePolicy={hasLivePolicy}
          variant="embedded"
        />
      )}
    >
    <div className="space-y-6 pb-12">
      {loadError && <Alert variant="error">{loadError}</Alert>}
      {publishError && <Alert variant="error">{publishError}</Alert>}

      {/* Sprint 2 trigger — replaces the old PolicyAssistantFab. Sits
          flush-right above the status strip so it's discoverable
          without competing with the page heading. The docked shell
          owns the close affordance via its header X — the trigger
          hides when the panel is open so we don't render two ways to
          close the same panel. */}
      {assistantOpen ? null : (
        <div className="flex justify-end">
          <Button
            type="button"
            variant="outline"
            onClick={() => setAssistantOpen(true)}
            aria-expanded={false}
            aria-controls="hr-policy-assistant-shell-title"
          >
            Ask about this policy
          </Button>
        </div>
      )}

      {/* 1. Status strip */}
      <StatusStrip
        normalized={normalized}
        matrixPayload={matrixPayload}
        hasDocument={documents.length > 0}
        onPreviewEmployeeView={() => {
          // Workspace is now flat (no collapsible) — scroll to it so the
          // user lands on the publish/preview controls inside.
          const el = document.getElementById('hr-policy-detailed-review');
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }}
        onPublish={() => void publishMatrix()}
        publishEnabled={publishEnabled}
        publishBusy={publishBusy}
      />

      {/* 2. What employees see today — collapsed disclosure (slice 3d).
          The benefit table further down is HR's primary work surface;
          this read-only summary is reference, not action. Stays in DOM
          (data still pre-fetched) so opening is instant.
          Disclosure label flips to "Preview your draft" when the
          payload is a draft (matches the inner heading from
          TopicSummarySection so HR isn't misled into thinking employees
          can see the draft). */}
      <details className="rounded-xl border border-[#e2e8f0] bg-white shadow-sm">
        <summary className="cursor-pointer list-none px-5 py-4 [&::-webkit-details-marker]:hidden">
          <div className="flex items-center justify-between gap-3">
            <span className="text-base font-semibold text-[#0b2b43]">
              {(matrixPayload?.status === 'published' ||
                matrixPayload?.source === 'published' ||
                matrixPayload?.source === 'published_clone')
                ? '▸ See what employees see today'
                : '▸ Preview your draft (not live for employees yet)'}
            </span>
            <span className="text-xs text-[#64748b]">
              {(matrixPayload?.status === 'published' ||
                matrixPayload?.source === 'published' ||
                matrixPayload?.source === 'published_clone')
                ? 'read-only summary by theme'
                : ''}
            </span>
          </div>
        </summary>
        <div className="px-5 pb-5">
          <TopicSummarySection
            matrixPayload={matrixPayload}
            onRequestDetails={() => {
              const el = document.getElementById('hr-policy-detailed-review');
              if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }}
          />
        </div>
      </details>

      {/* 3. Build your next version (only shown when there is no live policy
          OR no draft in progress — once HR has a working version, the matrix
          editor below is the primary authoring surface). PR 0.5 simplification:
          template is the primary CTA; document import is a quieter secondary
          link to keep the "matrix-primary" pipeline stance clear. */}
      {!canonicalLive && !hasDraftInProgress && (
        <BuildNextVersionSection
          documents={documents}
          hasLivePolicy={hasLivePolicy}
          onImportClick={handleImportClick}
          onTemplateClick={() => setTemplatePickerOpen(true)}
          adminCompanyId={adminCompanyId}
        />
      )}

      <PolicyTemplatePicker
        open={templatePickerOpen}
        onClose={() => setTemplatePickerOpen(false)}
        onApplied={() => {
          // Reload the page data so Section 2 (topics) and Section 4
          // (diff) pick up the new draft without a hard refresh.
          bump();
        }}
        adminCompanyId={adminCompanyId}
      />

      {/* 4. Draft vs Live diffs — collapsed disclosures (slice 3d).
          Big diffs need to stay one click away, not push the editable
          benefit table further down the page. The category-grouped
          accordions inside (slice 3a) keep the open state scannable.
          Slice 2 still gates the canonical diff to deployments with
          uploaded documents. */}
      <details className="rounded-xl border border-[#e2e8f0] bg-white shadow-sm">
        <summary className="cursor-pointer list-none px-5 py-4 [&::-webkit-details-marker]:hidden">
          <div className="flex items-center justify-between gap-3">
            <span className="text-base font-semibold text-[#0b2b43]">
              ▸ See draft vs live changes
            </span>
            <span className="text-xs text-[#64748b]">What changed, benefit by benefit</span>
          </div>
        </summary>
        <div className="px-5 pb-5">
          <PolicyDiffView
            adminCompanyId={adminCompanyId ?? null}
            refreshTrigger={workspaceRefreshTrigger}
          />
        </div>
      </details>
      {documents.length > 0 && (
        <details className="rounded-xl border border-[#e2e8f0] bg-white shadow-sm">
          <summary className="cursor-pointer list-none px-5 py-4 [&::-webkit-details-marker]:hidden">
            <div className="flex items-center justify-between gap-3">
              <span className="text-base font-semibold text-[#0b2b43]">
                ▸ See policy rules from your documents
              </span>
              <span className="text-xs text-[#64748b]">Policy rules extracted from your source documents</span>
            </div>
          </summary>
          <div className="px-5 pb-5">
            <CanonicalPolicyDiffView
              adminCompanyId={adminCompanyId ?? null}
              refreshTrigger={workspaceRefreshTrigger}
            />
          </div>
        </details>
      )}

      {/* 5. Benefit table & publish (was: "Detailed review" collapsible).
          PR 0.5 simplification flattens this — the table is the primary
          authoring surface, no point hiding it. The version history below
          stays compact via VersionHistorySection's own collapse. */}
      <div id="hr-policy-detailed-review">
        <HrPolicyReviewWorkspace
          refreshTrigger={workspaceRefreshTrigger}
          postNormalizePolicyId={postNormalizePolicyId}
          onBindComplete={() => setPostNormalizePolicyId(null)}
          adminCompanyId={adminCompanyId ?? null}
          hasPublishedMatrix={hasLivePolicy}
        />
      </div>

      {/* 6. Version history */}
      <VersionHistorySection normalized={normalized} />

      {/* Keeps refresh bump wired so the Detailed review's internal actions
          (publish / unpublish / re-normalize) reload the top-level status. */}
      <div aria-hidden className="hidden">
        <Button unstyled type="button" onClick={bump} />
      </div>
    </div>
    </PolicyAssistantDockedShell>
  );
};
