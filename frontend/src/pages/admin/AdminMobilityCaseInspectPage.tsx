/**
 * Admin mobility inspect: operational readiness, evaluation snapshot, next actions,
 * and one action — run requirement evaluation for the linked assignment.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AdminLayout } from './AdminLayout';
import { Card } from '../../components/antigravity';
import { adminAPI, type AdminMobilityOperationalInspect } from '../../api/client';
import { buildRoute } from '../../navigation/routes';

function JsonBlock({ value }: { value: unknown }) {
  if (value == null) return <span className="text-[#9ca3af]"> - </span>;
  try {
    const s = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
    return (
      <pre className="text-xs font-mono bg-[#f1f5f9] border border-[#e2e8f0] rounded p-2 max-h-40 overflow-auto whitespace-pre-wrap break-all">
        {s}
      </pre>
    );
  } catch {
    return <span className="text-xs text-red-600">(unserializable)</span>;
  }
}

function ReadinessItem({ ok, label, emptyText }: { ok: boolean; label: string; emptyText: string }) {
  return (
    <div className="flex gap-2 py-2 border-b border-[#f1f5f9] last:border-0">
      <span
        className={`shrink-0 w-5 text-center ${ok ? 'text-emerald-600' : 'text-[#94a3b8]'}`}
        aria-label={ok ? 'Yes' : 'No'}
      >
        {ok ? '✓' : '—'}
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium text-[#0b2b43]">{label}</div>
        {!ok && <p className="text-xs text-[#64748b] mt-0.5">{emptyText}</p>}
      </div>
    </div>
  );
}

function dash(v: unknown): string {
  if (v == null || v === '') return '—';
  return String(v);
}

export const AdminMobilityCaseInspectPage: React.FC = () => {
  const { caseId } = useParams<{ caseId?: string }>();
  const navigate = useNavigate();
  const [manualId, setManualId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<{
    context: Record<string, unknown>;
    audit_logs: Array<Record<string, unknown>>;
    operational?: AdminMobilityOperationalInspect;
  } | null>(null);
  const [evalSubmitting, setEvalSubmitting] = useState(false);
  const [evalSuccess, setEvalSuccess] = useState<string | null>(null);
  const [evalError, setEvalError] = useState<string | null>(null);

  const load = useCallback(async (id: string) => {
    const trimmed = id.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    setEvalSuccess(null);
    setEvalError(null);
    try {
      const data = await adminAPI.inspectMobilityCase(trimmed);
      setPayload(data);
    } catch (e: unknown) {
      const ax = e as { response?: { status?: number; data?: { detail?: unknown } } };
      const st = ax.response?.status;
      const d = ax.response?.data?.detail;
      const msg =
        st === 404
          ? 'Mobility case not found.'
          : typeof d === 'string'
            ? d
            : st === 403
              ? 'Admin only.'
              : 'Failed to load case.';
      setError(msg);
      setPayload(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (caseId && caseId.trim()) {
      void load(caseId);
    } else {
      setPayload(null);
      setError(null);
    }
  }, [caseId, load]);

  const context = payload?.context as Record<string, unknown> | undefined;
  const caseRow = context?.case as Record<string, unknown> | null | undefined;
  const op = payload?.operational;
  const auditLogs = payload?.audit_logs || [];

  const runEvaluation = async () => {
    const aid = op?.assignment_id?.trim();
    if (!aid || !caseId) return;
    setEvalSubmitting(true);
    setEvalSuccess(null);
    setEvalError(null);
    try {
      await adminAPI.evaluateMobilityAssignmentRequirements(aid);
      setEvalSuccess('Evaluation finished. Data refreshed below.');
      await load(caseId);
    } catch (e: unknown) {
      const ax = e as { response?: { data?: { detail?: unknown } } };
      const d = ax.response?.data?.detail;
      const msg =
        typeof d === 'string'
          ? d
          : d && typeof d === 'object' && d !== null && 'message' in d
            ? String((d as { message?: string }).message)
            : 'Evaluation failed.';
      setEvalError(msg);
    } finally {
      setEvalSubmitting(false);
    }
  };

  if (!caseId) {
    return (
      <AdminLayout title="Mobility case inspect" subtitle="Enter mobility_cases.id (UUID)">
        <Card padding="md" className="max-w-lg">
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              const id = manualId.trim();
              if (!id) return;
              navigate(`/admin/mobility/cases/${encodeURIComponent(id)}`);
            }}
          >
            <label className="block text-sm font-medium text-[#0b2b43]">Mobility case UUID</label>
            <input
              className="w-full border border-[#cbd5e1] rounded-md px-3 py-2 text-sm font-mono"
              placeholder="33333333-3333-4333-8333-333333333301"
              value={manualId}
              onChange={(e) => setManualId(e.target.value)}
            />
            <button
              type="submit"
              className="px-4 py-2 rounded-md bg-[#0b2b43] text-white text-sm font-medium hover:opacity-90"
            >
              Open case
            </button>
          </form>
          <p className="text-xs text-[#64748b] mt-4">
            Admin session required. Uses{' '}
            <code className="bg-[#f1f5f9] px-1 rounded">GET /api/admin/mobility/cases/&#123;id&#125;/inspect</code>.
          </p>
        </Card>
      </AdminLayout>
    );
  }

  const rf = op?.readiness_flags;
  const canEvaluate = Boolean(op?.assignment_id?.trim());

  return (
    <AdminLayout title="Mobility case inspect" subtitle="Graph readiness, evaluation, next actions">
      <div className="mb-4 flex flex-wrap gap-2 items-center">
        <Link
          to={buildRoute('adminMobilityCases')}
          className="text-sm text-[#2563eb] hover:underline"
        >
          ← Choose another case
        </Link>
        <button
          type="button"
          className="text-sm px-3 py-1 border border-[#cbd5e1] rounded-md hover:bg-[#f8fafc]"
          disabled={loading}
          onClick={() => void load(caseId)}
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 text-red-800 text-sm px-3 py-2">{error}</div>
      )}
      {evalSuccess && (
        <div className="mb-4 rounded-md border border-emerald-200 bg-emerald-50 text-emerald-900 text-sm px-3 py-2">
          {evalSuccess}
        </div>
      )}
      {evalError && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 text-red-800 text-sm px-3 py-2">{evalError}</div>
      )}

      {loading && !payload && (
        <p className="text-sm text-[#64748b]" aria-busy="true">
          Loading…
        </p>
      )}

      {payload && caseRow && (
        <div className="space-y-4">
          {/* 1. Header */}
          <Card padding="md">
            <h2 className="text-sm font-semibold text-[#0b2b43] mb-3">Case</h2>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <dt className="text-[#64748b]">Mobility case</dt>
              <dd className="font-mono break-all">{dash(op?.mobility_case_id ?? caseRow.id)}</dd>
              <dt className="text-[#64748b]">Assignment</dt>
              <dd className="font-mono break-all">{dash(op?.assignment_id)}</dd>
              <dt className="text-[#64748b]">Bridge</dt>
              <dd>
                {op?.bridge_status === 'linked' ? (
                  <span className="text-emerald-700">Linked</span>
                ) : op?.bridge_status === 'missing' ? (
                  <span className="text-amber-800">No bridge</span>
                ) : (
                  <span className="text-[#64748b]">—</span>
                )}
              </dd>
              <dt className="text-[#64748b]">Route</dt>
              <dd>
                {dash(caseRow.origin_country)} → {dash(caseRow.destination_country)} · {dash(caseRow.case_type)}
              </dd>
            </dl>
            {!op && (
              <p className="text-xs text-amber-800 mt-3">
                Operational summary missing from API (deploy backend with latest inspect payload).
              </p>
            )}
          </Card>

          {/* 2. Readiness checklist */}
          {op && rf && (
            <Card padding="md">
              <h2 className="text-sm font-semibold text-[#0b2b43] mb-2">Graph readiness</h2>
              <ReadinessItem
                ok={rf.has_mobility_link}
                label="Assignment ↔ mobility bridge"
                emptyText="No row in assignment_mobility_links for this case — evaluation cannot run from an assignment."
              />
              <ReadinessItem
                ok={rf.has_employee_person}
                label="Employee person node"
                emptyText="No case_people row with role employee."
              />
              <ReadinessItem
                ok={rf.has_passport_document}
                label="Passport graph document (passport_copy)"
                emptyText="No case_documents row with key passport_copy."
              />
              <ReadinessItem
                ok={rf.has_evaluations}
                label="Requirement evaluations on file"
                emptyText="No rows in case_requirement_evaluations yet — run evaluation below."
              />
            </Card>
          )}

          {/* 3. Run evaluation */}
          {op && (
            <Card padding="md">
              <h2 className="text-sm font-semibold text-[#0b2b43] mb-2">Evaluation</h2>
              <p className="text-xs text-[#64748b] mb-3">
                Runs the controlled evaluator for the linked assignment (does not run automatically on load).
              </p>
              <button
                type="button"
                className="px-4 py-2 rounded-md bg-[#0b2b43] text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={!canEvaluate || evalSubmitting || loading}
                onClick={() => void runEvaluation()}
                title={!canEvaluate ? 'Link an assignment to this mobility case first.' : undefined}
              >
                {evalSubmitting ? 'Running…' : 'Run requirement evaluation'}
              </button>
              {!canEvaluate && (
                <p className="text-xs text-[#64748b] mt-2">Disabled: no assignment_id for this mobility case.</p>
              )}
            </Card>
          )}

          {/* 4. Evaluation summary */}
          {op && (
            <Card padding="md">
              <h2 className="text-sm font-semibold text-[#0b2b43] mb-2">Evaluation summary</h2>
              {!rf?.has_evaluations ? (
                <p className="text-sm text-[#64748b]">No evaluations yet.</p>
              ) : (
                <div className="text-sm space-y-2">
                  <div>
                    <span className="text-[#64748b]">Latest evaluated_at: </span>
                    <span className="font-mono text-xs">
                      {dash(op.latest_evaluation_summary?.evaluated_at)}
                    </span>
                  </div>
                  <div>
                    <span className="text-[#64748b] block mb-1">Counts by status</span>
                    <ul className="flex flex-wrap gap-2">
                      {Object.entries(op.latest_evaluation_summary?.counts_by_status || {}).map(([k, v]) => (
                        <li
                          key={k}
                          className="text-xs px-2 py-1 rounded border border-[#e2e8f0] bg-[#f8fafc]"
                        >
                          {k}: <strong>{v}</strong>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </Card>
          )}

          {/* 5. Results table */}
          {op && (
            <Card padding="md">
              <h2 className="text-sm font-semibold text-[#0b2b43] mb-2">Latest results</h2>
              {!op.latest_results?.length ? (
                <p className="text-sm text-[#64748b]">No evaluation rows.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="border-b border-[#e2e8f0] text-left text-[#64748b]">
                        <th className="py-2 pr-2 font-medium">Requirement</th>
                        <th className="py-2 pr-2 font-medium">Status</th>
                        <th className="py-2 pr-2 font-medium">Rule</th>
                        <th className="py-2 font-medium">Evaluated</th>
                      </tr>
                    </thead>
                    <tbody>
                      {op.latest_results.map((r, i) => (
                        <tr key={`${String(r.requirement_code)}-${i}`} className="border-b border-[#f1f5f9]">
                          <td className="py-2 pr-2 font-mono text-xs">{dash(r.requirement_code)}</td>
                          <td className="py-2 pr-2">{dash(r.evaluation_status)}</td>
                          <td className="py-2 pr-2 font-mono text-xs">{dash(r.source_rule_code)}</td>
                          <td className="py-2 text-[#64748b] whitespace-nowrap text-xs">{dash(r.evaluated_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          )}

          {/* 6. Next actions */}
          {op && (
            <Card padding="md">
              <h2 className="text-sm font-semibold text-[#0b2b43] mb-2">Next actions</h2>
              {!op.next_actions_preview?.actions?.length ? (
                <p className="text-sm text-[#64748b]">No open next actions (nothing missing or needs review).</p>
              ) : (
                <ul className="space-y-2">
                  {op.next_actions_preview.actions.map((a, i) => (
                    <li
                      key={`${a.related_requirement_code ?? 'x'}-${i}`}
                      className="text-sm border border-[#e2e8f0] rounded-md px-3 py-2 bg-[#fafafa]"
                    >
                      <div className="font-medium text-[#0b2b43]">{dash(a.action_title)}</div>
                      <div className="text-xs text-[#64748b] mt-1">
                        Priority {a.priority ?? '—'}
                        {a.related_requirement_code != null && a.related_requirement_code !== '' && (
                          <> · <span className="font-mono">{String(a.related_requirement_code)}</span></>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}

          {/* 7. Input snapshot */}
          {op && (
            <Card padding="md">
              <h2 className="text-sm font-semibold text-[#0b2b43] mb-3">Input snapshot</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <div className="text-xs font-semibold text-[#64748b] uppercase tracking-wide mb-2">Employee</div>
                  <dl className="text-sm space-y-1">
                    <div className="flex gap-2">
                      <dt className="text-[#64748b] shrink-0">Name</dt>
                      <dd className="break-words">{dash(op.employee_snapshot?.full_name)}</dd>
                    </div>
                    <div className="flex gap-2">
                      <dt className="text-[#64748b] shrink-0">Email</dt>
                      <dd className="break-all">{dash(op.employee_snapshot?.email)}</dd>
                    </div>
                    <div className="flex gap-2">
                      <dt className="text-[#64748b] shrink-0">Nationality</dt>
                      <dd>{dash(op.employee_snapshot?.nationality)}</dd>
                    </div>
                    <div className="flex gap-2">
                      <dt className="text-[#64748b] shrink-0">Residence</dt>
                      <dd>{dash(op.employee_snapshot?.residence_country)}</dd>
                    </div>
                    <div className="flex gap-2">
                      <dt className="text-[#64748b] shrink-0">Passport country</dt>
                      <dd>{dash(op.employee_snapshot?.passport_country)}</dd>
                    </div>
                  </dl>
                </div>
                <div>
                  <div className="text-xs font-semibold text-[#64748b] uppercase tracking-wide mb-2">Passport document</div>
                  <dl className="text-sm space-y-1">
                    <div className="flex gap-2">
                      <dt className="text-[#64748b] shrink-0">Key</dt>
                      <dd className="font-mono text-xs">{dash(op.passport_document_snapshot?.document_key)}</dd>
                    </div>
                    <div className="flex gap-2">
                      <dt className="text-[#64748b] shrink-0">Status</dt>
                      <dd>{dash(op.passport_document_snapshot?.document_status)}</dd>
                    </div>
                    <div className="flex gap-2">
                      <dt className="text-[#64748b] shrink-0">Source evidence</dt>
                      <dd className="font-mono text-xs break-all">
                        {dash(op.passport_document_snapshot?.source_evidence_id)}
                      </dd>
                    </div>
                    <div className="flex gap-2">
                      <dt className="text-[#64748b] shrink-0">Submitted</dt>
                      <dd className="text-xs">{dash(op.passport_document_snapshot?.submitted_at)}</dd>
                    </div>
                  </dl>
                </div>
              </div>
            </Card>
          )}

          {/* Audit log */}
          <Card padding="md">
            <div className="text-sm font-semibold text-[#0b2b43] mb-2">Audit log ({auditLogs.length})</div>
            {auditLogs.length === 0 ? (
              <p className="text-sm text-[#64748b]">
                No audit rows (migrations not applied, or no activity yet).
              </p>
            ) : (
              <div className="space-y-3 max-h-[480px] overflow-y-auto">
                {auditLogs.map((row) => (
                  <div
                    key={String(row.id)}
                    className="border border-[#e2e8f0] rounded-md p-2 text-xs bg-[#fafafa]"
                  >
                    <div className="flex flex-wrap gap-x-3 gap-y-1 text-[#0b2b43]">
                      <span className="font-medium">{String(row.created_at ?? '')}</span>
                      <span>{String(row.action_type)}</span>
                      <span className="text-[#64748b]">{String(row.entity_type)}</span>
                      <span className="font-mono">{String(row.entity_id)}</span>
                      <span className="text-[#64748b]">
                        actor: {String(row.actor_type)}
                        {row.actor_id != null ? ` / ${String(row.actor_id)}` : ''}
                      </span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2">
                      <div>
                        <div className="text-[#64748b] mb-0.5">Old</div>
                        <JsonBlock value={row.old_value_json} />
                      </div>
                      <div>
                        <div className="text-[#64748b] mb-0.5">New</div>
                        <JsonBlock value={row.new_value_json} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Raw case metadata (read-only, compact) */}
          <Card padding="md">
            <div className="text-sm font-semibold text-[#0b2b43] mb-2">Case metadata</div>
            <JsonBlock value={caseRow.metadata} />
          </Card>
        </div>
      )}

      {payload && !caseRow && !loading && (
        <p className="text-sm text-[#64748b]">Case payload missing (unexpected).</p>
      )}
    </AdminLayout>
  );
};
