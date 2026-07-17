import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button } from '../../components/antigravity/Button';
import { Card } from '../../components/antigravity/Card';
import { AppShell } from '../../components/AppShell';
import { Breadcrumb } from '../../components/Breadcrumb';
import { listAIDecisions } from '../../api/aiDecisions';
import type { AIDecisionAction, AIDecisionRecord } from '../../api/aiDecisions';

/**
 * AIDecisionsAuditPage (AI-002 + AI-007) — EU AI Act Art. 14(4)(c) audit view.
 *
 * Lists every HR action recorded on an AI recommendation in `public.ai_decisions`.
 * Filterable by feature, decision, and recommendation_id (via ?recommendation_id=
 * query param — used by the deep-link from AIRecommendationCard). Rows whose
 * `ai_output.prior_decision` references another row render a clickable "← prior"
 * tag that scrolls to and highlights the prior row. CSV export of the current
 * filter is in the page header. Read-only — decisions are append-only.
 */

const DECISION_BADGE: Record<AIDecisionAction, string> = {
  accept: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  override: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  reject: 'bg-rose-50 text-rose-700 ring-1 ring-rose-200',
};

// At-a-glance stat tiles. `key` maps to the `counts` object below; the dot colour
// ties each tile back to its decision badge in the table (navy = the running total).
const STAT_TILES = [
  { key: 'total', label: 'Total decisions', dot: 'bg-navy-800', value: 'text-slate-900' },
  { key: 'accept', label: 'Accepted', dot: 'bg-emerald-500', value: 'text-emerald-700' },
  { key: 'override', label: 'Overridden', dot: 'bg-amber-500', value: 'text-amber-700' },
  { key: 'reject', label: 'Rejected', dot: 'bg-rose-500', value: 'text-rose-700' },
] as const;

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

function priorDecisionId(record: AIDecisionRecord): string | null {
  const prior = (record.ai_output as { prior_decision?: { id?: string } } | null)?.prior_decision;
  return prior?.id ?? null;
}

