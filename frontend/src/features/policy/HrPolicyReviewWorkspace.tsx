import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Input } from '../../components/antigravity';
import { companyPolicyAPI, policyDocumentsAPI } from '../../api/client';

const VERSION_STATUS_LABELS: Record<string, string> = {
  draft: 'Draft',
  review_required: 'Review required',
  reviewed: 'Reviewed',
  published: 'Published',
  archived: 'Archived',
  auto_generated: 'Auto-generated',
  in_review: 'In review',
  approved: 'Approved',
};

type Meta = Record<string, unknown>;
const meta = (r: any, key: string, def?: number | string | boolean) => {
  const m = (r?.metadata_json || r?.metadata) as Meta | undefined;
  if (!m || typeof m !== 'object') return def;
  const v = m[key];
  return v !== undefined && v !== null ? v : def;
};

function formatBenefitLabel(r: any): string {
  return (meta(r, 'benefit_label') as string) || r?.benefit_key || '—';
}

function formatDateTime(val: string | null | undefined): string {
  if (!val) return '—';
  try {
    return new Date(val).toLocaleString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return String(val);
  }
}

/** Topic labels and display order (must match backend POLICY_THEMES). */
const TOPIC_ORDER: string[] = [
  'immigration', 'travel', 'temporary_housing', 'household_goods', 'schooling',
  'spouse_support', 'family_support', 'banking', 'tax', 'allowances', 'medical',
  'home_leave', 'repatriation', 'compliance', 'documentation', 'misc',
];
const TOPIC_LABELS: Record<string, string> = {
  immigration: 'Immigration',
  travel: 'Travel',
  temporary_housing: 'Temporary housing',
  household_goods: 'Household goods',
  schooling: 'Schooling',
  spouse_support: 'Spouse support',
  family_support: 'Family support',
  banking: 'Banking',
  tax: 'Tax',
  allowances: 'Allowances',
  medical: 'Medical',
  home_leave: 'Home leave',
  repatriation: 'Repatriation',
  compliance: 'Compliance',
  documentation: 'Documentation',
  misc: 'Miscellaneous',
};

type HrPolicyReviewWorkspaceProps = {
  refreshTrigger?: number;
  postNormalizePolicyId?: string | null;
  onBindComplete?: () => void;
  /** Admin context: scope to this company */
  adminCompanyId?: string | null;
};

