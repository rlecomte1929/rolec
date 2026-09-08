/**
 * [AIQ-1438] Admin assistant-questions analytics — /admin/ai/questions
 *
 * What employees ask the policy assistant, ranked by canonical topic, from
 * GET /api/admin/workflow/assistant-topics. Raw question text is never stored
 * (PII-by-design), so ranking is at topic granularity. Support rate per topic is
 * shown with the antigravity ProgressBar; overall rates head the page.
 */
import React, { useEffect, useState } from 'react';
import { adminOpsAnalyticsAPI, type AssistantTopicsResponse } from '../../api/client';
import { Card, Badge, ProgressBar, Alert, Skeleton } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';

const StatTile: React.FC<{ label: string; value: string; hint?: string }> = ({ label, value, hint }) => (
  <Card padding="md" className="border border-slate-200">
    <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
    <p className="mt-1 text-2xl font-semibold text-slate-900 tabular-nums">{value}</p>
    {hint && <p className="mt-0.5 text-[11px] text-slate-400">{hint}</p>}
  </Card>
);

const supportColor = (pct: number): 'green' | 'yellow' | 'red' =>
  pct >= 70 ? 'green' : pct >= 40 ? 'yellow' : 'red';

export const AdminAssistantAnalyticsPage: React.FC = () => {
  const [data, setData] = useState<AssistantTopicsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(7);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    adminOpsAnalyticsAPI
      .getAssistantTopics({ days, limit: 20 })
      .then((res) => { if (!cancelled) setData(res); })
      .catch(() => { if (!cancelled) setError('Couldn’t load assistant analytics. Please try again.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days]);

  return (
    <AdminLayout
      title="Assistant questions"
      subtitle="What employees ask the policy assistant, ranked by topic. Raw question text is never stored — topics only."
    >
      <div className="mb-4 flex items-center gap-2">
        <label htmlFor="asst-days" className="text-sm text-slate-500">Period</label>
        <select
          id="asst-days"
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="rounded-md border border-slate-200 px-2 py-1 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-accent-500"
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {loading && <Skeleton className="h-64 w-full" />}
      {error && <Alert variant="error">{error}</Alert>}
      {!loading && !error && data && (
        <>
          <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatTile label="Questions asked" value={data.overall.asked.toLocaleString()} />
            <StatTile label="Support rate" value={`${data.overall.support_rate_pct}%`} hint="supported ÷ answered" />
            <StatTile label="Refusal rate" value={`${data.overall.refusal_rate_pct}%`} hint="refused ÷ asked" />
            <StatTile label="Refusals" value={data.overall.refusal.toLocaleString()} />
          </div>

          {data.topics.length === 0 ? (
            <Alert variant="info">No assistant activity in this period yet.</Alert>
          ) : (
            <Card padding="lg" className="border border-slate-200">
              <div className="divide-y divide-slate-100">
                {data.topics.map((t) => (
                  <div key={t.topic} className="flex items-center gap-4 py-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-sm font-medium text-slate-800">{t.topic}</span>
                        {t.refusal > 0 && <Badge variant="warning" size="sm">{t.refusal} refused</Badge>}
                      </div>
                      <p className="mt-0.5 text-xs text-slate-400">
                        {t.asked.toLocaleString()} asked · {t.supported} supported · {t.unsupported} unsupported
                      </p>
                    </div>
                    <div className="w-32 shrink-0">
                      <ProgressBar value={t.support_rate_pct} color={supportColor(t.support_rate_pct)} />
                    </div>
                  </div>
                ))}
              </div>
              <p className="mt-4 text-xs text-slate-400">Bar = support rate for the topic. Ranked by questions asked.</p>
            </Card>
          )}
        </>
      )}
    </AdminLayout>
  );
};
