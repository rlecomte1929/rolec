import React, { useEffect, useState } from 'react';
import { Card } from '../antigravity';
import { env } from '../../config/env';
import { getProductMetrics, type ProductMetrics } from '../../api/adminProductMetrics';

// PostHog app host (where events/insights are viewed) is derived from the ingest
// host, mirroring TestDriveTab: ingest = eu.i.posthog.com, app = eu.posthog.com.
const POSTHOG_APP_HOST = (env.posthogHost || 'https://eu.i.posthog.com').replace(
  '.i.posthog.com',
  '.posthog.com',
);

const DAY_OPTIONS = [7, 30, 90] as const;

function Tile({ label, value, sub }: { label: string; value: number; sub?: string }) {
  return (
    <Card>
      <div className="text-xs text-[#6b7280]">
        {label}
        {sub ? <span className="text-[#1f8e8b]"> · {sub}</span> : null}
      </div>
      <div className="text-2xl font-semibold text-[#0b2b43] tabular-nums">{value}</div>
    </Card>
  );
}

/**
 * Product-metrics tab in the admin Feedback section. Reads the PostHog product
 * events that are mirrored into analytics_events (GET /api/admin/product-metrics)
 * and renders headline counts, funnel rates, and a daily breakdown. PostHog
 * remains the place for deep analysis (funnels, session replay) — link out to it.
 */
export const ProductMetricsTab: React.FC = () => {
  const [days, setDays] = useState<number>(30);
  const [data, setData] = useState<ProductMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getProductMetrics(days)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load product metrics');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [days]);

  const e = data?.events ?? {};
  const num = (k: string) => e[k] ?? 0;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-1 rounded-lg bg-[#f3f4f6] p-1">
          {DAY_OPTIONS.map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDays(d)}
              className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
                days === d ? 'bg-white text-[#0b2b43] shadow-sm' : 'text-[#6b7280] hover:text-[#0b2b43]'
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
        <a
          href={POSTHOG_APP_HOST}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-medium text-[#1f8e8b] underline underline-offset-2 hover:text-[#197c79]"
        >
          Open PostHog →
        </a>
      </div>

      {error && (
        <Card>
          <p className="text-sm text-[#b91c1c]">{error}</p>
        </Card>
      )}

      {loading && !data && <p className="py-8 text-center text-sm text-[#6b7280]">Loading product metrics…</p>}

      {data && (
        <>
          <div className="mb-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Tile label="Cases created" value={num('case_created')} />
            <Tile label="Cases assigned" value={num('case_assigned')} />
            <Tile label="Policies published" value={num('policy_published')} />
            <Tile
              label="Wizards completed"
              value={num('wizard_completed')}
              sub={`${data.rates.wizard_completion_pct}% of steps`}
            />
            <Tile label="Estimate reviews" value={num('estimate_review_opened')} />
            <Tile
              label="Exception requests"
              value={num('exception_request_submitted')}
              sub={`${data.rates.exception_request_pct}% of reviews`}
            />
            <Tile
              label="Exceptions decided"
              value={num('exception_request_decided')}
              sub={`${data.rates.exception_decided_pct}% of requests`}
            />
            <Tile label="Wizard steps" value={num('wizard_step_completed')} />
          </div>

          <Card>
            <div className="mb-2 text-sm font-medium text-[#0b2b43]">Daily breakdown (last {data.period_days} days)</div>
            {data.daily.length === 0 ? (
              <p className="py-4 text-center text-sm text-[#6b7280]">No product events recorded in this window yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[#e5e7eb] text-left text-[#6b7280]">
                      <th className="py-2 pr-3">Date</th>
                      <th className="py-2 pr-3 text-right">Cases</th>
                      <th className="py-2 pr-3 text-right">Policies</th>
                      <th className="py-2 pr-3 text-right">Wizards done</th>
                      <th className="py-2 pr-3 text-right">Estimates</th>
                      <th className="py-2 text-right">Exceptions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.daily.map((d) => (
                      <tr key={d.date} className="border-b border-[#f3f4f6] tabular-nums">
                        <td className="py-2 pr-3 font-mono text-[#374151]">{d.date}</td>
                        <td className="py-2 pr-3 text-right">{d.case_created ?? 0}</td>
                        <td className="py-2 pr-3 text-right">{d.policy_published ?? 0}</td>
                        <td className="py-2 pr-3 text-right">{d.wizard_completed ?? 0}</td>
                        <td className="py-2 pr-3 text-right">{d.estimate_review_opened ?? 0}</td>
                        <td className="py-2 text-right">{d.exception_request_submitted ?? 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
};