export const HrPolicyReviewWorkspace: React.FC<HrPolicyReviewWorkspaceProps> = ({
  refreshTrigger = 0,
  postNormalizePolicyId = null,
  onBindComplete,
  adminCompanyId = null,
}) => {
  const [documents, setDocuments] = useState<any[]>([]);
  const [policies, setPolicies] = useState<any[]>([]);
  const [selectedPolicyId, setSelectedPolicyId] = useState<string | null>(null);
  const [normalized, setNormalized] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [messageVariant, setMessageVariant] = useState<'success' | 'error'>('error');
  const [sourceClause, setSourceClause] = useState<any | null>(null);
  const [editingRule, setEditingRule] = useState<any | null>(null);
  const [savingRule, setSavingRule] = useState<string | null>(null);
  const [publishBusy, setPublishBusy] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [renormalizeBusy, setRenormalizeBusy] = useState(false);
  const [expandedTopics, setExpandedTopics] = useState<Set<string>>(new Set());
  const [expandAll, setExpandAll] = useState(false);

  const loadWorkspaceData = React.useCallback(async (policyId: string): Promise<{ normRes: any; dlRes: string | null }> => {
    const [normRes, dlRes] = await Promise.all([
      companyPolicyAPI.getNormalized(policyId).catch(() => null),
      companyPolicyAPI.getDownloadUrl(policyId).then((r) => r?.url ?? null).catch(() => null),
    ]);
    return { normRes, dlRes: dlRes || null };
  }, []);

  const loadDocumentsAndPolicies = React.useCallback(async () => {
    const params = adminCompanyId ? { company_id: adminCompanyId } : undefined;
    const [docsRes, policiesRes] = await Promise.all([
      policyDocumentsAPI.list(params).catch(() => ({ documents: [] })),
      companyPolicyAPI.list(params).catch(() => ({ policies: [] })),
    ]);
    setDocuments(docsRes.documents || []);
    const pols = policiesRes.policies || [];
    setPolicies(pols);
    return pols;
  }, [adminCompanyId]);

  useEffect(() => {
    let cancelled = false;
    const bindPolicyId = postNormalizePolicyId;
    loadDocumentsAndPolicies().then((pols) => {
      if (cancelled) return;
      setSelectedPolicyId((current) => {
        if (bindPolicyId && pols.some((p: any) => p.id === bindPolicyId)) {
          onBindComplete?.();
          return bindPolicyId;
        }
        if (!current && pols.length) return pols[0].id;
        if (current && !pols.some((p: any) => p.id === current) && pols.length) return pols[0].id;
        return current;
      });
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refreshTrigger/adminCompanyId drive reload
  }, [refreshTrigger, adminCompanyId]);

  useEffect(() => {
    if (!selectedPolicyId) {
      setNormalized(null);
      setDownloadUrl(null);
      setDownloadError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setDownloadUrl(null);
    setDownloadError(null);
    loadWorkspaceData(selectedPolicyId)
      .then(({ normRes, dlRes }) => {
        if (cancelled) return;
        setNormalized(normRes);
        setDownloadUrl(dlRes);
        setDownloadError(dlRes ? null : 'Download link could not be generated');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedPolicyId, loadWorkspaceData]);

  const sourceDocId = normalized?.version?.source_policy_document_id;
  const versionStatus = normalized?.version?.status || 'draft';

  const getSourceLink = (objectType: string, objectId: string) => {
    const links = normalized?.source_links || [];
    return links.find((l: any) => l.object_type === objectType && l.object_id === objectId);
  };

  const openSourceClause = async (clauseId: string) => {
    if (!sourceDocId || !clauseId) return;
    try {
      const res = await policyDocumentsAPI.getClause(sourceDocId, clauseId);
      setSourceClause(res.clause);
    } catch {
      setSourceClause(null);
    }
  };

  const handlePatchBenefit = async (ruleId: string, patch: Record<string, any>) => {
    if (!selectedPolicyId) return;
    setMessage('');
    setSavingRule(ruleId);
    try {
      await companyPolicyAPI.patchBenefitRule(selectedPolicyId, ruleId, patch);
      const res = await companyPolicyAPI.getNormalized(selectedPolicyId);
      setNormalized(res);
      setEditingRule(null);
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || 'Update failed');
      setMessageVariant('error');
    } finally {
      setSavingRule(null);
    }
  };

  const STATUS_SUCCESS_LABELS: Record<string, string> = {
    draft: 'Draft saved.',
    review_required: 'Marked for review.',
    reviewed: 'Marked as reviewed.',
  };

  const handleSaveStatus = async (status: string) => {
    if (!selectedPolicyId) return;
    setStatusBusy(true);
    setMessage('');
    try {
      await companyPolicyAPI.patchLatestVersionStatus(selectedPolicyId, { status });
      const res = await companyPolicyAPI.getNormalized(selectedPolicyId);
      setNormalized(res);
      setMessage(STATUS_SUCCESS_LABELS[status] ?? 'Status updated.');
      setMessageVariant('success');
    } catch (err: any) {
      const statusCode = err?.response?.status;
      if (statusCode === 404) {
        const res = await companyPolicyAPI.getNormalized(selectedPolicyId).catch(() => null);
        if (res?.version) {
          setNormalized(res);
          setMessage('This version is no longer current. The page has been refreshed to the latest version.');
          setMessageVariant('success');
          return;
        }
      }
      setMessage(
        statusCode === 404
          ? 'This version is no longer current. The page has been refreshed to the latest version.'
          : err?.response?.data?.detail || 'Status update failed'
      );
      setMessageVariant('error');
    } finally {
      setStatusBusy(false);
    }
  };

  const handlePublish = async () => {
    if (!selectedPolicyId) return;
    setPublishBusy(true);
    setMessage('');
    try {
      await companyPolicyAPI.publishLatestVersion(selectedPolicyId);
      const res = await companyPolicyAPI.getNormalized(selectedPolicyId);
      setNormalized(res);
      setMessage('Version published. Employees will see this policy.');
      setMessageVariant('success');
    } catch (err: any) {
      const statusCode = err?.response?.status;
      if (statusCode === 404) {
        const res = await companyPolicyAPI.getNormalized(selectedPolicyId).catch(() => null);
        if (res?.version) {
          setNormalized(res);
          setMessage('This version is no longer current. The page has been refreshed to the latest version.');
          setMessageVariant('success');
          return;
        }
      }
      setMessage(
        statusCode === 404
          ? 'This version is no longer current. The page has been refreshed to the latest version.'
          : err?.response?.data?.detail || 'Publish failed'
      );
      setMessageVariant('error');
    } finally {
      setPublishBusy(false);
    }
  };

  const handleRenormalize = async () => {
    if (!sourceDocId || !selectedPolicyId) return;
    setRenormalizeBusy(true);
    setMessage('');
    try {
      await policyDocumentsAPI.normalize(sourceDocId);
      const res = await companyPolicyAPI.getNormalized(selectedPolicyId);
      setNormalized(res);
      setMessage('Re-normalization complete. Review the updated benefit matrix.');
      setMessageVariant('success');
      loadDocumentsAndPolicies();
    } catch (err: any) {
      const data = err?.response?.data;
      setMessage(data?.message || data?.detail || 'Re-normalization failed');
      setMessageVariant('error');
    } finally {
      setRenormalizeBusy(false);
    }
  };

  const groupedBenefits = useMemo(() => {
    const rules = normalized?.benefit_rules || [];
    const byCat = rules.reduce(
      (acc: Record<string, any[]>, r: any) => {
        const cat = r.benefit_category || 'misc';
        if (!acc[cat]) acc[cat] = [];
        acc[cat].push(r);
        return acc;
      },
      {} as Record<string, any[]>
    );
    // Return in display order, only topics that have rules
    const ordered: [string, any[]][] = [];
    for (const cat of TOPIC_ORDER) {
      if (byCat[cat]?.length) ordered.push([cat, byCat[cat]]);
    }
    const others = Object.keys(byCat).filter((c) => !TOPIC_ORDER.includes(c));
    for (const c of others) ordered.push([c, byCat[c]]);
    return ordered;
  }, [normalized?.benefit_rules]);

  // Expand first topic when normalized data first loads
  const prevRulesRef = React.useRef<string | null>(null);
  useEffect(() => {
    const key = normalized?.benefit_rules?.length != null ? String(normalized.benefit_rules.length) : null;
    if (key && key !== prevRulesRef.current && groupedBenefits.length > 0) {
      prevRulesRef.current = key;
      setExpandedTopics(new Set([groupedBenefits[0][0]]));
      setExpandAll(false);
    }
    if (!normalized) prevRulesRef.current = null;
  }, [normalized, groupedBenefits]);

  const toggleTopic = (cat: string) => {
    setExpandedTopics((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  const handleExpandAll = () => {
    if (expandAll) {
      setExpandedTopics(new Set());
    } else {
      setExpandedTopics(new Set(groupedBenefits.map(([c]) => c)));
    }
    setExpandAll(!expandAll);
  };

  const avgConfidence = useMemo(() => {
    const rules = normalized?.benefit_rules || [];
    if (!rules.length) return null;
    const sum = rules.reduce((a: number, r: any) => a + (r.confidence ?? 0), 0);
    return Math.round((sum / rules.length) * 100);
  }, [normalized?.benefit_rules]);

  return (
    <div className="space-y-6" data-hr-policy-workspace="v2">
      <div className="text-xl font-semibold text-[#0b2b43]">HR Policy Review Workspace</div>
      <div className="text-sm text-[#6b7280] mb-2">
        Review extracted policy content, edit benefit rules, and publish for employee visibility.
      </div>
      <div className="rounded-lg bg-[#f0fdf4] border border-[#bbf7d0] px-4 py-2 text-xs text-[#166534]">
        <strong>Workflow:</strong> Upload document → Reprocess (if needed) → Normalize into policy version → Review/edit matrix → Publish version
      </div>

      {message && (
        <Alert variant={messageVariant}>{message}</Alert>
      )}

      {/* Compact: Policy selector + actions */}
      <Card padding="lg">
        <div className="text-sm font-semibold text-[#0b2b43] mb-2">Policy & version</div>
        <div className="flex flex-wrap gap-3 items-center">
          <label className="text-sm text-[#6b7280]">Policy:</label>
          <select
            value={selectedPolicyId || ''}
            onChange={(e) => setSelectedPolicyId(e.target.value || null)}
            className="border border-[#e2e8f0] rounded px-2 py-1.5 text-sm"
          >
            <option value="">Select policy</option>
            {policies.map((p) => (
              <option key={p.id} value={p.id}>{p.title || p.id}</option>
            ))}
          </select>
          {downloadUrl && (
            <a className="text-sm text-[#0b2b43] underline" href={downloadUrl} target="_blank" rel="noreferrer">
              Download PDF
            </a>
          )}
          {downloadError && (
            <span className="text-xs text-red-600">{downloadError}</span>
          )}
          {normalized?.version && (
            <>
              <span className="text-xs px-2 py-1 rounded bg-[#e2e8f0]">
                Version {normalized.version.version_number} · {VERSION_STATUS_LABELS[versionStatus] || versionStatus}
              </span>
              <span className="text-xs text-[#6b7280]" title="Normalized at">
                Normalized: {formatDateTime(normalized.version.created_at)}
              </span>
              {versionStatus === 'published' && normalized.version.updated_at && (
                <span className="text-xs text-[#6b7280]" title="Published at">
                  Published: {formatDateTime(normalized.version.updated_at)}
                </span>
              )}
              {avgConfidence != null && (
                <span className={`text-xs px-2 py-1 rounded ${avgConfidence >= 70 ? 'bg-[#d1fae5] text-[#065f46]' : avgConfidence >= 50 ? 'bg-amber-100 text-amber-800' : 'bg-[#e2e8f0]'}`}>
                  Avg confidence: {avgConfidence}%
                </span>
              )}
              <span className="text-xs text-[#6b7280]">
                {normalized.benefit_rules?.length ?? 0} benefits · {normalized.exclusions?.length ?? 0} exclusions · {normalized.evidence_requirements?.length ?? 0} evidence rules
              </span>
              {sourceDocId && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRenormalize}
                  disabled={renormalizeBusy}
                >
                  {renormalizeBusy ? 'Re-normalizing…' : 'Re-run normalization'}
                </Button>
              )}
            </>
          )}
        </div>
        {loading && <div className="text-sm text-[#6b7280] mt-2">Loading…</div>}
        {documents.length > 0 && (
          <div className="text-xs text-[#6b7280] mt-2">
            Source: {documents.length} document{documents.length !== 1 ? 's' : ''}
          </div>
        )}
      </Card>

      {/* Grouped policy matrix by topic */}
      {normalized?.version && (
        <Card padding="lg">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-semibold text-[#0b2b43]">Benefit rules by topic</div>
            <button type="button" onClick={handleExpandAll} className="text-xs text-[#059669] hover:underline">
              {expandAll ? 'Collapse all' : 'Expand all'}
            </button>
          </div>
          {groupedBenefits.length === 0 ? (
            <div className="text-sm text-[#6b7280] py-4">No benefit rules. Upload a document, Reprocess, then Normalize.</div>
          ) : (
          <div className="space-y-2">
            {groupedBenefits.map(([cat, rules]) => {
              const isExpanded = expandedTopics.has(cat);
              const label = TOPIC_LABELS[cat] ?? cat;
              const autoCount = (rules as any[]).filter((r: any) => r.auto_generated).length;
              const manualCount = rules.length - autoCount;
              return (
                <div key={cat} className="border border-[#e2e8f0] rounded-lg overflow-hidden">
                  <button type="button" onClick={() => toggleTopic(cat)} className="w-full text-left px-4 py-3 flex items-center justify-between gap-3 hover:bg-[#f8fafc]">
                    <div className="flex items-center gap-2">
                      <span className="text-[#6b7280]">{isExpanded ? '▼' : '▶'}</span>
                      <span className="font-medium text-[#0b2b43]">{label}</span>
                      <span className="text-xs text-[#6b7280]">{rules.length} rule{rules.length !== 1 ? 's' : ''}{autoCount > 0 ? ` · ${autoCount} auto` : ''}{manualCount > 0 ? ` · ${manualCount} manual` : ''}</span>
                    </div>
                  </button>
                  {isExpanded && (
                  <div className="border-t border-[#e2e8f0] bg-white">
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-[#e2e8f0] bg-[#f8fafc]">
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]">Benefit</th>
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]">Allowed</th>
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]">Value</th>
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]">Unit</th>
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]">Approval</th>
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]">Evidence</th>
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]">Notes</th>
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]">Source</th>
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]"></th>
                </tr>
              </thead>
              <tbody>
                {(rules as any[]).map((r: any) => {
                  const link = getSourceLink('benefit_rule', r.id);
                  const isEditing = editingRule?.id === r.id;
                  const metaVal = (k: string, def?: any) => meta(r, k, def);
                  const allowed = metaVal('allowed', true);
                  const primaryVal = r.amount_value ?? metaVal('standard_value') ?? metaVal('max_value') ?? metaVal('min_value');
                  const capVal = metaVal('max_value') ?? r.amount_value;
                  const approvalReq = metaVal('approval_required', false);
                  const evidenceReq = metaVal('evidence_required', false);
                  const notes = metaVal('hr_notes') ?? r.description ?? '';
                  const unitStr = [r.currency, r.amount_unit].filter(Boolean).join(' ') || '—';
                  const hasNumericCap = typeof capVal === 'number' && capVal > 0;

                  return (
                    <tr key={r.id} className="border-b border-[#e2e8f0] hover:bg-[#f8fafc]">
                      <td className="py-2 px-2">
                        {isEditing ? (
                          <Input
                            value={editingRule ? formatBenefitLabel(editingRule) : formatBenefitLabel(r)}
                            onChange={(val) => setEditingRule({ ...editingRule, metadata_json: { ...(editingRule?.metadata_json || r?.metadata_json || {}), benefit_label: val } })}
                            placeholder="Label"
                          />
                        ) : (
                          <span className={r.auto_generated ? 'text-[#0b2b43]' : 'text-[#059669] font-medium'}>
                            {formatBenefitLabel(r)}
                            {r.auto_generated && <span className="text-[#9ca3af] ml-1">(auto)</span>}
                          </span>
                        )}
                      </td>
                      <td className="py-2 px-2">
                        {isEditing ? (
                          <input
                            type="checkbox"
                            checked={!!(editingRule?.metadata_json ? meta(editingRule, 'allowed', true) : allowed)}
                            onChange={(e) => {
                              const m = editingRule?.metadata_json || r?.metadata_json || {};
                              setEditingRule({ ...editingRule, metadata_json: { ...m, allowed: e.target.checked } });
                            }}
                          />
                        ) : (
                          <span>{allowed ? '✓' : '✗'}</span>
                        )}
                      </td>
                      <td className="py-2 px-2">
                        {isEditing ? (
                          <div className="space-y-1">
                            {hasNumericCap && (
                              <div className="h-2 w-24 bg-[#e2e8f0] rounded-full overflow-hidden">
                                <div className="h-full bg-[#1f8e8b]" style={{ width: `${Math.min(100, ((editingRule?.amount_value ?? primaryVal ?? 0) / (typeof capVal === 'number' ? capVal : 1)) * 100)}%` }} />
                              </div>
                            )}
                            <Input type="number" value={String(editingRule?.amount_value ?? primaryVal ?? '')} onChange={(val) => setEditingRule({ ...editingRule, amount_value: val ? Number(val) : null })} placeholder="—" />
                          </div>
                        ) : (
                          primaryVal != null ? primaryVal : '—'
                        )}
                      </td>
                      <td className="py-2 px-2">
                        {isEditing ? (
                          <div className="flex gap-1">
                            <Input value={editingRule?.currency ?? r.currency ?? ''} onChange={(val) => setEditingRule({ ...editingRule, currency: val })} placeholder="USD" />
                            <Input value={editingRule?.amount_unit ?? r.amount_unit ?? ''} onChange={(val) => setEditingRule({ ...editingRule, amount_unit: val })} placeholder="Unit" />
                          </div>
                        ) : (
                          <span>{unitStr}</span>
                        )}
                      </td>
                      <td className="py-2 px-2">
                        {isEditing ? (
                          <input
                            type="checkbox"
                            checked={!!(editingRule?.metadata_json ? meta(editingRule, 'approval_required', false) : approvalReq)}
                            onChange={(e) => {
                              const m = editingRule?.metadata_json || r?.metadata_json || {};
                              setEditingRule({ ...editingRule, metadata_json: { ...m, approval_required: e.target.checked } });
                            }}
                          />
                        ) : (
                          approvalReq ? 'Yes' : '—'
                        )}
                      </td>
                      <td className="py-2 px-2">
                        {isEditing ? (
                          <input
                            type="checkbox"
                            checked={!!(editingRule?.metadata_json ? meta(editingRule, 'evidence_required', false) : evidenceReq)}
                            onChange={(e) => {
                              const m = editingRule?.metadata_json || r?.metadata_json || {};
                              setEditingRule({ ...editingRule, metadata_json: { ...m, evidence_required: e.target.checked } });
                            }}
                          />
                        ) : (
                          evidenceReq ? 'Yes' : '—'
                        )}
                      </td>
                      <td className="py-2 px-2 max-w-[120px] truncate" title={String(notes)}>
                        {isEditing ? (
                          <Input
                            value={editingRule?.metadata_json ? String(meta(editingRule, 'hr_notes') ?? '') : String(notes)}
                            onChange={(val) => {
                              const m = editingRule?.metadata_json || r?.metadata_json || {};
                              setEditingRule({ ...editingRule, metadata_json: { ...m, hr_notes: val } });
                            }}
                            placeholder="Notes"
                          />
                        ) : (
                          notes || '—'
                        )}
                      </td>
                      <td className="py-2 px-2">
                        {link ? (
                          <button
                            type="button"
                            onClick={() => openSourceClause(link.clause_id)}
                            className="text-xs text-[#059669] hover:underline"
                          >
                            p.{link.source_page_start ?? '?'}
                          </button>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="py-2 px-2">
                        {isEditing ? (
                          <div className="flex gap-1">
                            <Button
                              size="sm"
                              onClick={() => handlePatchBenefit(r.id, {
                                amount_value: editingRule.amount_value,
                                amount_unit: editingRule.amount_unit,
                                currency: editingRule.currency,
                                description: editingRule.description,
                                benefit_key: editingRule.benefit_key,
                                metadata_json: editingRule.metadata_json,
                              })}
                              disabled={savingRule === r.id}
                            >
                              {savingRule === r.id ? 'Saving…' : 'Save'}
                            </Button>
                            <Button variant="outline" size="sm" onClick={() => setEditingRule(null)}>Cancel</Button>
                          </div>
                        ) : (
                          <Button variant="outline" size="sm" onClick={() => setEditingRule(r)}>Edit</Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
                  </div>
                  )}
                </div>
              );
            })}
          </div>
          )}
        </Card>
      )}

      {/* Exclusions & evidence summary */}
      {normalized?.version && (normalized.exclusions?.length > 0 || normalized.evidence_requirements?.length > 0) && (
        <Card padding="lg">
          <div className="text-sm font-semibold text-[#0b2b43] mb-2">Exclusions & evidence</div>
          <div className="space-y-3 text-sm">
            {normalized.exclusions?.length > 0 && (
              <div>
                <div className="text-xs font-medium text-[#6b7280] mb-1">Exclusions</div>
                <div className="flex flex-wrap gap-2">
                  {normalized.exclusions.map((e: any) => (
                    <div key={e.id} className="px-2 py-1 rounded bg-amber-50 border border-amber-200 text-xs">
                      {e.benefit_key && <span className="font-medium">{e.benefit_key}</span>}
                      <span className="text-[#4b5563]"> — {(e.description || e.raw_text || '').slice(0, 60)}{(e.description || e.raw_text || '').length > 60 ? '…' : ''}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {normalized.evidence_requirements?.length > 0 && (
              <div>
                <div className="text-xs font-medium text-[#6b7280] mb-1">Required evidence</div>
                <div className="flex flex-wrap gap-1">
                  {normalized.evidence_requirements.map((ev: any) => (
                    <span key={ev.id} className="px-2 py-0.5 rounded bg-[#f0fdf4] text-[#166534] text-xs">
                      {(Array.isArray(ev.evidence_items_json) ? ev.evidence_items_json : []).join(', ')}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Panel F: Publish controls */}
      {normalized?.version && (
        <Card padding="lg">
          <div className="text-sm font-semibold text-[#0b2b43] mb-2">F. Publish controls</div>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="outline" size="sm" onClick={() => handleSaveStatus('draft')} disabled={statusBusy}>
              {statusBusy ? 'Saving…' : 'Save draft'}
            </Button>
            <Button variant="outline" size="sm" onClick={() => handleSaveStatus('review_required')} disabled={statusBusy}>
              {statusBusy ? 'Saving…' : 'Mark for review'}
            </Button>
            <Button variant="outline" size="sm" onClick={() => handleSaveStatus('reviewed')} disabled={statusBusy}>
              {statusBusy ? 'Saving…' : 'Mark reviewed'}
            </Button>
            <Button size="sm" onClick={handlePublish} disabled={publishBusy || statusBusy || versionStatus === 'published'}>
              {publishBusy ? 'Publishing…' : 'Publish version'}
            </Button>
            {versionStatus === 'published' && (
              <span className="text-sm text-[#059669] font-medium">Published — employees see this policy</span>
            )}
          </div>
          <div className="text-xs text-[#6b7280] mt-2">
            Status: {VERSION_STATUS_LABELS[versionStatus] || versionStatus}. Only published versions are visible to employees.
          </div>
        </Card>
      )}

      {/* Source comparison modal */}
      {sourceClause && (
        <div
          className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
          onClick={(): void => setSourceClause(null)}
          onKeyDown={(e): void => { if (e.key === 'Escape') setSourceClause(null); }}
          role="button"
          tabIndex={0}
          aria-label="Close"
        >
          <div role="presentation" onClick={(e): void => e.stopPropagation()}>
            <Card padding="lg" className="max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col">
            <div className="flex justify-between items-center mb-3">
              <div className="text-sm font-semibold text-[#0b2b43]">View source</div>
              <button type="button" onClick={(): void => setSourceClause(null)} className="text-[#6b7280] hover:text-[#0b2b43]">Close</button>
            </div>
            <div className="text-xs text-[#6b7280] mb-2">
              Page {sourceClause.source_page_start != null ? sourceClause.source_page_start : '?'}
              {sourceClause.source_page_end != null && sourceClause.source_page_end !== sourceClause.source_page_start
                ? `–${sourceClause.source_page_end}` : ''}
              {sourceClause.clause_type && ` · ${sourceClause.clause_type}`}
            </div>
            <pre className="flex-1 overflow-auto text-sm text-[#4b5563] bg-[#f8fafc] p-4 rounded border border-[#e2e8f0] whitespace-pre-wrap">
              {sourceClause.raw_text || '—'}
            </pre>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
};
