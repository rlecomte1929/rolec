import React, { useCallback, useEffect, useState } from 'react';
import { Card, Button, Badge } from '../../components/antigravity';
import { hrAPI } from '../../api/client';

type RouteRef = {
  source_key?: string;
  source_type?: string;
  reference_strength?: string;
  source_title?: string;
  source_publisher?: string;
  source_url?: string;
  topic?: string;
  source_last_reviewed_at?: string;
};

type Summary = {
  resolved?: boolean;
  reason?: string;
  destination_raw?: string | null;
  destination_key?: string | null;
  route_key?: string;
  route_title?: string;
  hr_summary?: string;
  employee_summary?: string;
  top_watchouts?: string[];
  checklist?: { total?: number; completed_or_waived?: number; pending?: number };
  next_milestone?: { title?: string; phase?: string; relative_timing?: string } | null;
  user_message?: string;
  human_review_required?: boolean;
  trust_tier?: string;
  disclaimer_legal?: string;
  trust_summary?: string;
  route_references?: RouteRef[];
  route_references_note?: string | null;
  reference_set_version?: string;
  check_catalog_version?: string;
};

type ChecklistRow = {
  id: string;
  title?: string;
  owner_role?: string;
  required?: number;
  status?: string;
  notes_hr?: string | null;
  notes_employee?: string | null;
  state_notes?: string | null;
  stable_key?: string | null;
  content_tier?: string;
  human_review_required?: boolean;
  reference_note?: string;
  primary_reference?: RouteRef | null;
};

type MilestoneRow = {
  id: string;
  title?: string;
  phase?: string;
  relative_timing?: string;
  body_hr?: string | null;
  completed_at?: string | null;
};

const OWNER_LABEL: Record<string, string> = {
  employee: 'Employee',
  hr: 'HR',
  employer: 'Employer',
  provider: 'Provider',
};

function statusBadgeVariant(s: string) {
  if (s === 'done' || s === 'waived') return 'success' as const;
  if (s === 'blocked') return 'warning' as const;
  if (s === 'in_progress') return 'info' as const;
  return 'neutral' as const;
}

interface CaseReadinessCoreProps {
  assignmentId: string;
}

/**
 * Case Readiness Core — summary loads immediately; checklist + timeline load when expanded.
 * Copy comes from API (templates), not hardcoded in the component.
 */