// CSV serialisation — RFC 4180 quoting (double-quote escape, wrap fields with
// commas/quotes/newlines). Kept inline; no library dep for one call site.
function csvEscape(value: unknown): string {
  if (value === null || value === undefined) return '';
  const s = typeof value === 'string' ? value : JSON.stringify(value);
  if (/[",\n\r]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

function buildCSV(records: AIDecisionRecord[]): string {
  const header = ['when', 'feature', 'recommendation_id', 'decision', 'reason', 'actor_id', 'ai_output'];
  const rows = records.map((r) => [
    r.created_at,
    r.feature,
    r.recommendation_id,
    r.decision,
    r.reason ?? '',
    r.actor_id ?? '',
    r.ai_output,
  ]);
  return [header.join(','), ...rows.map((row) => row.map(csvEscape).join(','))].join('\n');
}

function downloadCSV(csv: string, filename: string): void {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function AIDecisionsAuditPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [records, setRecords] = useState<AIDecisionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [featureFilter, setFeatureFilter] = useState<string>('');
  const [decisionFilter, setDecisionFilter] = useState<AIDecisionAction | ''>('');

  // Deep-link from AIRecommendationCard: ?recommendation_id=<id> pre-filters
  // the table to just that recommendation's decision history.
  const recommendationIdFilter = searchParams.get('recommendation_id') ?? '';
  const clearRecommendationFilter = useCallback(() => {
    const next = new URLSearchParams(searchParams);
    next.delete('recommendation_id');
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  // Track row DOM refs so the chain "← prior" tag can scroll to the matched row.
  const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({});
  const [highlightId, setHighlightId] = useState<string | null>(null);

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

  // Apply the URL-driven recommendation_id filter client-side (after the
  // feature/decision query — we don't ask the backend for this filter).
  const visibleRecords = useMemo(() => {
    if (!recommendationIdFilter) return records;
    return records.filter((r) => r.recommendation_id === recommendationIdFilter);
  }, [records, recommendationIdFilter]);

  const loadedIds = useMemo(() => new Set(records.map((r) => r.id)), [records]);

  const counts = useMemo(
    () => ({
      total: visibleRecords.length,
      accept: visibleRecords.filter((r) => r.decision === 'accept').length,
      override: visibleRecords.filter((r) => r.decision === 'override').length,
      reject: visibleRecords.filter((r) => r.decision === 'reject').length,
    }),
    [visibleRecords]
  );

  const handlePriorClick = useCallback(
    (priorId: string) => {
      if (!loadedIds.has(priorId)) return;
      const el = rowRefs.current[priorId];
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        setHighlightId(priorId);
        window.setTimeout(() => setHighlightId(null), 1800);
      }
    },
    [loadedIds]
  );

  const handleExport = useCallback(() => {
    if (visibleRecords.length === 0) return;
    const stamp = new Date().toISOString().slice(0, 10);
    downloadCSV(buildCSV(visibleRecords), `ai_decisions_${stamp}.csv`);
  }, [visibleRecords]);

  return (
    <AppShell wide>
      <div className="px-6 py-5 border-b border-slate-100">
        <Breadcrumb section="HR Operations" title="AI decisions audit" className="mb-2" />
        <div className="flex items-end gap-3">
          <h1 className="text-xl font-semibold text-slate-900">AI decisions audit</h1>
          <div className="flex-1" />
          <Button unstyled
            type="button"
            onClick={handleExport}
            disabled={visibleRecords.length === 0}
            className="px-3 py-1.5 rounded-md border border-slate-200 bg-white text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Export AI decisions log (CSV)
          </Button>
        </div>
        <details className="mt-2 group">
          <summary className="inline-flex items-center gap-1.5 cursor-pointer list-none text-sm font-medium text-slate-600 hover:text-navy-800 [&::-webkit-details-marker]:hidden">
            <span className="text-slate-400 transition-transform group-open:rotate-90" aria-hidden="true">▸</span>
            How this works
          </summary>
          <div className="mt-2 max-w-3xl space-y-2 text-sm text-slate-500 leading-relaxed">
            <p>
              ReloPass AI reviews each relocation case and suggests the{' '}
              <strong className="font-medium text-slate-700">policy tier</strong> that applies to the employee, the{' '}
              <strong className="font-medium text-slate-700">service providers</strong> best suited to the destination, and
              the <strong className="font-medium text-slate-700">immigration pathway</strong> for the move. It only ever
              recommends — a person on your team accepts, overrides, or rejects every suggestion before it takes effect.
            </p>
            <p>
              This page is the record of those decisions. Each row is one AI recommendation and what your team decided about
              it, with the reason they gave. Rows are only ever added — never edited or deleted — so the log stays a faithful
              history. It is your human-oversight record under EU AI Act Art. 14(4)(c).
            </p>
          </div>
        </details>
      </div>

      <div className="px-6 py-5 border-b border-slate-100">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {STAT_TILES.map((t) => (
            <Card key={t.key} padding="sm">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${t.dot}`} aria-hidden="true" />
                <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{t.label}</span>
              </div>
              {loading ? (
                <div className="mt-2 h-7 w-12 animate-pulse rounded bg-slate-100" />
              ) : (
                <p className={`mt-1 text-2xl font-semibold tabular-nums ${t.value}`}>{counts[t.key]}</p>
              )}
            </Card>
          ))}
        </div>
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
        {recommendationIdFilter && (
          <span className="inline-flex items-center gap-2 px-2 py-1 rounded-md bg-accent-50 text-xs text-accent-700 ring-1 ring-accent-200">
            <span>
              recommendation_id: <span className="font-mono">{recommendationIdFilter}</span>
            </span>
            <Button unstyled
              type="button"
              onClick={clearRecommendationFilter}
              className="text-accent-500 hover:text-accent-700"
              aria-label="Clear recommendation_id filter"
            >
              ×
            </Button>
          </span>
        )}
      </div>

      <div className="px-6 py-5">
        {loading && (
          <div className="space-y-2" aria-busy="true" aria-label="Loading AI decisions">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-11 animate-pulse rounded bg-slate-100" />
            ))}
          </div>
        )}
        {error && !loading && (
          <p className="text-sm text-rose-600">{error}</p>
        )}
        {!loading && !error && visibleRecords.length === 0 && (
          <div className="text-center py-10">
            <p className="text-sm text-slate-500">No AI decisions recorded yet.</p>
            <p className="text-xs text-slate-400 mt-1">As HR admins accept, override, or reject AI recommendations, they will appear here.</p>
          </div>
        )}
        {!loading && !error && visibleRecords.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-slate-500 uppercase tracking-wider border-b border-slate-200">
                  <th className="text-left py-2 pr-3 font-medium">When</th>
                  <th className="text-left py-2 pr-3 font-medium">Feature</th>
                  <th className="text-left py-2 pr-3 font-medium">Recommendation ID</th>
                  <th className="text-left py-2 pr-3 font-medium">Decision</th>
                  <th className="text-left py-2 pr-3 font-medium">Reason</th>
                </tr>
              </thead>
              <tbody>
                {visibleRecords.map((r) => {
                  const priorId = priorDecisionId(r);
                  const priorLoaded = priorId ? loadedIds.has(priorId) : false;
                  return (
                    <tr
                      key={r.id}
                      ref={(el) => { rowRefs.current[r.id] = el; }}
                      className={`border-b border-slate-100 last:border-b-0 align-top transition-colors ${
                        highlightId === r.id ? 'bg-amber-50' : ''
                      }`}
                    >
                      <td className="py-3 pr-3 text-xs text-slate-500 whitespace-nowrap">{formatTimestamp(r.created_at)}</td>
                      <td className="py-3 pr-3 text-xs text-slate-700">{r.feature}</td>
                      <td className="py-3 pr-3 text-xs text-slate-700 max-w-xs truncate" title={r.recommendation_id}>
                        <div className="flex items-center gap-2">
                          <span className="truncate">{r.recommendation_id}</span>
                          {priorId && (
                            <Button unstyled
                              type="button"
                              onClick={() => priorLoaded && handlePriorClick(priorId)}
                              disabled={!priorLoaded}
                              title={priorLoaded ? 'Scroll to prior decision' : 'Prior decision is outside the current view'}
                              className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium ring-1 transition-colors ${
                                priorLoaded
                                  ? 'bg-accent-50 text-accent-700 ring-accent-200 hover:bg-accent-100 cursor-pointer'
                                  : 'bg-slate-50 text-slate-400 ring-slate-200 cursor-not-allowed'
                              }`}
                            >
                              ← prior
                            </Button>
                          )}
                        </div>
                      </td>
                      <td className="py-3 pr-3">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium uppercase tracking-wide ${DECISION_BADGE[r.decision]}`}>
                          {r.decision}
                        </span>
                      </td>
                      <td className="py-3 pr-3 text-xs text-slate-600 max-w-md">
                        {r.reason ? <span className="italic">&quot;{r.reason}&quot;</span> : <span className="text-slate-300">—</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppShell>
  );
}
