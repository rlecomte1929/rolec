import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Input } from '../../components/antigravity';
import { companyPolicyAPI, policyDocumentsAPI } from '../../api/client';

const formatDate = (val: string | null | undefined): string => {
  if (!val) return '—';
  try {
    return new Date(val).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return val;
  }
};

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

export const HrPolicyReviewWorkspace: React.FC = () => {
  const [documents, setDocuments] = useState<any[]>([]);
  const [policies, setPolicies] = useState<any[]>([]);
  const [selectedPolicyId, setSelectedPolicyId] = useState<string | null>(null);
  const [normalized, setNormalized] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [sourceClause, setSourceClause] = useState<any | null>(null);
  const [editingRule, setEditingRule] = useState<any | null>(null);
  const [savingRule, setSavingRule] = useState<string | null>(null);
  const [publishBusy, setPublishBusy] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);

  const loadDocuments = async () => {
    try {
      const res = await policyDocumentsAPI.list();
      setDocuments(res.documents || []);
    } catch {
      setDocuments([]);
    }
  };

  const loadPolicies = async () => {
    try {
      const res = await companyPolicyAPI.list();
      setPolicies(res.policies || []);
      if (!selectedPolicyId && res.policies?.length) {
        setSelectedPolicyId(res.policies[0].id);
      }
    } catch {
      setPolicies([]);
    }
  };

  useEffect(() => {
    loadDocuments();
    loadPolicies();
  }, []);

  useEffect(() => {
    if (!selectedPolicyId) {
      setNormalized(null);
      return;
    }
    setLoading(true);
    companyPolicyAPI
      .getNormalized(selectedPolicyId)
      .then(setNormalized)
      .catch(() => setNormalized(null))
      .finally(() => setLoading(false));
  }, [selectedPolicyId]);

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
    } finally {
      setSavingRule(null);
    }
  };

  const handleSaveStatus = async (status: string) => {
    if (!selectedPolicyId || !normalized?.version?.id) return;
    setStatusBusy(true);
    setMessage('');
    try {
      await companyPolicyAPI.patchVersionStatus(selectedPolicyId, normalized.version.id, { status });
      const res = await companyPolicyAPI.getNormalized(selectedPolicyId);
      setNormalized(res);
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || 'Status update failed');
    } finally {
      setStatusBusy(false);
    }
  };

  const handlePublish = async () => {
    if (!selectedPolicyId || !normalized?.version?.id) return;
    setPublishBusy(true);
    setMessage('');
    try {
      await companyPolicyAPI.publishVersion(selectedPolicyId, normalized.version.id);
      const res = await companyPolicyAPI.getNormalized(selectedPolicyId);
      setNormalized(res);
      setMessage('Version published. Employees will see this policy.');
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || 'Publish failed');
    } finally {
      setPublishBusy(false);
    }
  };

  const groupedBenefits = useMemo(() => {
    const rules = normalized?.benefit_rules || [];
    return rules.reduce(
      (acc: Record<string, any[]>, r: any) => {
        const cat = r.benefit_category || 'other';
        if (!acc[cat]) acc[cat] = [];
        acc[cat].push(r);
        return acc;
      },
      {} as Record<string, any[]>
    );
  }, [normalized?.benefit_rules]);

  const avgConfidence = useMemo(() => {
    const rules = normalized?.benefit_rules || [];
    if (!rules.length) return null;
    const sum = rules.reduce((a: number, r: any) => a + (r.confidence ?? 0), 0);
    return Math.round((sum / rules.length) * 100);
  }, [normalized?.benefit_rules]);

  return (
    <div className="space-y-6">
      <div className="text-xl font-semibold text-[#0b2b43]">HR Policy Review Workspace</div>
      <div className="text-sm text-[#6b7280]">
        Review extracted policy content, edit benefit rules, and publish for employee visibility.
      </div>

      {message && (
        <Alert variant={message.includes('published') ? 'success' : 'error'}>{message}</Alert>
      )}

      {/* Panel A: Source documents */}
      <Card padding="lg">
        <div className="text-sm font-semibold text-[#0b2b43] mb-2">A. Source documents</div>
        <div className="text-xs text-[#6b7280] mb-3">Uploaded policy documents used for extraction</div>
        {documents.length === 0 ? (
          <div className="text-sm text-[#6b7280] py-2">No documents uploaded. Upload in the Policy document intake section above.</div>
        ) : (
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {documents.map((d) => (
              <div key={d.id} className="flex items-center justify-between py-1.5 text-sm border-b border-[#e2e8f0] last:border-0">
                <span className="text-[#0b2b43]">{d.filename}</span>
                <span className="text-xs text-[#6b7280]">
                  {d.processing_status} · {formatDate(d.uploaded_at)}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Panel B: Extraction status and confidence */}
      <Card padding="lg">
        <div className="text-sm font-semibold text-[#0b2b43] mb-2">B. Extraction status and confidence</div>
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
          {normalized?.version && (
            <>
              <span className="text-xs px-2 py-1 rounded bg-[#e2e8f0]">
                Version {normalized.version.version_number} · {VERSION_STATUS_LABELS[versionStatus] || versionStatus}
              </span>
              {avgConfidence != null && (
                <span className={`text-xs px-2 py-1 rounded ${avgConfidence >= 70 ? 'bg-[#d1fae5] text-[#065f46]' : avgConfidence >= 50 ? 'bg-amber-100 text-amber-800' : 'bg-[#e2e8f0]'}`}>
                  Avg confidence: {avgConfidence}%
                </span>
              )}
              <span className="text-xs text-[#6b7280]">
                {normalized.benefit_rules?.length ?? 0} benefits · {normalized.exclusions?.length ?? 0} exclusions · {normalized.evidence_requirements?.length ?? 0} evidence rules
              </span>
            </>
          )}
        </div>
        {loading && <div className="text-sm text-[#6b7280] mt-2">Loading…</div>}
      </Card>

      {/* Panel C: Canonical policy matrix */}
      {normalized?.version && (
        <Card padding="lg">
          <div className="text-sm font-semibold text-[#0b2b43] mb-2">C. Canonical policy matrix</div>
          <div className="text-xs text-[#6b7280] mb-3">
            Editable benefit rules. Toggle allowed, set min/standard/max, add approval and evidence requirements.
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-[#e2e8f0] bg-[#f8fafc]">
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]">Benefit</th>
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]">Allowed</th>
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]">Min</th>
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]">Standard</th>
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]">Max</th>
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]">Currency / Unit</th>
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]">Approval</th>
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]">Evidence</th>
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]">Notes</th>
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]">Source</th>
                  <th className="text-left py-2 px-2 font-medium text-[#0b2b43]"></th>
                </tr>
              </thead>
              <tbody>
                {(normalized.benefit_rules || []).map((r: any) => {
                  const link = getSourceLink('benefit_rule', r.id);
                  const isEditing = editingRule?.id === r.id;
                  const metaVal = (k: string, def?: any) => meta(r, k, def);
                  const allowed = metaVal('allowed', true);
                  const minVal = metaVal('min_value') ?? r.amount_value;
                  const standardVal = r.amount_value ?? metaVal('standard_value');
                  const maxVal = metaVal('max_value');
                  const approvalReq = metaVal('approval_required', false);
                  const evidenceReq = metaVal('evidence_required', false);
                  const notes = metaVal('hr_notes') ?? r.description ?? '';

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
                          <Input
                            type="number"
                            value={editingRule?.metadata_json ? String(meta(editingRule, 'min_value') ?? '') : String(minVal ?? '')}
                            onChange={(val) => {
                              const m = editingRule?.metadata_json || r?.metadata_json || {};
                              setEditingRule({ ...editingRule, metadata_json: { ...m, min_value: val ? Number(val) : null } });
                            }}
                            placeholder="—"
                          />
                        ) : (
                          <>{minVal != null ? minVal : '—'}</>
                        )}
                      </td>
                      <td className="py-2 px-2">
                        {isEditing ? (
                          <Input
                            type="number"
                            value={String(editingRule?.amount_value ?? standardVal ?? '')}
                            onChange={(val) => setEditingRule({ ...editingRule, amount_value: val ? Number(val) : null })}
                            placeholder="—"
                          />
                        ) : (
                          <>{typeof standardVal === 'number' || typeof standardVal === 'string' ? standardVal : '—'}</>
                        )}
                      </td>
                      <td className="py-2 px-2">
                        {isEditing ? (
                          <Input
                            type="number"
                            value={editingRule?.metadata_json ? String(meta(editingRule, 'max_value') ?? '') : String(maxVal ?? '')}
                            onChange={(val) => {
                              const m = editingRule?.metadata_json || r?.metadata_json || {};
                              setEditingRule({ ...editingRule, metadata_json: { ...m, max_value: val ? Number(val) : null } });
                            }}
                            placeholder="—"
                          />
                        ) : (
                          <>{typeof maxVal === 'number' || typeof maxVal === 'string' ? maxVal : '—'}</>
                        )}
                      </td>
                      <td className="py-2 px-2">
                        {isEditing ? (
                          <div className="flex gap-1">
                            <Input value={editingRule?.currency ?? r.currency ?? ''} onChange={(val) => setEditingRule({ ...editingRule, currency: val })} placeholder="USD" />
                            <Input value={editingRule?.amount_unit ?? r.amount_unit ?? ''} onChange={(val) => setEditingRule({ ...editingRule, amount_unit: val })} placeholder="Unit" />
                          </div>
                        ) : (
                          <span>{[r.currency, r.amount_unit].filter(Boolean).join(' / ') || '—'}</span>
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
          {(normalized.benefit_rules?.length ?? 0) === 0 && (
            <div className="text-sm text-[#6b7280] py-4">No benefit rules. Upload a document, Reprocess, then Normalize.</div>
          )}
        </Card>
      )}

      {/* Panel D & E: Benefit cards, Exclusions, Evidence */}
      {normalized?.version && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card padding="lg">
            <div className="text-sm font-semibold text-[#0b2b43] mb-2">D. Benefit cards by category</div>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {Object.entries(groupedBenefits).map(([cat, rules]) => (
                <div key={cat} className="border border-[#e2e8f0] rounded p-2">
                  <div className="text-xs font-medium text-[#6b7280]">{cat}</div>
                  {(rules as any[]).map((r: any) => (
                    <div key={r.id} className="text-sm text-[#0b2b43] mt-1">
                      {formatBenefitLabel(r)}: {r.amount_value != null ? r.amount_value : '—'} {r.currency || ''} {r.amount_unit || ''}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </Card>
          <Card padding="lg">
            <div className="text-sm font-semibold text-[#0b2b43] mb-2">E. Exclusions and evidence rules</div>
            <div className="space-y-3 max-h-48 overflow-y-auto">
              {normalized.exclusions?.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-[#6b7280]">Exclusions</div>
                  {normalized.exclusions.map((e: any) => (
                    <div key={e.id} className="text-sm py-1 border-b border-[#e2e8f0]">
                      <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 text-xs">{e.domain}</span>
                      {e.benefit_key && <span className="ml-1 text-[#6b7280]">{e.benefit_key}</span>}
                      <div className="text-[#4b5563] truncate">{e.description || e.raw_text?.slice(0, 80)}</div>
                    </div>
                  ))}
                </div>
              )}
              {normalized.evidence_requirements?.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-[#6b7280]">Evidence</div>
                  {normalized.evidence_requirements.map((ev: any) => (
                    <div key={ev.id} className="text-sm py-1 border-b border-[#e2e8f0]">
                      {(Array.isArray(ev.evidence_items_json) ? ev.evidence_items_json : []).join(', ')}
                      {ev.description && <div className="text-[#6b7280]">{ev.description}</div>}
                    </div>
                  ))}
                </div>
              )}
              {normalized.conditions?.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-[#6b7280]">Conditions</div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {normalized.conditions.map((c: any) => (
                      <span key={c.id} className="px-2 py-0.5 rounded bg-[#f0fdf4] text-xs text-[#166534]">
                        {c.condition_type}: {JSON.stringify(c.condition_value_json || {}).slice(0, 40)}…
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {(!normalized.exclusions?.length && !normalized.evidence_requirements?.length && !normalized.conditions?.length) && (
                <div className="text-sm text-[#6b7280]">None</div>
              )}
            </div>
          </Card>
        </div>
      )}

      {/* Panel F: Publish controls */}
      {normalized?.version && (
        <Card padding="lg">
          <div className="text-sm font-semibold text-[#0b2b43] mb-2">F. Publish controls</div>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="outline" size="sm" onClick={() => handleSaveStatus('draft')} disabled={statusBusy}>
              Save draft
            </Button>
            <Button variant="outline" size="sm" onClick={() => handleSaveStatus('review_required')} disabled={statusBusy}>
              Mark for review
            </Button>
            <Button variant="outline" size="sm" onClick={() => handleSaveStatus('reviewed')} disabled={statusBusy}>
              Mark reviewed
            </Button>
            <Button size="sm" onClick={handlePublish} disabled={publishBusy || versionStatus === 'published'}>
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