export const CaseReadinessCore: React.FC<CaseReadinessCoreProps> = ({ assignmentId }) => {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [checklistItems, setChecklistItems] = useState<ChecklistRow[]>([]);
  const [milestones, setMilestones] = useState<MilestoneRow[]>([]);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailFetched, setDetailFetched] = useState(false);
  const [actionBusy, setActionBusy] = useState<string | null>(null);

  useEffect(() => {
    if (!assignmentId) return;
    let cancelled = false;
    const ac = new AbortController();
    setSummaryLoading(true);
    setSummaryError(null);
    hrAPI
      .getReadinessSummary(assignmentId, { signal: ac.signal })
      .then((data) => {
        if (!cancelled) setSummary(data as Summary);
      })
      .catch(() => {
        if (!cancelled) setSummaryError('Could not load readiness summary.');
      })
      .finally(() => {
        if (!cancelled) setSummaryLoading(false);
      });
    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [assignmentId]);

  useEffect(() => {
    setDetailFetched(false);
    setChecklistItems([]);
    setMilestones([]);
    setDetailError(null);
    setExpanded(false);
  }, [assignmentId]);

  const loadDetail = useCallback(async () => {
    if (!assignmentId) return;
    setDetailLoading(true);
    setDetailError(null);
    try {
      const data = await hrAPI.getReadinessDetail(assignmentId);
      setChecklistItems((data.checklist_items as ChecklistRow[]) || []);
      setMilestones((data.milestones as MilestoneRow[]) || []);
      setDetailFetched(true);
    } catch {
      setDetailError('Could not load checklist and timeline.');
      setDetailFetched(true);
    } finally {
      setDetailLoading(false);
    }
  }, [assignmentId]);

  useEffect(() => {
    if (!expanded || detailFetched || detailLoading) return;
    void loadDetail();
  }, [expanded, detailFetched, detailLoading, loadDetail]);

  const onToggleExpand = () => {
    setExpanded((e) => !e);
  };

  const patchChecklist = async (itemId: string, status: string) => {
    setActionBusy(`chk-${itemId}`);
    try {
      await hrAPI.patchReadinessChecklistItem(assignmentId, itemId, { status });
      await loadDetail();
      const s = await hrAPI.getReadinessSummary(assignmentId);
      setSummary(s as Summary);
    } finally {
      setActionBusy(null);
    }
  };

  const patchMilestone = async (milestoneId: string, completed: boolean) => {
    setActionBusy(`ms-${milestoneId}`);
    try {
      await hrAPI.patchReadinessMilestone(assignmentId, milestoneId, { completed });
      await loadDetail();
      const s = await hrAPI.getReadinessSummary(assignmentId);
      setSummary(s as Summary);
    } finally {
      setActionBusy(null);
    }
  };

  if (summaryLoading) {
    return (
      <Card padding="lg">
        <div className="text-sm text-[#6b7280]">Loading case readiness…</div>
      </Card>
    );
  }

  if (summaryError || !summary) {
    return (
      <Card padding="lg">
        <div className="text-sm text-red-600">{summaryError || 'Readiness unavailable.'}</div>
      </Card>
    );
  }

  if (!summary.resolved) {
    const body =
      summary.user_message ||
      (summary.reason === 'no_destination'
        ? 'Set destination in the employee move plan (or case host country) to see immigration route, documents, and milestones.'
        : summary.reason === 'readiness_store_unavailable'
          ? 'Readiness database is not available in this environment. Apply the readiness migration or contact operations.'
          : `No readiness template for destination “${summary.destination_key || summary.destination_raw || 'unknown'}” yet.`);
    return (
      <Card padding="lg">
        <div className="text-sm font-semibold text-[#0b2b43]">Case readiness</div>
        <p className="text-sm text-[#6b7280] mt-2">{body}</p>
        {summary.human_review_required && (
          <div className="mt-3 text-xs font-semibold text-amber-900 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            Human review required — ReloPass is not verifying immigration eligibility.
          </div>
        )}
        {summary.disclaimer_legal && (
          <p className="text-xs text-[#64748b] mt-3 border-t border-[#e2e8f0] pt-3">{summary.disclaimer_legal}</p>
        )}
        {summary.route_references && summary.route_references.length > 0 && (
          <div className="mt-4">
            <div className="text-xs font-semibold text-[#0b2b43] uppercase tracking-wide">
              Official pointers (diligence)
            </div>
            <ul className="mt-2 space-y-2 text-sm">
              {summary.route_references.map((r) => (
                <li key={r.source_key || r.source_title}>
                  {r.source_url ? (
                    <a
                      href={r.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[#1d4ed8] hover:underline"
                    >
                      {r.source_title || r.source_key}
                    </a>
                  ) : (
                    <span>{r.source_title}</span>
                  )}
                  {r.source_publisher && (
                    <span className="text-[#64748b]"> — {r.source_publisher}</span>
                  )}
                </li>
              ))}
            </ul>
            {summary.route_references_note && (
              <p className="text-xs text-[#64748b] mt-2">{summary.route_references_note}</p>
            )}
          </div>
        )}
      </Card>
    );
  }

  const chk = summary.checklist || {};
  const total = chk.total ?? 0;
  const done = chk.completed_or_waived ?? 0;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  const grouped = checklistItems.reduce<Record<string, ChecklistRow[]>>((acc, row) => {
    const k = row.owner_role || 'other';
    if (!acc[k]) acc[k] = [];
    acc[k].push(row);
    return acc;
  }, {});

  return (
    <Card padding="lg">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-wide text-[#6b7280]">Case readiness</div>
          <h3 className="text-lg font-semibold text-[#0b2b43] mt-1">{summary.route_title}</h3>
          <p className="text-sm text-[#475569] mt-2 max-w-3xl">{summary.hr_summary}</p>
        </div>
        <div className="text-right shrink-0">
          <div className="text-2xl font-semibold text-[#0b2b43]">{pct}%</div>
          <div className="text-xs text-[#6b7280]">
            {done}/{total} checklist done
          </div>
        </div>
      </div>

      {summary.disclaimer_legal && (
        <p className="mt-3 text-xs text-[#64748b] border border-[#e2e8f0] rounded-lg px-3 py-2 bg-[#f8fafc]">
          {summary.disclaimer_legal}
        </p>
      )}
      {summary.trust_summary && (
        <p className="mt-2 text-xs text-[#64748b]">{summary.trust_summary}</p>
      )}
      {summary.route_references && summary.route_references.length > 0 && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-[#1d4ed8] font-medium">
            Official reference pointers ({summary.route_references.length})
          </summary>
          <ul className="mt-2 space-y-1.5 pl-4 list-disc text-[#475569]">
            {summary.route_references.map((r) => (
              <li key={r.source_key || r.source_title}>
                {r.source_url ? (
                  <a href={r.source_url} target="_blank" rel="noopener noreferrer" className="text-[#1d4ed8] hover:underline">
                    {r.source_title}
                  </a>
                ) : (
                  r.source_title
                )}
                {r.source_last_reviewed_at && (
                  <span className="text-[#94a3b8]"> · Last reviewed {r.source_last_reviewed_at}</span>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
      {summary.human_review_required && (
        <div className="mt-3 text-xs font-medium text-amber-900">
          Human review required for immigration decisions — checklist is operational guidance only.
        </div>
      )}

      {summary.top_watchouts && summary.top_watchouts.length > 0 && (
        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50/80 px-3 py-2">
          <div className="text-xs font-semibold text-amber-900 uppercase tracking-wide">Internal watchouts</div>
          <ul className="mt-1 list-disc list-inside text-sm text-amber-950 space-y-1">
            {summary.top_watchouts.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {summary.next_milestone && (
        <div className="mt-4 text-sm">
          <span className="text-[#6b7280]">Next milestone: </span>
          <span className="font-medium text-[#0b2b43]">{summary.next_milestone.title}</span>
          {summary.next_milestone.relative_timing && (
            <span className="text-[#6b7280]"> · {summary.next_milestone.relative_timing}</span>
          )}
        </div>
      )}

      <div className="mt-4">
        <Button variant="outline" type="button" onClick={onToggleExpand}>
          {expanded ? 'Hide checklist & timeline' : 'Show checklist & timeline'}
        </Button>
      </div>

      {expanded && (
        <div className="mt-6 space-y-6 border-t border-[#e2e8f0] pt-6">
          {detailLoading && <div className="text-sm text-[#6b7280]">Loading details…</div>}
          {detailError && <div className="text-sm text-red-600">{detailError}</div>}

          {!detailLoading && !detailError && (
            <>
              <div>
                <div className="text-sm font-semibold text-[#0b2b43] mb-3">Document checklist</div>
                <div className="space-y-4">
                  {Object.entries(grouped).map(([owner, items]) => (
                    <div key={owner}>
                      <div className="text-xs font-medium text-[#64748b] mb-2">
                        {OWNER_LABEL[owner] || owner}
                      </div>
                      <ul className="space-y-2">
                        {items.map((row) => (
                          <li
                            key={row.id}
                            className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-[#e2e8f0] bg-[#fafbfc] px-3 py-2"
                          >
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="text-sm font-medium text-[#0f172a]">{row.title}</span>
                                {row.required ? (
                                  <Badge variant="neutral">Required</Badge>
                                ) : (
                                  <Badge variant="neutral">Optional</Badge>
                                )}
                                <Badge variant={statusBadgeVariant(row.status || 'pending')}>
                                  {row.status || 'pending'}
                                </Badge>
                              </div>
                              {row.notes_hr && (
                                <p className="text-xs text-[#64748b] mt-1">{row.notes_hr}</p>
                              )}
                              {row.reference_note && (
                                <p className="text-xs text-[#475569] mt-1 italic">{row.reference_note}</p>
                              )}
                              {row.primary_reference?.source_url && (
                                <p className="text-xs mt-1">
                                  <span className="text-[#64748b]">Pointer: </span>
                                  <a
                                    href={row.primary_reference.source_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-[#1d4ed8] hover:underline"
                                  >
                                    {row.primary_reference.source_title || 'Source'}
                                  </a>
                                  {row.primary_reference.reference_strength && (
                                    <span className="text-[#94a3b8]"> ({row.primary_reference.reference_strength})</span>
                                  )}
                                </p>
                              )}
                              {row.human_review_required && (
                                <div className="mt-1">
                                  <Badge variant="warning" size="sm">
                                    Human review
                                  </Badge>
                                </div>
                              )}
                            </div>
                            <div className="flex flex-wrap gap-1 shrink-0">
                              {(['pending', 'in_progress', 'done', 'waived', 'blocked'] as const).map((st) => (
                                <button
                                  key={st}
                                  type="button"
                                  disabled={actionBusy === `chk-${row.id}`}
                                  onClick={() => patchChecklist(row.id, st)}
                                  className={`text-[11px] px-2 py-1 rounded border ${
                                    row.status === st
                                      ? 'bg-[#0f172a] text-white border-[#0f172a]'
                                      : 'bg-white text-[#475569] border-[#e2e8f0] hover:bg-[#f1f5f9]'
                                  }`}
                                >
                                  {st.replace('_', ' ')}
                                </button>
                              ))}
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="text-sm font-semibold text-[#0b2b43] mb-3">Milestones</div>
                <ol className="space-y-2 list-decimal list-inside text-sm text-[#334155]">
                  {milestones.map((m) => (
                    <li key={m.id} className="pl-1">
                      <span className="font-medium text-[#0f172a]">{m.title}</span>
                      {m.relative_timing && (
                        <span className="text-[#6b7280]"> — {m.relative_timing}</span>
                      )}
                      {m.body_hr && <div className="text-xs text-[#64748b] ml-6 mt-0.5">{m.body_hr}</div>}
                      <label className="ml-6 mt-1 flex items-center gap-2 text-xs cursor-pointer">
                        <input
                          type="checkbox"
                          checked={!!m.completed_at}
                          disabled={actionBusy === `ms-${m.id}`}
                          onChange={(e) => patchMilestone(m.id, e.target.checked)}
                        />
                        <span>Mark complete</span>
                      </label>
                    </li>
                  ))}
                </ol>
              </div>
            </>
          )}
        </div>
      )}
    </Card>
  );
};
