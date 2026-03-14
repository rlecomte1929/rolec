import React, { useEffect, useMemo, useState, useRef } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Alert, Button, Card, Input } from '../components/antigravity';
import { hrAPI, employeeAPI, companyPolicyAPI, policyDocumentsAPI } from '../api/client';
import type { AssignmentDetail, AssignmentSummary, PolicyResponse, PolicyServiceComparisonResponse, PolicySpendItem } from '../types';
import { safeNavigate } from '../navigation/safeNavigate';
import { useSelectedCase } from '../contexts/SelectedCaseContext';
import { CaseIncompleteBanner } from '../components/CaseIncompleteBanner';
import { EmployeePolicyView } from '../features/policy/EmployeePolicyView';
import { PolicyServiceComparisonView } from '../features/policy/PolicyServiceComparisonView';
import { PolicyBenefitsTable, type PolicyBenefitRow } from '../features/policy/PolicyBenefitsTable';
import { HrPolicyReviewWorkspace } from '../features/policy/HrPolicyReviewWorkspace';
import { getAuthItem } from '../utils/demo';
import { buildRoute } from '../navigation/routes';

const formatCurrency = (value: number | undefined | null, currency = 'USD') => {
  const safe = typeof value === 'number' && isFinite(value) ? value : 0;
  return safe.toLocaleString('en-US', { style: 'currency', currency, maximumFractionDigits: 0 });
};

const statusBadge = (status: PolicySpendItem['status']) => {
  if (status === 'OVER_LIMIT') return { label: 'OVER LIMIT', classes: 'bg-[#fef2f2] text-[#7a2a2a]' };
  if (status === 'NEAR_LIMIT') return { label: 'NEAR LIMIT', classes: 'bg-[#fff7ed] text-[#9a3412]' };
  return { label: 'ON TRACK', classes: 'bg-[#eaf5f4] text-[#1f8e8b]' };
};

