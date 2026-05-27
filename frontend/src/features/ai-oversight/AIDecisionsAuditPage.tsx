import { useEffect, useMemo, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { Breadcrumb } from '../../components/Breadcrumb';
import { listAIDecisions } from '../../api/aiDecisions';
import type { AIDecisionAction, AIDecisionRecord } from '../../api/aiDecisions';

/**
 * AIDecisionsAuditPage (AI-002) — EU AI Act Art. 14(4)(c) human oversight audit view.
 *
 * Lists every HR action recorded on an AI recommendation in `public.ai_decisions`.
 * Filterable by feature and decision. Read-only — decisions are append-only and
 * cannot be edited from the UI.
 */

const DECISION_BADGE: Record<AIDecisionAction, string> = {
  accept: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  override: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  reject: 'bg-rose-50 text-rose-700 ring-1 ring-rose-200',
};

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export function AIDecisionsAuditPage() {
  const [records, setRecords] = useState<AIDecisionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [featureFilter, setFeatureFilter] = useState<string>('');
  const [decisionFilter, setDecisionFilter] = useState<AIDecisionAction | ''>('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listAIDecisions({
      feature: featureFilter || undefined,
      decision: decisionFilter || undefined,
      limit: 200,
    })
      .then((rows) => {
        if (!cancelled) setRecords(rows);
      })
      .catch((e) => {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : 'Failed to load AI decisions';
          setError(msg);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [featureFilter, decisionFilter]);

  const featureOptions = useMemo(() => {
    const set = new Set<string>();
    for (const r of records) set.add(r.feature);
    return Array.from(set).sort();
  }, [records]);

  const counts = useMemo(
    () => ({
      total: records.length,
      accept: records.filter((r) => r.decision === 'accept').length,
      override: records.filter((r) => r.decision === 'override').length,
      reject: records.filter((r) => r.decision === 'reject').length,
    }),
    [records]
  );

  return (
    <AppShell wide>
      <div className="px-6 py-5 border-b border-slate-100">
        <Breadcrumb section="HR Operations" title="AI decisions audit" className="mb-2" />
        <div className="flex items-end gap-3">
          <h1 className="text-xl font-semibold text-slate-900">AI decisions audit</h1>
          <div className="flex-1" />
          <span className="text-xs text-slate-500">
            {counts.total} decisions · {counts.accept} accepted · {counts.override} overridden · {counts.reject} rejected
          </span>
        </div>
        <p className="mt-1 text-sm text-slate-500 leading-relaxed">
          Every accept, override, or reject your team recorded on an AI-generated recommendation. Append-only — required by EU AI Act Art. 14(4)(c).
        </p>
      </div>

      <div className="px-6 py-4 border-b border-slate-100 flex flex-wrap gap-3 items-center">
        <label className="text-xs font-medium text-slate-600">
          Feature
          <select
            value={featureFilter}
            onChange={(e) => setFeatureFilter(e.target.value)}
            className="ml-2 rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-700 bg-white focus:outline-none focus:ring-2 focus:ring-slate-200"
          >
            <option value="">All features</option>
            {featureOptions.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </label>
        <label className="text-xs font-medium text-slate-600">
          Decision
          <select
            value={decisionFilter}
            onChange={(e) => setDecisionFilter(e.target.value as AIDecisionAction | '')}
            className="ml-2 rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-700 bg-white focus:outline-none focus:ring-2 focus:ring-slate-200"
          >
            <option value="">All decisions</option>
            <option value="accept">Accept</option>
            <option value="override">Override</option>
            <option value="reject">Reject</option>
          </select>
        </label>
      </div>

      <div className="px-6 py-5">
        {loading && (
          <p className="text-sm text-slate-500">Loading AI decisions…</p>
        )}
        {error && !loading && (
          <p className="text-sm text-rose-600">{error}</p>
        )}
        {!loading && !error && records.length === 0 && (
          <div className="text-center py-10">
            <p className="text-sm text-slate-500">No AI decisions recorded yet.</p>
            <p className="text-xs text-slate-400 mt-1">As HR admins accept, override, or reject AI recommendations, they will appear here.</p>
          </div>
        )}
        {!loading && !error && records.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-slate-200">
                  <th className="text-left py-2 pr-3 font-medium">When</th>
                  <th className="text-left py-2 pr-3 font-medium">Feature</th>
                  <th className="text-left py-2 pr-3 font-medium">Recommendation</th>
                  <th className="text-left py-2 pr-3 font-medium">Decision</th>
                  <th className="text-left py-2 pr-3 font-medium">Reason</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r) => (
                  <tr key={r.id} className="border-b border-slate-100 last:border-b-0 align-top">
                    <td className="py-3 pr-3 text-xs text-slate-500 whitespace-nowrap">{formatTimestamp(r.created_at)}</td>
                    <td className="py-3 pr-3 text-xs text-slate-700">{r.feature}</td>
                    <td className="py-3 pr-3 text-xs text-slate-700 max-w-xs truncate" title={r.recommendation_id}>{r.recommendation_id}</td>
                    <td className="py-3 pr-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium uppercase tracking-wide ${DECISION_BADGE[r.decision]}`}>
                        {r.decision}
                      </span>
                    </td>
                    <td className="py-3 pr-3 text-xs text-slate-600 max-w-md">
                      {r.reason ? <span className="italic">"{r.reason}"</span> : <span className="text-slate-300">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppShell>
  );
}
