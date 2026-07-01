import React, { useState } from 'react';
import { Card, Button, Input, Badge, Alert } from '../../components/antigravity';
import { hrAPI, type OptimizeBenefitMixResponse } from '../../api/client';
import { useHrCompanyContext } from '../../contexts/HrCompanyContext';

// [Parker-B] HR-facing UI over POST /api/hr/{company_id}/optimize-benefit-mix.
// Candidates carry their own expected_satisfaction so the optimizer runs on an
// empty/pre-launch DB (no benefit_priors seeding required — the endpoint only
// 422s when a candidate omits satisfaction AND no prior exists).

interface Row {
  id: string;
  label: string;
  category: string;
  cost: number;
  satisfaction: number;
  mandatory: boolean;
}

// Satisfaction is on a 0–1 scale: the optimizer's default variance is 0.25·s²
// and default λ=0.3, so utility = s − 0.075·s² is only positive for small s.
// Values on a 0–1 scale keep every benefit's utility positive so a real
// portfolio is selected; a 0–100 scale would make the optimum the empty set.
const SEED_ROWS: Row[] = [
  { id: 'temp-housing', label: 'Temporary housing (30d)', category: 'Housing', cost: 3000, satisfaction: 0.78, mandatory: false },
  { id: 'home-search', label: 'Home-search assistance', category: 'Housing', cost: 1500, satisfaction: 0.60, mandatory: false },
  { id: 'language', label: 'Language training', category: 'Integration', cost: 1200, satisfaction: 0.66, mandatory: false },
  { id: 'school-search', label: 'School placement', category: 'Family', cost: 2000, satisfaction: 0.82, mandatory: false },
  { id: 'spousal', label: 'Spousal / partner support', category: 'Family', cost: 1800, satisfaction: 0.55, mandatory: false },
  { id: 'shipping', label: 'Household goods shipping', category: 'Logistics', cost: 2500, satisfaction: 0.50, mandatory: false },
];

const INFEASIBILITY_COPY: Record<string, string> = {
  mandatory_exceeds_budget: 'The benefits marked as required already cost more than the budget. Raise the budget or unmark some as required.',
  mandatory_exceeds_category_cap: 'A required benefit exceeds a category cap.',
  no_feasible_mix: 'No combination of these benefits fits the budget. Try raising the budget or lowering costs.',
};

interface Props {
  embedded?: boolean;
}

