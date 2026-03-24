import React, { useCallback, useEffect, useState, useRef } from 'react';
import { Link, useSearchParams, useLocation } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { trackRouteEntry, trackShellRender, trackPolicyStage } from '../perf/pagePerf';
import { Alert, Button, Card } from '../components/antigravity';
import { employeeAPI, policyDocumentsAPI } from '../api/client';
import { EmployeePolicyPanel } from '../features/policy/EmployeePolicyPanel';
import { EmployeePolicyAssistantPanel } from '../features/policy/EmployeePolicyAssistantPanel';
import { HrPolicyReviewWorkspace } from '../features/policy/HrPolicyReviewWorkspace';
import { getAuthItem } from '../utils/demo';
import { buildRoute } from '../navigation/routes';

function EmployeePolicyContent() {
  const [pack, setPack] = useState<Awaited<ReturnType<typeof employeeAPI.getMyAssignmentPackagePolicy>> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    employeeAPI
      .getMyAssignmentPackagePolicy()
      .then((res) => {
        if (!cancelled) setPack(res);
      })
      .catch(() => {
        if (!cancelled) {
          setPack({
            status: 'error',
            ok: false,
            assignment_id: null,
            has_policy: false,
            policy: null,
            benefits: [],
            exclusions: [],
            message: "We couldn't load your policy right now. Please try again shortly.",
            message_secondary: null,
          });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="pb-6">
      <EmployeePolicyAssistantPanel
        assignmentId={pack?.assignment_id}
        assignmentLoading={loading}
        variant="sideSheet"
      />
      <div className="min-w-0">
        <EmployeePolicyPanel pack={pack} loading={loading} />
      </div>
    </div>
  );
}

export const HrPolicy: React.FC = () => {
  const role = getAuthItem('relopass_role');
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const adminCompanyId = searchParams.get('adminCompanyId') || null;

  useEffect(() => {
    trackRouteEntry(location.pathname);
    trackShellRender(location.pathname);
  }, [location.pathname]);

  const [workspaceRefreshTrigger, setWorkspaceRefreshTrigger] = useState(0);
  const [postNormalizePolicyId, setPostNormalizePolicyId] = useState<string | null>(null);
  useEffect(() => {
    trackPolicyStage('upload_ui_shown');
  }, []);

  const handleNormalized = useCallback((policyId: string) => {
    setPostNormalizePolicyId(policyId);
    setWorkspaceRefreshTrigger((t) => t + 1);
  }, []);

  const handleDocumentsChange = useCallback(() => {
    setWorkspaceRefreshTrigger((t) => t + 1);
  }, []);

  if (role === 'EMPLOYEE') {
    return (
      <AppShell
        title="HR policy"
        subtitle="Published policy from your employer (read-only). Use Policy Assistant (top right) to open a side panel without leaving this page."
      >
        <EmployeePolicyContent />
      </AppShell>
    );
  }

  return (
    <AppShell
      title={adminCompanyId ? 'Admin: policy' : 'Policy'}
      subtitle={
        adminCompanyId ? 'View and edit company policy as admin.' : 'Company relocation policies.'
      }
    >
      <div data-hr-policy-page="v2">
        {adminCompanyId && (
          <p className="text-sm text-[#6b7280] mb-4">
            Admin mode: viewing policy for company <code className="bg-[#f1f5f9] px-1 rounded">{adminCompanyId}</code>.{' '}
            <Link to={buildRoute('adminPolicies')} className="text-[#0b2b43] hover:underline">← Back to Policy Workspace</Link>
          </p>
        )}

        <div id="hr-policy-document-intake" className="scroll-mt-4">
          <PolicyDocumentIntakeSection onNormalized={handleNormalized} onDocumentsChange={handleDocumentsChange} adminCompanyId={adminCompanyId} />
        </div>
        <div className="mt-8">
          <HrPolicyReviewWorkspace
            refreshTrigger={workspaceRefreshTrigger}
            postNormalizePolicyId={postNormalizePolicyId}
            onBindComplete={() => setPostNormalizePolicyId(null)}
            adminCompanyId={adminCompanyId}
          />
        </div>
      </div>
    </AppShell>
  );
};

function formatDate(val: string | null | undefined): string {
  if (!val) return '-';
  try {
    return new Date(val).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return val;
  }
}

function formatDateTime(val: string | null | undefined): string {
  if (!val) return '-';
  try {
    return new Date(val).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return val;
  }
}

const DOC_TYPE_LABELS: Record<string, string> = {
  assignment_policy: 'Assignment policy',
  policy_summary: 'Policy summary',
  tax_policy: 'Tax policy',
  country_addendum: 'Country addendum',
  unknown: 'Unknown',
};

const SCOPE_LABELS: Record<string, string> = {
  global: 'Global',
  long_term_assignment: 'Long-term assignment',
  short_term_assignment: 'Short-term assignment',
  tax_equalization: 'Tax equalization',
  mixed: 'Mixed',
  unknown: 'Unknown',
};

const CLAUSE_TYPE_LABELS: Record<string, string> = {
  scope: 'Scope',
  eligibility: 'Eligibility',
  benefit: 'Benefit',
  exclusion: 'Exclusion',
  approval_rule: 'Approval rule',
  evidence_rule: 'Evidence rule',
  tax_rule: 'Tax rule',
  definition: 'Definition',
  lifecycle_rule: 'Lifecycle rule',
  unknown: 'Unknown',
};

/** Canonical metadata schema from backend - supports legacy shapes via normalization. */
interface PolicyDocumentMetadata {
  detected_title?: string | null;
  detected_version?: string | null;
  detected_effective_date?: string | null;
  mentioned_assignment_types?: string[];
  mentioned_family_status_terms?: string[];
  mentioned_benefit_categories?: string[];
  mentioned_units?: string[];
  likely_table_heavy?: boolean;
  likely_country_addendum?: boolean;
  likely_tax_specific?: boolean;
  likely_contains_exclusions?: boolean;
  likely_contains_approval_rules?: boolean;
  likely_contains_evidence_rules?: boolean;
  // Legacy fields (normalized on backend)
  policy_title?: string | null;
  version?: string | null;
  effective_date?: string | null;
  assignment_types_mentioned?: string[];
  benefit_categories_mentioned?: string[];
  contains_tables?: boolean;
}

function DetectedMetadataDisplay({ metadata }: { metadata: PolicyDocumentMetadata | null | undefined }) {
  if (!metadata || (typeof metadata !== 'object')) return null;

  const title = metadata.detected_title ?? metadata.policy_title ?? null;
  const version = metadata.detected_version ?? metadata.version ?? null;
  const effDate = metadata.detected_effective_date ?? metadata.effective_date ?? null;
  const assignmentTypes = metadata.mentioned_assignment_types ?? metadata.assignment_types_mentioned ?? [];
  const familyTerms = metadata.mentioned_family_status_terms ?? [];
  const benefitCats = metadata.mentioned_benefit_categories ?? metadata.benefit_categories_mentioned ?? [];
  const units = metadata.mentioned_units ?? [];
  const tableHeavy = metadata.likely_table_heavy ?? metadata.contains_tables ?? false;
  const countryAddendum = metadata.likely_country_addendum ?? false;
  const taxSpecific = metadata.likely_tax_specific ?? false;
  const hasExclusions = metadata.likely_contains_exclusions ?? false;
  const hasApproval = metadata.likely_contains_approval_rules ?? false;
  const hasEvidence = metadata.likely_contains_evidence_rules ?? false;

  const hasAny =
    title || version || effDate ||
    assignmentTypes.length || familyTerms.length || benefitCats.length || units.length ||
    tableHeavy || countryAddendum || taxSpecific || hasExclusions || hasApproval || hasEvidence;

  if (!hasAny) return null;

  const layer1Note = (
    <p className="text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded px-2 py-1.5 mb-3">
      These fields come from automatic document extraction and are for triage only. What employees see is driven by
      your <strong>published policy</strong> after you build and publish it in the policy workspace—not this preview list.
    </p>
  );

  const MetaRow = ({ label, value }: { label: string; value: React.ReactNode }) => (
    <div className="flex gap-2 py-1 text-sm">
      <span className="text-[#6b7280] min-w-[10rem]">{label}:</span>
      <span className="text-[#0b2b43]">{value ?? '-'}</span>
    </div>
  );

  const TagList = ({ items }: { items: string[] }) =>
    items.length ? (
      <span className="flex flex-wrap gap-1">
        {items.map((x) => (
          <span key={x} className="px-2 py-0.5 rounded bg-[#e2e8f0] text-[#4b5563] text-xs">
            {x}
          </span>
        ))}
      </span>
    ) : (
      <span className="text-[#9ca3af]"> - </span>
    );

  const BoolBadge = ({ v }: { v: boolean }) => (
    <span className={v ? 'text-[#059669] font-medium' : 'text-[#9ca3af]'}>
      {v ? 'Yes' : 'No'}
    </span>
  );

  return (
    <div>
      <div className="text-sm font-medium text-[#0b2b43] mb-2">Detected metadata</div>
      {layer1Note}
      <div className="bg-white rounded border border-[#e2e8f0] p-4 space-y-1">
        <MetaRow label="Title" value={title} />
        <MetaRow label="Version" value={version} />
        <MetaRow label="Effective date" value={effDate ? formatDate(effDate) : null} />
        <MetaRow label="Assignment types" value={<TagList items={assignmentTypes} />} />
        <MetaRow label="Family status terms" value={<TagList items={familyTerms} />} />
        <MetaRow label="Benefit categories" value={<TagList items={benefitCats} />} />
        <MetaRow label="Units mentioned" value={<TagList items={units} />} />
        <MetaRow label="Table-heavy" value={<BoolBadge v={tableHeavy} />} />
        <MetaRow label="Country addendum" value={<BoolBadge v={countryAddendum} />} />
        <MetaRow label="Tax-specific" value={<BoolBadge v={taxSpecific} />} />
        <MetaRow label="Contains exclusions" value={<BoolBadge v={hasExclusions} />} />
        <MetaRow label="Approval rules" value={<BoolBadge v={hasApproval} />} />
        <MetaRow label="Evidence rules" value={<BoolBadge v={hasEvidence} />} />
      </div>
    </div>
  );
}

/** Compact display of early clause heuristics from extraction (not authoritative for employees). */
function NormalizedHintsDisplay({ hints }: { hints: Record<string, unknown> }) {
  if (!hints || typeof hints !== 'object') return null;
  const entries = Object.entries(hints).filter(([, v]) => v != null && v !== '');
  if (entries.length === 0) return null;
  const fmt = (v: unknown): string => {
    if (Array.isArray(v)) return v.join(', ');
    if (typeof v === 'boolean') return v ? 'Yes' : 'No';
    return String(v);
  };
  const label = (k: string): string =>
    k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  return (
    <div className="mt-2 px-2 py-1.5 rounded bg-[#f0fdf4] border border-[#bbf7d0] text-xs">
      <span className="text-[#166534] font-medium">Early clause hints: </span>
      <span className="text-[#15803d]">
        {entries.map(([k, v]) => `${label(k)}=${fmt(v)}`).join(' · ')}
      </span>
    </div>
  );
}

function DocumentStructureTab({ docId }: { docId: string }) {
  const [clauses, setClauses] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [clauseTypeFilter, setClauseTypeFilter] = useState<string>('');
  const [patchingId, setPatchingId] = useState<string | null>(null);
  const [editingClause, setEditingClause] = useState<string | null>(null);

  const loadClauses = async () => {
    setLoading(true);
    try {
      const res = await policyDocumentsAPI.listClauses(docId, clauseTypeFilter || undefined);
      setClauses(res.clauses || []);
    } catch {
      setClauses([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadClauses();
  }, [docId, clauseTypeFilter]);

  const handlePatch = async (clauseId: string, patch: { clause_type?: string; title?: string; hr_override_notes?: string }) => {
    setPatchingId(clauseId);
    try {
      await policyDocumentsAPI.patchClause(docId, clauseId, patch);
      await loadClauses();
      setEditingClause((prev) => (prev === clauseId ? null : prev));
    } finally {
      setPatchingId(null);
    }
  };

  const grouped = clauses.reduce<Record<string, any[]>>((acc, c) => {
    const key = c.section_label || c.section_path || 'Unsectioned';
    if (!acc[key]) acc[key] = [];
    acc[key].push(c);
    return acc;
  }, {});

  if (loading && clauses.length === 0) {
    return <div className="text-sm text-[#6b7280] py-4">Loading clauses…</div>;
  }

  if (clauses.length === 0) {
    return (
      <div className="text-sm text-[#6b7280] py-4">
        No clauses yet. Click Reprocess to segment the document.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <label className="text-sm text-[#6b7280]">Filter by type:</label>
        <select
          value={clauseTypeFilter}
          onChange={(e) => setClauseTypeFilter(e.target.value)}
          className="border border-[#e2e8f0] rounded px-2 py-1 text-sm"
        >
          <option value="">All</option>
          {Object.entries(CLAUSE_TYPE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <span className="text-xs text-[#6b7280]">{clauses.length} clauses</span>
      </div>
      <div className="space-y-4">
        {Object.entries(grouped).map(([section, items]) => (
          <div key={section} className="border border-[#e2e8f0] rounded-lg overflow-hidden">
            <div className="px-3 py-2 bg-[#f1f5f9] text-sm font-medium text-[#0b2b43]">
              {section}
            </div>
            <div className="divide-y divide-[#e2e8f0]">
              {items.map((c) => {
                const isEditing = editingClause === c.id;
                const conf = typeof c.confidence === 'number' ? Math.round(c.confidence * 100) : null;
                return (
                  <div key={c.id} className="px-3 py-2 bg-white">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2 text-xs text-[#6b7280]">
                          <span className="px-2 py-0.5 rounded bg-[#e2e8f0] text-[#4b5563]">
                            {CLAUSE_TYPE_LABELS[c.clause_type] || c.clause_type}
                          </span>
                          {c.source_page_start != null && (
                            <span>p.{c.source_page_start}{c.source_page_end != null && c.source_page_end !== c.source_page_start ? `–${c.source_page_end}` : ''}</span>
                          )}
                          {conf != null && (
                            <span className={conf >= 70 ? 'text-[#059669]' : conf >= 50 ? 'text-amber-600' : 'text-[#6b7280]'}>
                              {conf}% conf
                            </span>
                          )}
                        </div>
                        {c.title && (
                          <div className="text-sm font-medium text-[#0b2b43] mt-1">{c.title}</div>
                        )}
                        <pre className="text-xs text-[#4b5563] mt-1 whitespace-pre-wrap break-words">
                          {c.raw_text?.slice(0, 300)}
                          {(c.raw_text?.length || 0) > 300 ? '…' : ''}
                        </pre>
                        {c.normalized_hint_json && Object.keys(c.normalized_hint_json).length > 0 && (
                          <NormalizedHintsDisplay hints={c.normalized_hint_json} />
                        )}
                        {c.hr_override_notes && (
                          <div className="text-xs text-amber-700 mt-1">HR note: {c.hr_override_notes}</div>
                        )}
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setEditingClause(isEditing ? null : c.id)}
                      >
                        {isEditing ? 'Cancel' : 'Re-tag'}
                      </Button>
                    </div>
                    {isEditing && (
                      <div className="mt-3 pt-3 border-t border-[#e2e8f0] flex flex-wrap items-center gap-2">
                        <select
                          defaultValue={c.clause_type}
                          className="border border-[#e2e8f0] rounded px-2 py-1 text-sm"
                          onChange={(e) => handlePatch(c.id, { clause_type: e.target.value })}
                          disabled={patchingId === c.id}
                        >
                          {Object.entries(CLAUSE_TYPE_LABELS).map(([k, v]) => (
                            <option key={k} value={k}>{v}</option>
                          ))}
                        </select>
                        <span className="text-xs text-[#6b7280]">
                          {patchingId === c.id ? 'Saving…' : 'Change applies on select'}
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const UPLOAD_ERROR_MESSAGES: Record<string, string> = {
  upload_missing_file: 'Choose a file first.',
  upload_invalid_mime_type: 'Only PDF or DOCX files are supported.',
  upload_empty_file: 'The selected file is empty.',
  upload_storage_failed: 'The file could not be uploaded to storage.',
  upload_db_insert_failed: 'The uploaded file could not be registered in the database.',
  upload_extract_failed: 'The file was uploaded, but extraction failed.',
  upload_processing_failed: 'The policy document could not be processed.',
  upload_unexpected_exception: 'An unexpected upload error occurred.',
  storage_missing_service_role:
    'Policy document uploads require Supabase storage. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the backend .env (see .env.example) to enable uploads.',
  storage_missing_url:
    'Policy document uploads require Supabase storage. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the backend .env (see .env.example) to enable uploads.',
  storage_bucket_not_found:
    'Policy storage bucket is unavailable. In Supabase go to Storage → New bucket, create a bucket named hr-policies (public or private), then try again.',
  storage_upload_failed: 'The file could not be uploaded to storage.',
  storage_access_denied: 'Policy storage access denied.',
  policy_documents_table_missing: 'Policy database tables are missing.',
  policy_document_clauses_table_missing: 'Policy database tables are missing.',
  policy_versions_table_missing: 'Policy database tables are missing.',
  resolved_assignment_policies_table_missing: 'Policy database tables are missing.',
  db_insert_failed: 'The uploaded file could not be registered in the database.',
  upload_company_required: 'Company is required for upload. When viewing a company\'s policy workspace, uploads are scoped to that company.',
  invalid_file_type: 'Only PDF or DOCX files are supported.',
  normalization_failed:
    'Normalization failed unexpectedly. Your extraction data is unchanged—try Reprocess, then normalize again.',
  NORMALIZATION_NOT_READY:
    'This document is not ready to normalize yet. Fix the listed issues, then use Reprocess if needed.',
  NORMALIZATION_BLOCKED:
    'Normalization cannot produce a meaningful draft (failed extraction, unknown policy scope with no mapped benefits/exclusions, or similar). Reprocess or upload a fuller policy.',
  INVALID_POLICY_VERSION_SCHEMA:
    'Schema validation failed on assembled policy data—this usually indicates an internal mapping or taxonomy issue, not vague policy wording. Retry after reprocess; contact support with request_id if it persists.',
  INVALID_POLICY_VERSIONS_PAYLOAD:
    'Schema validation failed on assembled policy data (legacy code; same as INVALID_POLICY_VERSION_SCHEMA).',
  PERSISTENCE_FAILED:
    'The database rejected a normalized row after validation. Try again or apply pending migrations.',
  POLICY_VERSION_PERSISTENCE_FAILED:
    'The database rejected the policy_versions row (legacy code; same as PERSISTENCE_FAILED).',
  POLICY_LAYER2_PERSISTENCE_FAILED:
    'The database rejected a benefit rule, exclusion, or link row (legacy code; same as PERSISTENCE_FAILED).',
  publish_failed_after_normalize:
    'Policy was saved but could not be published. Use “Publish version” in the HR Policy review workspace.',
  normalization_input_invalid:
    'This document is not ready to normalize yet (legacy code; same as NORMALIZATION_NOT_READY).',
  // Download-url and policy errors
  policy_policy_not_found: 'Policy not found.',
  policy_file_missing: 'Policy file not found in storage.',
  policy_file_path_invalid: 'Invalid policy file path.',
  policy_file_sign_failed: 'Failed to create signed download URL.',
  policy_storage_unexpected_error: 'Download link could not be generated.',
};

function getUploadErrorMessage(err: unknown): string {
  const data = err && typeof err === 'object' && 'response' in err
    ? (err as { response?: { data?: { error_code?: string; message?: string; detail?: string } } }).response?.data
    : null;
  const code = data?.error_code;
  const message = data?.message && typeof data.message === 'string' ? data.message : null;
  const detail = data?.detail && typeof data.detail === 'string' ? data.detail : null;
  // For normalization errors, prefer server message (it now includes real error); append detail if message is generic
  if (code === 'normalization_failed' && message) {
    if (detail && !message.includes(detail.slice(0, 50))) return `${message} ${detail}`;
    return message;
  }
  if (code && UPLOAD_ERROR_MESSAGES[code]) {
    if (!message) return UPLOAD_ERROR_MESSAGES[code];
    if (code === 'INVALID_POLICY_VERSION_SCHEMA' || code === 'PERSISTENCE_FAILED') {
      return `${UPLOAD_ERROR_MESSAGES[code]} ${message}`.trim();
    }
  }
  if (message) return message;
  if (detail) return detail;
  return 'Something went wrong. Try again.';
}

function getUploadRequestId(err: unknown): string | null {
  const data = err && typeof err === 'object' && 'response' in err
    ? (err as { response?: { data?: { request_id?: string } } }).response?.data
    : null;
  return (data?.request_id && typeof data.request_id === 'string') ? data.request_id : null;
}

function PolicyDocumentIntakeSection({
  onNormalized,
  onDocumentsChange,
  adminCompanyId = null,
}: {
  onNormalized?: (policyId: string) => void;
  onDocumentsChange?: () => void;
  adminCompanyId?: string | null;
}) {
  const [documents, setDocuments] = useState<any[]>([]);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState('');
  const [uploadRequestId, setUploadRequestId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expandedTab, setExpandedTab] = useState<'metadata' | 'structure'>('metadata');
  const [reprocessingId, setReprocessingId] = useState<string | null>(null);
  const [normalizingId, setNormalizingId] = useState<string | null>(null);
  const [health, setHealth] = useState<{
    bucket_access_ok: boolean;
    policy_documents_table_ok: boolean;
    supabase_url_present?: boolean;
    service_role_present?: boolean;
    config_error?: string;
    bucket_probe?: { diagnosis?: string };
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [deleteFeedback, setDeleteFeedback] = useState<'idle' | 'deleting' | 'done' | 'error'>('idle');

  const loadDocs = async () => {
    try {
      const params = adminCompanyId ? { company_id: adminCompanyId } : undefined;
      const res = await policyDocumentsAPI.list(params);
      setDocuments(res.documents || []);
      setMessage('');
    } catch (err: unknown) {
      setMessage('Unable to load documents');
      setDocuments([]);
    }
  };

  const loadHealth = async () => {
    try {
      const h = await policyDocumentsAPI.health();
      setHealth(h);
    } catch {
      setHealth(null);
    }
  };

  const isDevOrLocalhost =
    import.meta.env.DEV ||
    (typeof window !== 'undefined' && window.location.hostname === 'localhost');
  const configOnlyInvalid =
    health && (health.config_error === 'wrong_key_type' || health.config_error === 'wrong_project_url_key_mismatch' || health.bucket_probe?.diagnosis === 'wrong_key_type');
  const uploadReady =
    health === null ||
    (health.bucket_access_ok && health.policy_documents_table_ok) ||
    (isDevOrLocalhost && health && (!health.supabase_url_present || !health.service_role_present)) ||
    (isDevOrLocalhost && configOnlyInvalid);

  useEffect(() => {
    loadDocs();
    loadHealth();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- loadDocs uses adminCompanyId from closure
  }, [adminCompanyId]);

  const handleUpload = async () => {
    const fileToUpload = uploadFile;
    if (!fileToUpload || !(fileToUpload instanceof File)) {
      setMessage('Choose a file first.');
      return;
    }
    setMessage('');
    setUploadRequestId(null);
    setUploading(true);
    try {
      if (import.meta.env.DEV) {
        console.info('policy upload handleUpload', {
          name: fileToUpload.name,
          size: fileToUpload.size,
          type: fileToUpload.type,
          isFile: fileToUpload instanceof File,
        });
      }
      const res = await policyDocumentsAPI.upload(fileToUpload, adminCompanyId);
      setUploadRequestId(res.request_id || null);
      if (res.ok) {
        setUploadFile(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
        setMessage(
          'Document uploaded and classified. Review the entry below, then use Normalize & publish to create and release a policy version to employees.'
        );
        await loadDocs();
        onDocumentsChange?.();
      } else {
        setMessage(UPLOAD_ERROR_MESSAGES[res.error_code || ''] || res.message || 'Upload failed.');
        if (res.document) {
          await loadDocs();
          setMessage((m) => m + ' Document is in the list below; you can reprocess or normalize & publish.');
        }
      }
    } catch (err: unknown) {
      setMessage(getUploadErrorMessage(err));
      setUploadRequestId(getUploadRequestId(err));
    } finally {
      setUploading(false);
    }
  };

  const handleReprocess = async (docId: string) => {
    setMessage('');
    setReprocessingId(docId);
    try {
      await policyDocumentsAPI.reprocess(docId);
      await loadDocs();
      onDocumentsChange?.();
      setExpandedId(docId);
    } catch (err: unknown) {
      const detail = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : null;
      setMessage(String(detail || 'Reprocess failed'));
    } finally {
      setReprocessingId(null);
    }
  };

  const handleNormalize = async (docId: string) => {
    setMessage('');
    setNormalizingId(docId);
    try {
      const res = await policyDocumentsAPI.normalize(docId);
      const br = res.summary?.benefit_rules ?? 0;
      const ex = res.summary?.exclusions ?? 0;
      const drc =
        (res.summary && typeof res.summary === 'object' && 'draft_rule_candidates' in res.summary
          ? (res.summary as { draft_rule_candidates?: number }).draft_rule_candidates
          : undefined) ?? res.rule_candidates_summary?.draft_rule_candidates;

      if (res.normalization_result_code === 'NORMALIZED_DRAFT_ONLY' || res.outcome === 'normalized_but_not_publishable') {
        const draftHint =
          typeof drc === 'number' && drc > 0 && br + ex === 0
            ? ' The document was normalized into a draft (clause-level signals retained) and requires HR review before employee use.'
            : '';
        setMessage(
          'The document was analyzed, but it does not contain enough structured benefit or exclusion rules to publish automatically.' +
            draftHint +
            ` Draft saved: ${br} benefits, ${ex} exclusions. Review in the policy workspace or upload a fuller policy, then publish when ready.`
        );
      } else if (res.normalization_result_code === 'NORMALIZED_PUBLISH_BLOCKED' || res.outcome === 'publish_blocked') {
        const codeSuffix = res.publish_block_code ? ` [${res.publish_block_code}]` : '';
        setMessage(
          `Draft saved (${br} benefits, ${ex} exclusions) but automatic publish was blocked${codeSuffix}. ${
            res.publish_block_detail || 'Use Publish version in the review workspace when requirements are met.'
          }`
        );
      } else {
        const pubNote = res.published ? ' Published to employees.' : '';
        let msg = `Normalize complete. ${br} benefits, ${ex} exclusions.${pubNote}`;
        if (res.comparison_readiness_code === 'COMPARISON_NOT_READY') {
          msg +=
            ' The document contains policy signals, but not enough structured limits for automatic budget checks yet.';
        }
        setMessage(msg);
      }
      await loadDocs();
      if (res.policy_id) onNormalized?.(res.policy_id);
    } catch (err: unknown) {
      const data = err && typeof err === 'object' && 'response' in err
        ? (err as {
            response?: {
              data?: {
                error_code?: string;
                message?: string;
                detail?: string;
                hint?: string;
                errors?: Array<{ path?: string; code?: string; message?: string }>;
              };
            };
          }).response?.data
        : null;
      const code = data?.error_code;
      let msg = data?.message || (code && UPLOAD_ERROR_MESSAGES[code]) || data?.detail;
      const issues = data?.errors;
      if (Array.isArray(issues) && issues.length) {
        const detail = issues
          .map((e) => (e.path && e.message ? `${e.path}: ${e.message}` : e.message || e.code || ''))
          .filter(Boolean)
          .join(' · ');
        if (detail) {
          msg = msg ? `${msg} ${detail}` : detail;
        }
      }
      const normDetails = (data as { details?: Array<{ field?: string; issue?: string }> } | null)?.details;
      if (Array.isArray(normDetails) && normDetails.length) {
        const detail = normDetails
          .map((d) => (d.field && d.issue ? `${d.field}: ${d.issue}` : d.issue || d.field || ''))
          .filter(Boolean)
          .join(' · ');
        if (detail) {
          msg = msg ? `${msg} ${detail}` : detail;
        }
      }
      if (data?.hint && typeof data.hint === 'string') {
        msg = msg ? `${msg} ${data.hint}` : data.hint;
      }
      setMessage(String(msg || 'Normalize & publish failed'));
    } finally {
      setNormalizingId(null);
    }
  };

  return (
    <Card padding="lg">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-lg font-semibold text-[#0b2b43]">Policy document intake</div>
          <div className="text-sm text-[#6b7280] mt-1">
            Upload PDF or DOCX to classify and extract metadata before benefit extraction.
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {!selectionMode ? (
            documents.length > 0 && (
              <Button size="sm" variant="outline" onClick={() => setSelectionMode(true)}>
                Edit
              </Button>
            )
          ) : (
            <>
              {deleteFeedback === 'done' && (
                <span className="text-sm text-green-600">Deleted. List updated.</span>
              )}
              {deleteFeedback === 'error' && (
                <span className="text-sm text-red-600">Delete failed or some documents could not be removed.</span>
              )}
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setSelectionMode(false);
                  setSelectedDocIds(new Set());
                  setDeleteFeedback('idle');
                }}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={selectedDocIds.size === 0 || deleteFeedback === 'deleting'}
                onClick={async () => {
                  if (selectedDocIds.size === 0) return;
                  if (!window.confirm(`Delete ${selectedDocIds.size} selected document(s)?`)) return;
                  if (!window.confirm('Are you sure? This action cannot be undone. Documents referenced by a policy version cannot be deleted.')) return;
                  const ids = Array.from(selectedDocIds);
                  setDeleteFeedback('deleting');
                  setSelectedDocIds(new Set());
                  try {
                    const res = await policyDocumentsAPI.bulkDelete(ids);
                    await loadDocs();
                    onDocumentsChange?.();
                    setDeleteFeedback(res.deleted === ids.length ? 'done' : 'error');
                    if (res.deleted === ids.length) {
                      setSelectionMode(false);
                      setTimeout(() => setDeleteFeedback('idle'), 3000);
                    } else {
                      setTimeout(() => setDeleteFeedback('idle'), 5000);
                    }
                  } catch {
                    await loadDocs();
                    setDeleteFeedback('error');
                    setTimeout(() => setDeleteFeedback('idle'), 5000);
                  }
                }}
              >
                {deleteFeedback === 'deleting' ? 'Deleting…' : 'Delete selected'}
              </Button>
            </>
          )}
        </div>
      </div>

      {message && (
        <div className="mt-4">
          <Alert
            variant={
              message.startsWith('Normalize & publish complete') ||
              message.startsWith('Document uploaded') ||
              message === 'Saved'
                ? 'success'
                : message.includes('Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY')
                  ? 'info'
                  : 'error'
            }
          >
            {message}
          </Alert>
          {uploadRequestId && (
            <div className="text-xs text-[#9ca3af] mt-1 font-mono">Request ID: {uploadRequestId}</div>
          )}
        </div>
      )}

      {health && !uploadReady && (
        <Alert
          variant={
            !health.supabase_url_present || !health.service_role_present || health.config_error
              ? 'info'
              : 'error'
          }
          className="mt-4"
        >
          {!health.supabase_url_present || !health.service_role_present
            ? 'Policy document uploads require Supabase storage. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the backend .env (see project .env.example) to enable uploads.'
            : health.config_error === 'wrong_key_type' || health.bucket_probe?.diagnosis === 'wrong_key_type'
            ? 'Invalid API key: in the backend .env use SUPABASE_URL from your project (e.g. https://xxxxx.supabase.co) and SUPABASE_SERVICE_ROLE_KEY from Supabase → Settings → API (the service_role secret, not the anon key). Restart the backend after changing .env.'
            : health.config_error === 'wrong_project_url_key_mismatch'
            ? 'SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be from the same Supabase project. Check Settings → API and fix .env, then restart the backend.'
            : !health.bucket_access_ok
            ? 'Policy storage bucket is unavailable. In Supabase go to Storage → New bucket, create a bucket named hr-policies (public or private), then reload this page.'
            : !health.policy_documents_table_ok
            ? 'Policy database tables are missing. Run migrations or use a database that has the policy_documents schema.'
            : 'Policy upload is not ready.'}
        </Alert>
      )}

      <div className="flex flex-wrap items-center gap-3 mt-4">
        <input
          ref={fileInputRef}
          type="file"
          accept=".docx,.pdf"
          onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
          className="sr-only"
          aria-label="Choose policy document file"
        />
        <Button
          type="button"
          variant="outline"
          onClick={() => fileInputRef.current?.click()}
          disabled={!uploadReady}
        >
          Choose file
        </Button>
        <span className="text-sm text-[#6b7280] min-w-[8rem]">
          {uploadFile ? uploadFile.name : 'No file selected'}
        </span>
        <Button
          onClick={handleUpload}
          disabled={!uploadFile || !(uploadFile instanceof File) || uploading || !uploadReady}
        >
          {uploading ? 'Uploading…' : 'Upload & classify'}
        </Button>
      </div>

      {documents.length === 0 ? (
        <p className="text-sm text-[#6b7280] mt-4">No documents uploaded.</p>
      ) : (
        <div className="mt-6 space-y-2">
          {documents.map((doc) => {
            const isExpanded = expandedId === doc.id;
            const needsReview = doc.processing_status === 'review_required';
            const isFailed = doc.processing_status === 'failed';
            return (
              <div
                key={doc.id}
                className="border border-[#e2e8f0] rounded-lg overflow-hidden flex items-stretch"
              >
                {selectionMode && (
                  <div className="flex items-center pl-3 border-r border-[#e2e8f0] bg-[#f8fafc]">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-[#cbd5e1]"
                      checked={selectedDocIds.has(doc.id)}
                      onChange={(e) => {
                        e.stopPropagation();
                        setSelectedDocIds((prev) => {
                          const next = new Set(prev);
                          if (e.target.checked) next.add(doc.id);
                          else next.delete(doc.id);
                          return next;
                        });
                      }}
                      onClick={(e) => e.stopPropagation()}
                      aria-label={`Select ${doc.filename}`}
                    />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                <button
                  type="button"
                  onClick={() => !selectionMode && setExpandedId(isExpanded ? null : doc.id)}
                  className="w-full text-left px-4 py-3 flex items-center justify-between gap-4 hover:bg-[#f8fafc]"
                >
                  <div className="flex-1 min-w-0">
                    <span className="font-medium text-[#0b2b43]">{doc.filename}</span>
                    <div className="flex flex-wrap items-center gap-2 mt-1 text-sm text-[#6b7280]">
                      <span>Status: {doc.processing_status}</span>
                      <span>•</span>
                      <span>Type: {DOC_TYPE_LABELS[doc.detected_document_type] || doc.detected_document_type || '-'}</span>
                      <span>•</span>
                      <span>Scope: {SCOPE_LABELS[doc.detected_policy_scope] || doc.detected_policy_scope || '-'}</span>
                      <span>•</span>
                      <span>Uploaded: {formatDateTime(doc.uploaded_at)}</span>
                      {needsReview && (
                        <span className="px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                          Needs review
                        </span>
                      )}
                      {isFailed && doc.extraction_error && (
                        <span className="px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                          {doc.extraction_error.slice(0, 50)}…
                        </span>
                      )}
                    </div>
                  </div>
                  <span className="text-[#6b7280]">{isExpanded ? '▼' : '▶'}</span>
                </button>
                {isExpanded && (
                  <div className="border-t border-[#e2e8f0] bg-[#f8fafc]">
                    <div className="flex border-b border-[#e2e8f0]">
                      <button
                        type="button"
                        onClick={() => setExpandedTab('metadata')}
                        className={`px-4 py-2 text-sm font-medium ${expandedTab === 'metadata' ? 'bg-white border-b-2 border-[#0b2b43] text-[#0b2b43]' : 'text-[#6b7280] hover:text-[#0b2b43]'}`}
                      >
                        Metadata
                      </button>
                      <button
                        type="button"
                        onClick={() => setExpandedTab('structure')}
                        className={`px-4 py-2 text-sm font-medium ${expandedTab === 'structure' ? 'bg-white border-b-2 border-[#0b2b43] text-[#0b2b43]' : 'text-[#6b7280] hover:text-[#0b2b43]'}`}
                      >
                        Document structure
                      </button>
                    </div>
                    <div className="px-4 py-3 space-y-4">
                      {expandedTab === 'metadata' && (
                        <>
                          <DetectedMetadataDisplay metadata={doc.extracted_metadata} />
                          {doc.raw_text && (
                            <div>
                              <div className="text-sm font-medium text-[#0b2b43] mb-1">Extracted text preview</div>
                              <pre className="text-xs text-[#4b5563] bg-white p-3 rounded border overflow-auto max-h-48 whitespace-pre-wrap">
                                {doc.raw_text.slice(0, 2000)}
                                {doc.raw_text.length > 2000 ? '\n\n… (truncated)' : ''}
                              </pre>
                            </div>
                          )}
                          {doc.extraction_error && (
                            <div className="text-sm text-red-600">{doc.extraction_error}</div>
                          )}
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleReprocess(doc.id)}
                              disabled={reprocessingId === doc.id}
                            >
                              {reprocessingId === doc.id ? 'Reprocessing…' : 'Reprocess'}
                            </Button>
                            <Button
                              size="sm"
                              onClick={() => handleNormalize(doc.id)}
                              disabled={normalizingId === doc.id || !doc.raw_text}
                            >
                              {normalizingId === doc.id ? 'Normalize & publish…' : 'Normalize & publish'}
                            </Button>
                          </div>
                        </>
                      )}
                      {expandedTab === 'structure' && (
                        <DocumentStructureTab docId={doc.id} />
                      )}
                    </div>
                  </div>
                )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