function EmployeePolicyContent() {
  const [assignmentId, setAssignmentId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [policyDoc, setPolicyDoc] = useState<any | null>(null);
  const [benefits, setBenefits] = useState<PolicyBenefitRow[]>([]);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [companyName, setCompanyName] = useState<string | null>(null);
  const [comparison, setComparison] = useState<PolicyServiceComparisonResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    companyPolicyAPI
      .getLatest()
      .then(async (res) => {
        if (cancelled) return;
        setPolicyDoc(res.policy || null);
        setBenefits(res.benefits || []);
        setCompanyName(res.company_name || null);
        if (res.policy?.id) {
          const dl = await companyPolicyAPI.getDownloadUrl(res.policy.id);
          setDownloadUrl(dl.url);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setPolicyDoc(null);
          setBenefits([]);
        }
      });
    employeeAPI
      .getCurrentAssignment()
      .then((res) => {
        if (!cancelled && res?.assignment?.id) setAssignmentId(res.assignment.id);
      })
      .catch((err: any) => {
        if (!cancelled && err?.response?.status !== 401) setError('Unable to load your assignment.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!assignmentId) {
      setComparison(null);
      return;
    }
    employeeAPI
      .getPolicyServiceComparison(assignmentId)
      .then((res) => {
        if (!cancelled) setComparison(res);
      })
      .catch(() => {
        if (!cancelled) setComparison(null);
      });
    return () => { cancelled = true; };
  }, [assignmentId]);

  if (loading) return <div className="text-sm text-[#6b7280] py-8">Loading your policy...</div>;
  if (error) return <Alert variant="error">{error}</Alert>;
  if (!assignmentId && !policyDoc) {
    return (
      <Card padding="lg">
        <p className="text-[#4b5563]">You don't have an active assignment yet. Once your case is assigned, your applicable policy and benefit limits will appear here.</p>
      </Card>
    );
  }
  return (
    <div className="space-y-4">
      {policyDoc && (
        <Card padding="lg">
          <div className="text-lg font-semibold text-[#0b2b43] mb-2">HR Policy summary</div>
          {companyName && (
            <div className="text-sm text-[#4b5563] mb-2">Company: {companyName}</div>
          )}
          <div className="text-sm text-[#6b7280] mb-4">
            Version {policyDoc.version || '—'} • Effective {policyDoc.effective_date ? formatDate(policyDoc.effective_date) : '—'}
          </div>
          {downloadUrl && (
            <a className="text-sm text-[#0b2b43] underline" href={downloadUrl} target="_blank" rel="noreferrer">
              Download policy document
            </a>
          )}
          <div className="mt-4">
            <PolicyBenefitsTable benefits={benefits} />
          </div>
          <div className="text-xs text-[#6b7280] mt-4">
            Informational summary — the policy document remains the source of truth.
          </div>
        </Card>
      )}
      {!policyDoc && assignmentId && <EmployeePolicyView assignmentId={assignmentId} compact={false} />}
      {assignmentId && (
        <Card padding="lg">
          <div className="text-sm font-semibold text-[#0b2b43] mb-2">Your services vs policy</div>
          <div className="text-xs text-[#6b7280] mb-3">
            How your selected services compare to your resolved assignment policy.
          </div>
          <PolicyServiceComparisonView
            comparisons={comparison?.comparisons ?? []}
            resolvedAt={comparison?.resolved_policy?.resolved_at}
            emptyMessage={comparison?.message ?? undefined}
          />
        </Card>
      )}
      <Link to={buildRoute('services')}>
        <Button variant="outline">Back to Services</Button>
      </Link>
    </div>
  );
}

export const HrPolicy: React.FC = () => {
  const role = getAuthItem('relopass_role');
  if (role === 'EMPLOYEE') {
    return (
      <AppShell title="Assignment Package & Limits" subtitle="View your applicable policy and benefit limits.">
        <EmployeePolicyContent />
      </AppShell>
    );
  }
  return (
    <AppShell title="Assignment Package & Limits" subtitle="Understand what is covered, what is capped, and what requires HR approval before proceeding.">
      {/* 1. Policy document intake — primary upload path (creates policy_documents) */}
      <PolicyDocumentIntakeSection />
      {/* 2. HR Policy Review workspace (clauses, normalize, publish) */}
      <div className="mt-8">
        <HrPolicyReviewWorkspace />
      </div>
      {/* 3. Company policy section — legacy company_policies for backward compat */}
      <div className="mt-6">
        <CompanyPolicyDocumentSection />
      </div>
      <div className="mt-8">
        <HrPolicyContent />
      </div>
    </AppShell>
  );
};

function formatDate(val: string | null | undefined): string {
  if (!val) return '—';
  try {
    return new Date(val).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
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

  const MetaRow = ({ label, value }: { label: string; value: React.ReactNode }) => (
    <div className="flex gap-2 py-1 text-sm">
      <span className="text-[#6b7280] min-w-[10rem]">{label}:</span>
      <span className="text-[#0b2b43]">{value ?? '—'}</span>
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
      <span className="text-[#9ca3af]">—</span>
    );

  const BoolBadge = ({ v }: { v: boolean }) => (
    <span className={v ? 'text-[#059669] font-medium' : 'text-[#9ca3af]'}>
      {v ? 'Yes' : 'No'}
    </span>
  );

  return (
    <div>
      <div className="text-sm font-medium text-[#0b2b43] mb-2">Detected metadata</div>
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

/** Compact display of normalized hints (non-authoritative). */
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
      <span className="text-[#166534] font-medium">Hints: </span>
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

// Legacy: superseded by HrPolicyReviewWorkspace. Exported to satisfy noUnusedLocals.
export function NormalizedPolicySectionLegacy() {
  const [policies, setPolicies] = useState<any[]>([]);
  const [selectedPolicyId, setSelectedPolicyId] = useState<string | null>(null);
  const [normalized, setNormalized] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [editingRule, setEditingRule] = useState<any | null>(null);

  useEffect(() => {
    companyPolicyAPI.list().then((res) => {
      setPolicies(res.policies || []);
      if (!selectedPolicyId && res.policies?.length) setSelectedPolicyId(res.policies[0].id);
    }).catch(() => setPolicies([]));
  }, []);

  useEffect(() => {
    if (!selectedPolicyId) { setNormalized(null); return; }
    setLoading(true);
    companyPolicyAPI.getNormalized(selectedPolicyId).then(setNormalized).catch(() => setNormalized(null)).finally(() => setLoading(false));
  }, [selectedPolicyId]);

  const handlePatchBenefit = async (ruleId: string, patch: Record<string, any>) => {
    if (!selectedPolicyId) return;
    setMessage('');
    try {
      await companyPolicyAPI.patchBenefitRule(selectedPolicyId, ruleId, patch);
      const res = await companyPolicyAPI.getNormalized(selectedPolicyId);
      setNormalized(res);
      setEditingRule(null);
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || 'Update failed');
    }
  };

  const getSourceLink = (objectType: string, objectId: string) => {
    const links = normalized?.source_links || [];
    return links.find((l: any) => l.object_type === objectType && l.object_id === objectId);
  };

  const groupedBenefits = (normalized?.benefit_rules || []).reduce(
    (acc: Record<string, any[]>, r: any) => {
      const cat = r.benefit_category || 'other';
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(r);
      return acc;
    },
    {} as Record<string, any[]>
  );

  return (
    <Card padding="lg">
      <div className="text-lg font-semibold text-[#0b2b43]">Normalized policy</div>
      <div className="text-sm text-[#6b7280] mt-1">
        Canonical benefit rules, exclusions, evidence, and conditions from normalized documents.
      </div>
      {message && <Alert variant="error" className="mt-2">{message}</Alert>}
      <div className="mt-4 flex items-center gap-3">
        <label className="text-sm text-[#6b7280]">Policy:</label>
        <select
          value={selectedPolicyId || ''}
          onChange={(e) => setSelectedPolicyId(e.target.value || null)}
          className="border border-[#e2e8f0] rounded px-2 py-1 text-sm"
        >
          <option value="">Select policy</option>
          {policies.map((p) => (
            <option key={p.id} value={p.id}>{p.title || p.id}</option>
          ))}
        </select>
      </div>
      {loading && <div className="text-sm text-[#6b7280] mt-4">Loading…</div>}
      {!loading && selectedPolicyId && !normalized?.version && (
        <div className="text-sm text-[#6b7280] mt-4">No normalized version. Upload a document, Reprocess, then Normalize.</div>
      )}
      {!loading && normalized?.version && (
        <div className="mt-6 space-y-6">
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="px-2 py-1 rounded bg-[#e2e8f0]">
              {normalized.benefit_rules?.length ?? 0} benefits
            </span>
            <span className="px-2 py-1 rounded bg-[#e2e8f0]">
              {normalized.exclusions?.length ?? 0} exclusions
            </span>
            <span className="px-2 py-1 rounded bg-[#e2e8f0]">
              {normalized.evidence_requirements?.length ?? 0} evidence
            </span>
            <span className="px-2 py-1 rounded bg-[#e2e8f0]">
              {normalized.conditions?.length ?? 0} conditions
            </span>
          </div>

          {/* Benefit rules grouped */}
          <div>
            <div className="text-sm font-medium text-[#0b2b43] mb-2">Benefit rules</div>
            <div className="space-y-4">
              {Object.entries(groupedBenefits).map(([cat, rules]) => (
                <div key={cat} className="border border-[#e2e8f0] rounded-lg overflow-hidden">
                  <div className="px-3 py-2 bg-[#f1f5f9] text-sm font-medium text-[#0b2b43]">
                    {cat}
                  </div>
                  <div className="divide-y divide-[#e2e8f0]">
                    {(rules as any[]).map((r: any) => {
                      const link = getSourceLink('benefit_rule', r.id);
                      const isEditing = editingRule?.id === r.id;
                      return (
                        <div key={r.id} className="px-3 py-2 bg-white">
                          <div className="flex justify-between gap-3">
                            <div>
                              <span className="font-medium text-[#0b2b43]">{r.benefit_key}</span>
                              <span className="ml-2 text-xs text-[#6b7280]">
                                {r.calc_type} {r.amount_value != null ? `${r.amount_value}` : ''} {r.amount_unit || ''} {r.currency || ''} {r.frequency || ''}
                              </span>
                              {link && (
                                <span className="ml-2 text-xs text-[#059669]">
                                  p.{link.source_page_start ?? '?'}
                                </span>
                              )}
                            </div>
                            <Button variant="outline" size="sm" onClick={() => setEditingRule(isEditing ? null : r)}>
                              {isEditing ? 'Cancel' : 'Edit'}
                            </Button>
                          </div>
                          {r.description && (
                            <div className="text-xs text-[#6b7280] mt-1 truncate max-w-xl">{r.description}</div>
                          )}
                          {isEditing && (
                            <div className="mt-3 pt-3 border-t border-[#e2e8f0] grid grid-cols-2 md:grid-cols-4 gap-2">
                              <Input
                                label="Amount"
                                type="number"
                                value={editingRule.amount_value ?? ''}
                                onChange={(val) => setEditingRule({ ...editingRule, amount_value: val ? Number(val) : null })}
                              />
                              <Input
                                label="Unit"
                                value={editingRule.amount_unit ?? ''}
                                onChange={(val) => setEditingRule({ ...editingRule, amount_unit: val })}
                              />
                              <Input
                                label="Currency"
                                value={editingRule.currency ?? ''}
                                onChange={(val) => setEditingRule({ ...editingRule, currency: val })}
                              />
                              <Input
                                label="Frequency"
                                value={editingRule.frequency ?? ''}
                                onChange={(val) => setEditingRule({ ...editingRule, frequency: val })}
                              />
                              <div className="col-span-2">
                                <Input
                                  label="Description"
                                  value={editingRule.description ?? ''}
                                  onChange={(val) => setEditingRule({ ...editingRule, description: val })}
                                />
                              </div>
                              <div className="col-span-2 flex gap-2">
                                <Button size="sm" onClick={() => handlePatchBenefit(r.id, { amount_value: editingRule.amount_value, amount_unit: editingRule.amount_unit, currency: editingRule.currency, frequency: editingRule.frequency, description: editingRule.description })}>Save</Button>
                                <Button variant="outline" size="sm" onClick={() => setEditingRule(null)}>Cancel</Button>
                              </div>
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

          {/* Exclusions */}
          {normalized.exclusions?.length > 0 && (
            <div>
              <div className="text-sm font-medium text-[#0b2b43] mb-2">Exclusions</div>
              <div className="border border-[#e2e8f0] rounded-lg divide-y divide-[#e2e8f0]">
                {normalized.exclusions.map((e: any) => (
                  <div key={e.id} className="px-3 py-2">
                    <span className="text-xs px-2 py-0.5 rounded bg-amber-100 text-amber-800">{e.domain}</span>
                    {e.benefit_key && <span className="ml-2 text-xs text-[#6b7280]">{e.benefit_key}</span>}
                    <div className="text-sm text-[#4b5563] mt-1">{e.description || e.raw_text?.slice(0, 100)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Evidence */}
          {normalized.evidence_requirements?.length > 0 && (
            <div>
              <div className="text-sm font-medium text-[#0b2b43] mb-2">Evidence requirements</div>
              <div className="border border-[#e2e8f0] rounded-lg divide-y divide-[#e2e8f0]">
                {normalized.evidence_requirements.map((ev: any) => (
                  <div key={ev.id} className="px-3 py-2">
                    <span className="text-xs text-[#6b7280]">
                      {(Array.isArray(ev.evidence_items_json) ? ev.evidence_items_json : []).join(', ')}
                    </span>
                    {ev.description && <div className="text-sm mt-1">{ev.description}</div>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Conditions */}
          {normalized.conditions?.length > 0 && (
            <div>
              <div className="text-sm font-medium text-[#0b2b43] mb-2">Conditions</div>
              <div className="flex flex-wrap gap-2">
                {normalized.conditions.map((c: any) => (
                  <span key={c.id} className="px-2 py-1 rounded bg-[#f0fdf4] text-xs text-[#166534]">
                    {c.condition_type}: {JSON.stringify(c.condition_value_json || {})}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

const UPLOAD_ERROR_MESSAGES: Record<string, string> = {
  storage_missing_service_role: 'Policy upload is not configured correctly. Contact support.',
  storage_missing_url: 'Policy upload is not configured correctly. Contact support.',
  storage_bucket_not_found: 'Policy storage bucket is unavailable.',
  storage_upload_failed: 'Upload failed. Please try again.',
  storage_access_denied: 'Policy storage access denied.',
  policy_documents_table_missing: 'Policy database tables are missing.',
  policy_document_clauses_table_missing: 'Policy database tables are missing.',
  policy_versions_table_missing: 'Policy database tables are missing.',
  resolved_assignment_policies_table_missing: 'Policy database tables are missing.',
  db_insert_failed: 'Policy database tables are missing.',
  invalid_file_type: 'Only .docx or .pdf supported.',
};

function getUploadErrorMessage(err: unknown): string {
  const data = err && typeof err === 'object' && 'response' in err
    ? (err as { response?: { data?: { error_code?: string; message?: string; detail?: string } } }).response?.data
    : null;
  const code = data?.error_code;
  if (code && UPLOAD_ERROR_MESSAGES[code]) return UPLOAD_ERROR_MESSAGES[code];
  if (data?.message && typeof data.message === 'string') return data.message;
  if (data?.detail && typeof data.detail === 'string') return data.detail;
  return 'Upload failed. Please try again.';
}

function PolicyDocumentIntakeSection() {
  const [documents, setDocuments] = useState<any[]>([]);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expandedTab, setExpandedTab] = useState<'metadata' | 'structure'>('metadata');
  const [reprocessingId, setReprocessingId] = useState<string | null>(null);
  const [normalizingId, setNormalizingId] = useState<string | null>(null);
  const [health, setHealth] = useState<{
    bucket_access_ok: boolean;
    policy_documents_table_ok: boolean;
    supabase_url_present?: boolean;
    service_role_present?: boolean;
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadDocs = async () => {
    try {
      const res = await policyDocumentsAPI.list();
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

  const uploadReady = health === null || (health.bucket_access_ok && health.policy_documents_table_ok);

  useEffect(() => {
    loadDocs();
    loadHealth();
  }, []);

  const handleUpload = async () => {
    if (!uploadFile) return;
    setMessage('');
    setUploading(true);
    try {
      await policyDocumentsAPI.upload(uploadFile);
      setUploadFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      await loadDocs();
    } catch (err: unknown) {
      setMessage(getUploadErrorMessage(err));
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
      setMessage(`Normalized: ${res.summary?.benefit_rules ?? 0} benefits, ${res.summary?.exclusions ?? 0} exclusions`);
      await loadDocs();
    } catch (err: unknown) {
      const detail = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : null;
      setMessage(String(detail || 'Normalize failed'));
    } finally {
      setNormalizingId(null);
    }
  };

  return (
    <Card padding="lg">
      <div className="text-lg font-semibold text-[#0b2b43]">Policy document intake</div>
      <div className="text-sm text-[#6b7280] mt-1">
        Upload PDF or DOCX to classify and extract metadata before benefit extraction.
      </div>

      {message && (
        <Alert variant={message.startsWith('Normalized') ? 'success' : message === 'Saved' ? 'success' : 'error'} className="mt-4">{message}</Alert>
      )}

      {health && !uploadReady && (
        <Alert variant="error" className="mt-4">
          {!health.supabase_url_present || !health.service_role_present
            ? 'Policy upload is not configured correctly. Contact support.'
            : !health.bucket_access_ok
            ? 'Policy storage bucket is unavailable.'
            : !health.policy_documents_table_ok
            ? 'Policy database tables are missing.'
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
          disabled={!uploadFile || uploading || !uploadReady}
        >
          {uploading ? 'Uploading…' : 'Upload & classify'}
        </Button>
      </div>

      {documents.length === 0 ? (
        <p className="text-sm text-[#6b7280] mt-4">No documents uploaded yet.</p>
      ) : (
        <div className="mt-6 space-y-2">
          {documents.map((doc) => {
            const isExpanded = expandedId === doc.id;
            const needsReview = doc.processing_status === 'review_required';
            const isFailed = doc.processing_status === 'failed';
            return (
              <div
                key={doc.id}
                className="border border-[#e2e8f0] rounded-lg overflow-hidden"
              >
                <button
                  type="button"
                  onClick={() => setExpandedId(isExpanded ? null : doc.id)}
                  className="w-full text-left px-4 py-3 flex items-center justify-between gap-4 hover:bg-[#f8fafc]"
                >
                  <div className="flex-1 min-w-0">
                    <span className="font-medium text-[#0b2b43]">{doc.filename}</span>
                    <div className="flex flex-wrap items-center gap-2 mt-1 text-sm text-[#6b7280]">
                      <span>Status: {doc.processing_status}</span>
                      <span>•</span>
                      <span>Type: {DOC_TYPE_LABELS[doc.detected_document_type] || doc.detected_document_type || '—'}</span>
                      <span>•</span>
                      <span>Scope: {SCOPE_LABELS[doc.detected_policy_scope] || doc.detected_policy_scope || '—'}</span>
                      <span>•</span>
                      <span>{formatDate(doc.uploaded_at)}</span>
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
                              {normalizingId === doc.id ? 'Normalizing…' : 'Normalize now'}
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
            );
          })}
        </div>
      )}
    </Card>
  );
}

function CompanyPolicyDocumentSection() {
  const [policies, setPolicies] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedPolicy, setSelectedPolicy] = useState<any | null>(null);
  const [benefits, setBenefits] = useState<PolicyBenefitRow[]>([]);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);

  const loadPolicies = async () => {
    setLoading(true);
    try {
      const res = await companyPolicyAPI.list();
      setPolicies(res.policies || []);
      const first = res.policies?.[0];
      setSelectedId(first?.id || null);
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || 'Unable to load policies');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPolicies();
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    companyPolicyAPI.getById(selectedId).then(async (res) => {
      setSelectedPolicy(res.policy);
      setBenefits(res.benefits || []);
      const dl = await companyPolicyAPI.getDownloadUrl(selectedId);
      setDownloadUrl(dl.url);
    }).catch(() => {
      setSelectedPolicy(null);
      setBenefits([]);
    });
  }, [selectedId]);

  const handleExtract = async () => {
    if (!selectedId) return;
    setMessage('');
    try {
      const res = await companyPolicyAPI.extract(selectedId);
      setBenefits(res.benefits || []);
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || 'Extraction failed');
    }
  };

  const handleSave = async () => {
    if (!selectedId) return;
    setMessage('');
    try {
      const res = await companyPolicyAPI.saveBenefits(selectedId, benefits);
      setBenefits(res.benefits || []);
      setMessage('Saved');
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || 'Save failed');
    }
  };

  return (
    <Card padding="lg">
      {/* Primary upload path: Policy document intake above */}
      <div className="rounded-lg bg-[#f0fdf4] border border-[#bbf7d0] px-4 py-3 mb-6">
        <div className="text-sm font-medium text-[#166534]">For full pipeline (clauses, normalize, publish), use Policy document intake above.</div>
        <div className="text-xs text-[#15803d] mt-1">
          Upload PDF/DOCX there, then Reprocess → Normalize → Publish in HR Policy Review.
        </div>
      </div>

      {message && <Alert variant={message === 'Saved' ? 'success' : 'error'} className="mt-4">{message}</Alert>}

      {/* Current policy metadata (legacy company_policies from normalize or old flow) */}
      {selectedPolicy && (
        <div className="mt-6 p-4 rounded-lg bg-[#f8fafc] border border-[#e2e8f0]">
          <div className="text-sm font-medium text-[#0b2b43] mb-2">Current policy version</div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-sm text-[#4b5563]">
            <div><span className="text-[#6b7280]">Policy:</span> {selectedPolicy.title || '—'}</div>
            <div><span className="text-[#6b7280]">Version:</span> {selectedPolicy.version || '—'}</div>
            <div><span className="text-[#6b7280]">Effective:</span> {formatDate(selectedPolicy.effective_date)}</div>
            <div><span className="text-[#6b7280]">Upload date:</span> {formatDate(selectedPolicy.created_at)}</div>
            <div><span className="text-[#6b7280]">Status:</span> {selectedPolicy.extraction_status || 'pending'}</div>
          </div>
        </div>
      )}

      {/* Section B: Extracted benefits table */}
      <div className="mt-6 border-t border-[#e2e8f0] pt-4">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <div className="text-sm text-[#6b7280]">Current policy</div>
            {loading && <div className="text-sm text-[#6b7280]">Loading…</div>}
            {!loading && policies.length === 0 && <div className="text-sm text-[#6b7280]">No policy uploaded yet.</div>}
            {!loading && policies.length > 0 && (
              <select
                value={selectedId || ''}
                onChange={(e) => setSelectedId(e.target.value)}
                className="mt-1 border border-[#e2e8f0] rounded-md px-2 py-1 text-sm"
              >
                {policies.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title} {p.version ? `v${p.version}` : ''}
                  </option>
                ))}
              </select>
            )}
          </div>
          <div className="flex items-center gap-2">
            {downloadUrl && (
              <a className="text-sm text-[#0b2b43] underline" href={downloadUrl} target="_blank" rel="noreferrer">
                Download policy
              </a>
            )}
            <Button variant="outline" onClick={handleExtract} disabled={!selectedId}>
              Extract benefits
            </Button>
          </div>
        </div>

        {benefits.length > 0 && (
          <div className="mt-6">
            <div className="text-sm font-medium text-[#0b2b43] mb-2">Extracted benefits table</div>
            <PolicyBenefitsTable benefits={benefits} editable onChange={setBenefits} onSave={handleSave} />
            <div className="text-xs text-[#6b7280] mt-4">
              Informational summary — policy document remains the source of truth.
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

function HrPolicyContent() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { selectedCaseId } = useSelectedCase();
  const [_assignments, setAssignments] = useState<AssignmentSummary[]>([]);
  const [assignment, setAssignment] = useState<AssignmentDetail | null>(null);
  const [policy, setPolicy] = useState<PolicyResponse | null>(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [exceptionCategory, setExceptionCategory] = useState('');
  const [exceptionReason, setExceptionReason] = useState('');
  const [exceptionAmount, setExceptionAmount] = useState('');
  const [exceptionOpen, setExceptionOpen] = useState(false);
  const [resolvedPolicy, setResolvedPolicy] = useState<any | null>(null);
  const [resolvedLoading, setResolvedLoading] = useState(false);
  const [recomputeBusy, setRecomputeBusy] = useState(false);
  const [comparison, setComparison] = useState<PolicyServiceComparisonResponse | null>(null);

  const caseId = searchParams.get('caseId') || selectedCaseId || '';

  const loadAssignments = async () => {
    try {
      const data = await hrAPI.listAssignments();
      setAssignments(data);
      if (!caseId && data.length > 0) {
        const nextId = data[0].id;
        localStorage.setItem('relopass_last_assignment_id', nextId);
        setSearchParams({ caseId: nextId });
      }
      setError('');
    } catch (err: any) {
      if (err.response?.status === 401) {
        safeNavigate(navigate, 'landing');
      } else {
        setError('Unable to load assignments.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const loadPolicy = async (id: string) => {
    if (!id) return;
    setIsLoading(true);
    try {
      const [assignmentData, policyData] = await Promise.all([
        hrAPI.getAssignment(id),
        hrAPI.getPolicy(id),
      ]);
      setAssignment(assignmentData);
      setPolicy(policyData);
      localStorage.setItem('relopass_last_assignment_id', id);
    } catch (err: any) {
      if (err.response?.status === 401) {
        safeNavigate(navigate, 'landing');
      } else if (err.response?.status === 405) {
        setError('Unable to load policy details. The API is outdated (GET /api/hr/assignments/{id} missing). Please deploy the latest backend.');
      } else {
        setError('Unable to load policy details.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAssignments();
  }, []);

  useEffect(() => {
    if (caseId) loadPolicy(caseId);
  }, [caseId]);

  useEffect(() => {
    if (!assignment?.id) {
      setResolvedPolicy(null);
      setComparison(null);
      return;
    }
    setResolvedLoading(true);
    hrAPI
      .getResolvedPolicy(assignment.id)
      .then((r) => setResolvedPolicy(r))
      .catch(() => setResolvedPolicy(null))
      .finally(() => setResolvedLoading(false));
  }, [assignment?.id]);

  useEffect(() => {
    if (!assignment?.id) return;
    hrAPI
      .getPolicyServiceComparison(assignment.id)
      .then((r) => setComparison(r))
      .catch(() => setComparison(null));
  }, [assignment?.id]);

  const handleRecomputeResolved = async () => {
    if (!assignment?.id) return;
    setRecomputeBusy(true);
    try {
      const r = await hrAPI.recomputeResolvedPolicy(assignment.id);
      setResolvedPolicy({
        resolved: r.resolved,
        policy_version: r.policy_version,
        resolution_context: (r.resolved as Record<string, unknown>)?.resolution_context,
      });
    } catch {
      setResolvedPolicy(null);
    } finally {
      setRecomputeBusy(false);
    }
  };

  const profile = assignment?.profile;
  const routeLabel = profile?.movePlan?.origin && profile?.movePlan?.destination
    ? `${profile.movePlan.origin} → ${profile.movePlan.destination}`
    : 'Relocation route';
  const familySize = 1 + (profile?.spouse?.fullName ? 1 : 0) + (profile?.dependents?.length || 0);
  const exceptionPending = policy?.exceptions?.some?.((exc) => exc.status === 'PENDING') ?? false;

  const coverageItems = useMemo(() => {
    if (!policy) return [];
    return Object.entries(policy.spend).map(([key, item]) => ({
      key,
      ...item,
    }));
  }, [policy]);

  const handleRequestException = async () => {
    if (!caseId || !exceptionCategory) return;
    try {
      await hrAPI.requestPolicyException(caseId, {
        category: exceptionCategory,
        reason: exceptionReason,
        amount: exceptionAmount ? Number(exceptionAmount) : undefined,
      });
      setExceptionOpen(false);
      setExceptionReason('');
      setExceptionAmount('');
      loadPolicy(caseId);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Unable to submit exception.');
    }
  };

  return (
    <>
      {error && <Alert variant="error">{error}</Alert>}
      <div className="flex items-center justify-between mb-4">
        <span />
        <Link
          to={buildRoute('hrPolicyManagement')}
          className="text-sm font-medium text-[#0b2b43] hover:underline px-3 py-2 rounded-lg border border-[#0b2b43] bg-white"
        >
          Manage policies →
        </Link>
      </div>
      {isLoading && <div className="text-sm text-[#6b7280]">Loading policy...</div>}

      {!isLoading && !caseId && (
        <Card padding="lg">
          <div className="text-sm text-[#4b5563] mb-4">Select a case from the HR Dashboard to view its policy.</div>
          <Link to={buildRoute('hrPolicyManagement')}>
            <Button>Create or edit policies</Button>
          </Link>
        </Card>
      )}

      {!isLoading && caseId && !policy && !error && (
        <Card padding="lg">
          <div className="text-sm text-[#4b5563]">Policy data is not available for this case.</div>
        </Card>
      )}

      {!isLoading && policy && assignment && (
        <div className="mb-4">
          <CaseIncompleteBanner assignment={assignment} />
        </div>
      )}

      {/* Resolved assignment policy (from published company policy) */}
      {!isLoading && assignment && (
        <Card padding="lg" className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <div>
              <div className="text-sm font-semibold text-[#0b2b43]">Resolved policy package</div>
              <div className="text-xs text-[#6b7280]">
                Applicable benefits for this assignment from published company policy
              </div>
            </div>
            <Button variant="outline" size="sm" onClick={handleRecomputeResolved} disabled={recomputeBusy || resolvedLoading}>
              {recomputeBusy ? 'Recomputing…' : 'Recompute'}
            </Button>
          </div>
          {resolvedLoading && <div className="text-sm text-[#6b7280] py-2">Loading…</div>}
          {!resolvedLoading && resolvedPolicy?.resolved && (
            <div className="space-y-2 text-sm">
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="px-2 py-1 rounded bg-[#e2e8f0]">
                  Version {resolvedPolicy.policy_version?.version_number ?? '—'} · Resolved {resolvedPolicy.resolved?.resolved_at ? new Date(resolvedPolicy.resolved.resolved_at).toLocaleString() : '—'}
                </span>
                {resolvedPolicy.resolution_context && (
                  <span className="px-2 py-1 rounded bg-[#f0fdf4] text-[#166534]">
                    {resolvedPolicy.resolution_context.assignment_type} · {resolvedPolicy.resolution_context.family_status}
                  </span>
                )}
              </div>
              <div className="border border-[#e2e8f0] rounded divide-y divide-[#e2e8f0] max-h-48 overflow-y-auto">
                {(resolvedPolicy.resolved?.benefits || []).map((b: any) => (
                  <div key={b.benefit_key} className="px-3 py-2 flex justify-between items-center">
                    <span className={b.included ? 'text-[#0b2b43]' : 'text-[#6b7280] line-through'}>
                      {String(b.benefit_key).replace(/_/g, ' ')}
                    </span>
                    <span className="text-xs text-[#6b7280]">
                      {b.included
                        ? `${b.currency || 'USD'} ${(b.max_value ?? b.standard_value ?? '—')}${b.approval_required ? ' · Approval req.' : ''}`
                        : 'Excluded'}
                    </span>
                  </div>
                ))}
              </div>
              {(!resolvedPolicy.resolved?.benefits?.length) && (
                <p className="text-[#6b7280]">No benefits resolved. Publish a policy in HR Policy Review and recompute.</p>
              )}
            </div>
          )}
          {!resolvedLoading && resolvedPolicy?.message && !resolvedPolicy?.resolved && (
            <p className="text-sm text-[#6b7280]">{resolvedPolicy.message}</p>
          )}
        </Card>
      )}

      {/* Service vs policy comparison (HR) */}
      {!isLoading && assignment && (
        <Card padding="lg" className="mb-4">
          <div className="text-sm font-semibold text-[#0b2b43] mb-2">Service vs policy comparison</div>
          <div className="text-xs text-[#6b7280] mb-3">
            Compare employee selected services against resolved policy. Highlights mismatches and approval-required items.
          </div>
          <PolicyServiceComparisonView
            comparisons={comparison?.comparisons ?? []}
            resolvedAt={comparison?.resolved_policy?.resolved_at}
            showDiagnostics={true}
            diagnostics={comparison?.diagnostics}
            emptyMessage={comparison?.message}
          />
        </Card>
      )}

      {!isLoading && policy && assignment && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-3">
              <span className="text-xs px-3 py-1 rounded-full border border-[#e2e8f0] text-[#4b5563]">
                {routeLabel}
              </span>
              <span className="text-xs px-3 py-1 rounded-full border border-[#e2e8f0] text-[#4b5563]">
                Family size: {familySize}
              </span>
              <span className="text-xs px-3 py-1 rounded-full border border-[#e2e8f0] text-[#4b5563]">
                Policy: {policy.policy?.policyVersion ?? '—'}
              </span>
              <span className="text-xs px-3 py-1 rounded-full border border-[#e2e8f0] text-[#4b5563]">
                HR owner: {assignment.employeeIdentifier || 'HR'}
              </span>
            </div>
            <div className="text-xs text-[#6b7280]">
              Effective: {policy.policy?.effectiveDate ? new Date(policy.policy.effectiveDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}
            </div>
          </div>

          {exceptionPending && (
            <Card padding="md" className="bg-[#eef4ff] border border-[#c7d8ff]">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                  <div className="text-sm font-semibold text-[#0b2b43]">Policy Exceptions Pending</div>
                  <div className="text-xs text-[#4b5563]">
                    You have pending exception requests that require HR approval before submission.
                  </div>
                </div>
                <Button variant="outline">View details</Button>
              </div>
            </Card>
          )}

          <div className="flex items-center justify-between">
            <div className="text-lg font-semibold text-[#0b2b43]">Your Coverage Envelope</div>
            <div className="text-xs text-[#6b7280]">Policy exceptions: {policy.exceptions?.length ?? 0}</div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
            {coverageItems.map((item) => {
              const badge = statusBadge(item.status);
              const barPercent = item.cap ? Math.min(100, Math.round((item.used / item.cap) * 100)) : 0;
              return (
                <Card key={item.key} padding="md">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-semibold text-[#0b2b43]">{item.title}</div>
                    <span className={`text-xs px-2 py-1 rounded-full ${badge.classes}`}>{badge.label}</span>
                  </div>
                  <div className="mt-4 text-xs text-[#6b7280] flex items-center justify-between">
                    <span>Used</span>
                    <span className="text-[#0b2b43] font-semibold">
                      {formatCurrency(item.used, item.currency)}
                    </span>
                  </div>
                  <div className="mt-2 h-2 w-full bg-[#e2e8f0] rounded-full overflow-hidden">
                    <div
                      className={`h-full ${item.status === 'OVER_LIMIT' ? 'bg-[#ef4444]' : item.status === 'NEAR_LIMIT' ? 'bg-[#f59e0b]' : 'bg-[#1f8e8b]'}`}
                      style={{ width: `${barPercent}%` }}
                    />
                  </div>
                  <div className="mt-2 text-xs text-[#6b7280] flex items-center justify-between">
                    <span>Cap: {formatCurrency(item.cap, item.currency)}</span>
                    <span>Remaining: {formatCurrency(item.remaining, item.currency)}</span>
                  </div>
                  <div className="mt-3 flex items-center justify-between text-xs">
                    <button className="text-[#0b2b43]">View rules</button>
                    {(item.status === 'OVER_LIMIT' || item.status === 'NEAR_LIMIT') && (
                      <button
                        className="text-[#7a2a2a]"
                        onClick={() => {
                          setExceptionCategory(item.key);
                          setExceptionOpen(true);
                        }}
                      >
                        Request exception
                      </button>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>

          <Card padding="lg">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-sm font-semibold text-[#0b2b43]">Detailed Policy Rules</div>
                <div className="text-xs text-[#6b7280]">Policy logic and required evidence by category.</div>
              </div>
              <span className="text-xs text-[#6b7280]">Read-only</span>
            </div>
            <div className="space-y-3">
              {coverageItems.map((item) => (
                <details key={`rule-${item.key}`} className="border border-[#e2e8f0] rounded-lg p-4">
                  <summary className="flex items-center justify-between cursor-pointer">
                    <div>
                      <div className="text-sm font-semibold text-[#0b2b43]">{item.title} Rules</div>
                      <div className="text-xs text-[#6b7280]">
                        Cap: {formatCurrency(item.cap, item.currency)} · Approval: {policy.policy?.approvalRules?.['overLimit'] ?? 'Standard'}
                      </div>
                    </div>
                    <span className="text-xs text-[#6b7280]">View</span>
                  </summary>
                  <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4 text-xs text-[#4b5563]">
                    <div className="space-y-2">
                      <div>Condition: Applies to all cases requiring {item.title.toLowerCase()} support.</div>
                      <div>Cap logic: Spend must remain within policy cap or request an exception.</div>
                      <div>Enforcement: {item.status === 'OVER_LIMIT' ? 'HARD BLOCK' : 'SOFT WARNING'}.</div>
                    </div>
                    <div className="border border-[#e2e8f0] rounded-lg p-3 bg-[#f8fafc]">
                      <div className="text-xs font-semibold text-[#0b2b43]">Required evidence</div>
                      <ul className="mt-2 space-y-1">
                        {(policy.policy?.requiredEvidence?.[item.key] ?? []).map((evidence) => (
                          <li key={evidence}>• {evidence}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </details>
              ))}
            </div>
          </Card>
        </div>
      )}

      {exceptionOpen && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
          <Card padding="lg" className="w-full max-w-lg">
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm font-semibold text-[#0b2b43]">Request policy exception</div>
              <button
                onClick={() => setExceptionOpen(false)}
                className="text-sm text-[#6b7280] hover:text-[#0b2b43]"
              >
                Close
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <div className="text-xs uppercase tracking-wide text-[#6b7280] mb-2">Category</div>
                <div className="text-sm text-[#0b2b43] capitalize">{exceptionCategory}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-[#6b7280] mb-2">Amount requested</div>
                <input
                  value={exceptionAmount}
                  onChange={(event) => setExceptionAmount(event.target.value)}
                  placeholder="Enter amount"
                  className="w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
                />
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-[#6b7280] mb-2">Reason</div>
                <textarea
                  value={exceptionReason}
                  onChange={(event) => setExceptionReason(event.target.value)}
                  rows={3}
                  className="w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
                />
              </div>
              <div className="flex items-center justify-end gap-2">
                <Button variant="outline" onClick={() => setExceptionOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleRequestException}>Submit request</Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
