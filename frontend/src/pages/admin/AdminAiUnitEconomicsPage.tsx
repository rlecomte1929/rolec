import React, { useEffect, useState } from 'react';
import { Card, Alert } from '../../components/antigravity';
import { getAiUnitEconomics } from '../../api/aiUnitEconomics';
import type { AiUnitEconomicsRollup } from '../../api/aiUnitEconomics';
import { AdminLayout } from './AdminLayout';

// Parker-G — read-only dashboard over GET /api/admin/ai-unit-economics.
// Surfaces per-call cost, tokens, and carbon attributed by customer + feature.
// Pre-launch the trace table is sparse, so an explicit empty state is required.

const usd = (v: number): string =>
  `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`;
const int = (v: number): string => v.toLocaleString();
const grams = (v: number): string => `${v.toLocaleString(undefined, { maximumFractionDigits: 2 })} g`;

const TotalCard: React.FC<{ label: string; value: string; sub?: string }> = ({ label, value, sub }) => (
  <Card className="border border-slate-200">
    <p className="text-xs font-medium text-slate-400">{label}</p>
    <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
    {sub && <p className="mt-0.5 text-xs text-slate-400">{sub}</p>}
  </Card>
);

export const AdminAiUnitEconomicsPage: React.FC = () => {
  const [data, setData] = useState<AiUnitEconomicsRollup | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    getAiUnitEconomics()
      .then((d) => {
        if (active) setData(d);
      })
      .catch(() => {
        if (active) setError('Could not load AI unit-economics.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <AdminLayout
      title="AI economics"
      subtitle="Per-call cost, tokens, and carbon for every AI feature, attributed by customer. Aggregated across all recorded usage."
    >
      {loading && <p className="text-sm text-slate-400">Loading…</p>}

      {error && (
        <Alert variant="error" title="Failed to load">
          {error}
        </Alert>
      )}

      {data && data.rows.length === 0 && (
        <Alert variant="info" title="No AI usage recorded yet">
          Cost, token, and carbon figures accumulate as the platform&apos;s AI features are used.
          This dashboard populates automatically once traces are recorded.
        </Alert>
      )}

      {data && data.rows.length > 0 && (
        <div className="space-y-6">
          {/* Totals */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <TotalCard label="Total cost" value={usd(data.totals.total_cost_usd)} sub={`${int(data.totals.n_calls)} AI calls`} />
            <TotalCard label="Tokens in" value={int(data.totals.total_tokens_in)} />
            <TotalCard label="Tokens out" value={int(data.totals.total_tokens_out)} />
            <TotalCard label="Carbon (CO₂e)" value={grams(data.totals.total_co2e_grams)} />
          </div>

          {/* Rollup table */}
          <Card padding="lg" className="border border-slate-200">
            <h2 className="mb-3 text-sm font-semibold text-slate-900">By customer &amp; feature</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-500 font-medium">
                    <th className="py-2 pr-4">Customer</th>
                    <th className="py-2 pr-4">Feature</th>
                    <th className="py-2 pr-4 text-right">Calls</th>
                    <th className="py-2 pr-4 text-right">Cost</th>
                    <th className="py-2 pr-4 text-right">Tokens in</th>
                    <th className="py-2 pr-4 text-right">Tokens out</th>
                    <th className="py-2 pr-4 text-right">CO₂e</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((r, i) => (
                    <tr key={`${r.customer_id ?? '∅'}:${r.feature_key}:${i}`} className="border-b border-slate-100">
                      <td className="py-2 pr-4 text-slate-700">
                        {r.customer_id ?? <span className="text-slate-400">—</span>}
                      </td>
                      <td className="py-2 pr-4 font-medium text-slate-900">{r.feature_key}</td>
                      <td className="py-2 pr-4 text-right tabular-nums text-slate-700">{int(r.n_calls)}</td>
                      <td className="py-2 pr-4 text-right tabular-nums text-slate-900">{usd(r.total_cost_usd)}</td>
                      <td className="py-2 pr-4 text-right tabular-nums text-slate-500">{int(r.total_tokens_in)}</td>
                      <td className="py-2 pr-4 text-right tabular-nums text-slate-500">{int(r.total_tokens_out)}</td>
                      <td className="py-2 pr-4 text-right tabular-nums text-slate-500">{grams(r.total_co2e_grams)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </AdminLayout>
  );
};
