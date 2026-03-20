/**
 * Read-only admin view: one mobility_cases row + people, documents, evaluations (filterable), audit log.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AdminLayout } from './AdminLayout';
import { Card } from '../../components/antigravity';
import { adminAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';

type EvalFilter = 'all' | 'missing' | 'needs_review' | 'met';

function JsonBlock({ value }: { value: unknown }) {
  if (value == null) return <span className="text-[#9ca3af]">—</span>;
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

const FILTER_OPTIONS: { key: EvalFilter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'missing', label: 'Missing' },
  { key: 'needs_review', label: 'Needs review' },
  { key: 'met', label: 'Met' },
];

export const AdminMobilityCaseInspectPage: React.FC = () => {
  const { caseId } = useParams<{ caseId?: string }>();
  const navigate = useNavigate();
  const [manualId, setManualId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<{
    context: Record<string, unknown>;
    audit_logs: Array<Record<string, unknown>>;
  } | null>(null);
  const [evalFilter, setEvalFilter] = useState<EvalFilter>('all');

  const load = useCallback(async (id: string) => {
    const trimmed = id.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
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
  const people = (context?.people as Array<Record<string, unknown>>) || [];
  const documents = (context?.documents as Array<Record<string, unknown>>) || [];
  const evaluationsRaw = (context?.evaluations as Array<Record<string, unknown>>) || [];
  const auditLogs = payload?.audit_logs || [];

  const filteredEvaluations = useMemo(() => {
    if (evalFilter === 'all') return evaluationsRaw;
    return evaluationsRaw.filter((e) => String(e.evaluation_status || '') === evalFilter);
  }, [evaluationsRaw, evalFilter]);

  if (!caseId) {
    return (
      <AdminLayout title="Mobility case inspect" subtitle="Enter a mobility_cases.id (UUID) to load read-only data.">
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
            <label className="block text-sm font-medium text-[#0b2b43]">Case UUID</label>
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
            Requires admin session. Uses{' '}
            <code className="bg-[#f1f5f9] px-1 rounded">GET /api/admin/mobility/cases/&#123;id&#125;/inspect</code>.
          </p>
        </Card>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout title="Mobility case inspect" subtitle={`Case ${caseId} — read-only`}>
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

      {loading && !payload && (
        <p className="text-sm text-[#64748b]" aria-busy="true">
          Loading…
        </p>
      )}

      {payload && caseRow && (
        <div className="space-y-4">
          <Card padding="md">
            <div className="text-sm font-semibold text-[#0b2b43] mb-2">Case summary</div>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-sm">
              <dt className="text-[#64748b]">ID</dt>
              <dd className="font-mono">{String(caseRow.id ?? '—')}</dd>
              <dt className="text-[#64748b]">Company</dt>
              <dd className="font-mono">{String(caseRow.company_id ?? '—')}</dd>
              <dt className="text-[#64748b]">Employee user</dt>
              <dd className="font-mono">{String(caseRow.employee_user_id ?? '—')}</dd>
              <dt className="text-[#64748b]">Origin</dt>
              <dd>{String(caseRow.origin_country ?? '—')}</dd>
              <dt className="text-[#64748b]">Destination</dt>
              <dd>{String(caseRow.destination_country ?? '—')}</dd>
              <dt className="text-[#64748b]">Case type</dt>
              <dd>{String(caseRow.case_type ?? '—')}</dd>
              <dt className="text-[#64748b]">Metadata</dt>
              <dd className="sm:col-span-1">
                <JsonBlock value={caseRow.metadata} />
              </dd>
            </dl>
          </Card>

          <Card padding="md">
            <div className="text-sm font-semibold text-[#0b2b43] mb-2">People ({people.length})</div>
            {people.length === 0 ? (
              <p className="text-sm text-[#64748b]">No people linked.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="border-b border-[#e2e8f0] text-left text-[#64748b]">
                      <th className="py-2 pr-2 font-medium">ID</th>
                      <th className="py-2 pr-2 font-medium">Role</th>
                      <th className="py-2 font-medium">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {people.map((p) => (
                      <tr key={String(p.id)} className="border-b border-[#f1f5f9]">
                        <td className="py-2 pr-2 font-mono text-xs">{String(p.id)}</td>
                        <td className="py-2 pr-2">{String(p.role ?? '—')}</td>
                        <td className="py-2 text-[#64748b]">{String(p.created_at ?? '—')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card padding="md">
            <div className="text-sm font-semibold text-[#0b2b43] mb-2">Documents ({documents.length})</div>
            {documents.length === 0 ? (
              <p className="text-sm text-[#64748b]">No documents.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="border-b border-[#e2e8f0] text-left text-[#64748b]">
                      <th className="py-2 pr-2 font-medium">Key</th>
                      <th className="py-2 pr-2 font-medium">Status</th>
                      <th className="py-2 pr-2 font-medium">Person</th>
                      <th className="py-2 font-medium">Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {documents.map((d) => (
                      <tr key={String(d.id)} className="border-b border-[#f1f5f9]">
                        <td className="py-2 pr-2">{String(d.document_key ?? '—')}</td>
                        <td className="py-2 pr-2">{String(d.document_status ?? '—')}</td>
                        <td className="py-2 pr-2 font-mono text-xs">{String(d.person_id ?? '—')}</td>
                        <td className="py-2 text-[#64748b]">{String(d.updated_at ?? '—')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card padding="md">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <div className="text-sm font-semibold text-[#0b2b43]">
                Evaluations ({filteredEvaluations.length}
                {evalFilter !== 'all' ? ` of ${evaluationsRaw.length}` : ''})
              </div>
              <div className="flex flex-wrap gap-1">
                {FILTER_OPTIONS.map(({ key, label }) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setEvalFilter(key)}
                    className={`text-xs px-2 py-1 rounded border ${
                      evalFilter === key
                        ? 'border-[#0b2b43] bg-[#eef4f8] text-[#0b2b43]'
                        : 'border-[#e2e8f0] text-[#64748b] hover:bg-[#f8fafc]'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            {evaluationsRaw.length === 0 ? (
              <p className="text-sm text-[#64748b]">No evaluations yet. Run the system evaluator to populate.</p>
            ) : filteredEvaluations.length === 0 ? (
              <p className="text-sm text-[#64748b]">No rows for this filter.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="border-b border-[#e2e8f0] text-left text-[#64748b]">
                      <th className="py-2 pr-2 font-medium">Requirement</th>
                      <th className="py-2 pr-2 font-medium">Status</th>
                      <th className="py-2 pr-2 font-medium">Reason</th>
                      <th className="py-2 font-medium">Evaluated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredEvaluations.map((ev) => (
                      <tr key={String(ev.id)} className="border-b border-[#f1f5f9] align-top">
                        <td className="py-2 pr-2 font-mono text-xs">
                          {String(ev.requirement_code ?? ev.requirement_id ?? '—')}
                        </td>
                        <td className="py-2 pr-2">{String(ev.evaluation_status ?? '—')}</td>
                        <td className="py-2 pr-2 max-w-md">{String(ev.reason_text ?? '—')}</td>
                        <td className="py-2 text-[#64748b] whitespace-nowrap">
                          {String(ev.evaluated_at ?? ev.updated_at ?? '—')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

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
        </div>
      )}

      {payload && !caseRow && !loading && (
        <p className="text-sm text-[#64748b]">Case payload missing (unexpected).</p>
      )}
    </AdminLayout>
  );
};