export const HrBenefitMixOptimizerPage: React.FC<Props> = () => {
  const { companyId } = useHrCompanyContext();
  const [rows, setRows] = useState<Row[]>(SEED_ROWS);
  const [budget, setBudget] = useState<number>(6000);
  const [lambdaRisk, setLambdaRisk] = useState<number>(0.3);
  const [result, setResult] = useState<OptimizeBenefitMixResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const updateRow = (id: string, patch: Partial<Row>) =>
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  const removeRow = (id: string) => setRows((rs) => rs.filter((r) => r.id !== id));

  const selectedSet = new Set(result?.selected ?? []);

  const runOptimize = async () => {
    if (!companyId) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await hrAPI.optimizeBenefitMix(companyId, {
        budget,
        lambda_risk: lambdaRisk,
        category_caps: {},
        mandatory_ids: [],
        min_coverage: 0,
        candidates: rows.map((r) => ({
          id: r.id,
          category: r.category,
          cost_per_employee: r.cost,
          expected_satisfaction: r.satisfaction,
          mandatory: r.mandatory,
        })),
      });
      setResult(res);
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Could not run the optimizer. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-base font-semibold text-[#0b2b43]">Optimize benefit mix</h2>
        <p className="text-sm text-[#6b7280] mt-1">
          Given a per-employee budget, find the benefit portfolio that maximises expected satisfaction
          (risk-adjusted). Edit the catalogue below, set a budget, and run the optimizer.
        </p>
      </div>

      {!companyId && (
        <Alert variant="info" title="No company selected">
          Select or switch to a company to run the optimizer — it is scoped per employer.
        </Alert>
      )}

      {/* Controls */}
      <Card padding="lg">
        <div className="flex flex-wrap items-end gap-4">
          <div className="w-44">
            <Input
              label="Budget per employee (€)"
              type="number"
              min={0}
              value={budget}
              onChange={(v) => setBudget(Math.max(0, Number(v) || 0))}
            />
          </div>
          <div className="w-44">
            <Input
              label="Risk aversion (λ, 0–5)"
              type="number"
              min={0}
              max={5}
              step={0.1}
              value={lambdaRisk}
              onChange={(v) => setLambdaRisk(Math.min(5, Math.max(0, Number(v) || 0)))}
            />
          </div>
          <Button variant="primary" onClick={() => void runOptimize()} disabled={loading || !companyId}>
            {loading ? 'Optimizing…' : 'Optimize'}
          </Button>
        </div>
      </Card>

      {error && (
        <Alert variant="error" title="Optimizer error">
          {error}
        </Alert>
      )}

      {result && !result.feasible && (
        <Alert variant="warning" title="No feasible mix">
          {INFEASIBILITY_COPY[result.infeasibility_reason ?? ''] ?? 'No feasible benefit mix for these inputs.'}
        </Alert>
      )}

      {result && result.feasible && (
        <Card padding="lg">
          <div className="flex flex-wrap items-center gap-3 mb-3">
            <span className="text-3xl font-semibold text-[#0b2b43]">€{result.total_cost.toLocaleString()}</span>
            <span className="text-sm text-[#6b7280]">
              of €{budget.toLocaleString()} budget · {selectedSet.size} benefit{selectedSet.size === 1 ? '' : 's'}
            </span>
            <Badge variant="success">Utility {result.achieved_utility.toFixed(1)}</Badge>
            <Badge variant="info">+€1000 budget → +{result.shadow_prices.budget_per_1000.toFixed(1)} utility</Badge>
          </div>
          <p className="text-xs text-[#94a3b8]">
            The shadow price is the marginal satisfaction each extra €1000 of budget would unlock — use it to justify a budget increase.
          </p>
        </Card>
      )}

      {/* Candidate catalogue */}
      <Card padding="lg">
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">Benefit catalogue</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-[#6b7280] font-medium">
                <th className="py-2 pr-4">Benefit</th>
                <th className="py-2 pr-4">Category</th>
                <th className="py-2 pr-4 text-right">Cost / employee (€)</th>
                <th className="py-2 pr-4 text-right">Expected satisfaction (0–1)</th>
                <th className="py-2 pr-4 text-center">Required</th>
                <th className="py-2 pr-4" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const chosen = selectedSet.has(r.id);
                return (
                  <tr key={r.id} className={`border-b border-slate-100 ${chosen ? 'bg-emerald-50' : ''}`}>
                    <td className="py-2 pr-4 font-medium text-[#0b2b43]">
                      <span className="inline-flex items-center gap-2">
                        {r.label}
                        {chosen && <Badge variant="success" size="sm">Selected</Badge>}
                      </span>
                    </td>
                    <td className="py-2 pr-4 text-[#6b7280]">{r.category}</td>
                    <td className="py-2 pr-4 text-right">
                      <input
                        type="number"
                        min={0}
                        aria-label={`${r.label} cost`}
                        className="w-24 rounded border border-slate-200 px-2 py-1 text-right text-sm"
                        value={r.cost}
                        onChange={(e) => updateRow(r.id, { cost: Math.max(0, Number(e.target.value) || 0) })}
                      />
                    </td>
                    <td className="py-2 pr-4 text-right">
                      <input
                        type="number"
                        min={0}
                        max={1}
                        step={0.05}
                        aria-label={`${r.label} expected satisfaction`}
                        className="w-20 rounded border border-slate-200 px-2 py-1 text-right text-sm"
                        value={r.satisfaction}
                        onChange={(e) => updateRow(r.id, { satisfaction: Math.min(1, Math.max(0, Number(e.target.value) || 0)) })}
                      />
                    </td>
                    <td className="py-2 pr-4 text-center">
                      <input
                        type="checkbox"
                        aria-label={`${r.label} required`}
                        checked={r.mandatory}
                        onChange={(e) => updateRow(r.id, { mandatory: e.target.checked })}
                      />
                    </td>
                    <td className="py-2 pr-4 text-right">
                      <button
                        type="button"
                        onClick={() => removeRow(r.id)}
                        className="text-xs text-slate-400 hover:text-red-500"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};
