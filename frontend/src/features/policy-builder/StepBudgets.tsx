/**
 * Step 2 — Set budget caps per tier × corridor.
 * Renders a table: rows = tiers, columns = corridors (destination countries).
 * Each cell holds a BudgetCap (amount + currency or salary-multiple toggle).
 */
import React, { useState } from 'react';
import type { PolicyTier, PolicyBudgets, BudgetCap } from '../../types/relocationPolicy';
import { Button, Select } from '../../components/antigravity';

// Shared inline input style for budget cells
const inlineInput = 'border border-slate-200 rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-[#0b2b43] focus:ring-offset-1';

// Common destination corridors — HR can add more via free-text.
const DEFAULT_CORRIDORS = [
  { key: '*',    label: 'Any destination (default)' },
  { key: '*→US', label: '→ United States' },
  { key: '*→GB', label: '→ United Kingdom' },
  { key: '*→DE', label: '→ Germany' },
  { key: '*→FR', label: '→ France' },
  { key: '*→SG', label: '→ Singapore' },
];

const CURRENCIES = ['EUR', 'USD', 'GBP', 'CHF', 'SGD', 'AUD', 'CAD'].map((c) => ({
  value: c,
  label: c,
}));

const Tip: React.FC<{ text: string }> = ({ text }) => (
  <span className="relative group ml-1 inline-flex items-center cursor-help">
    <span className="w-4 h-4 rounded-full bg-slate-200 text-slate-500 text-xs flex items-center justify-center font-bold select-none">?</span>
    <span className="absolute left-6 top-0 z-20 hidden group-hover:block bg-[#0b2b43] text-white text-xs rounded px-2 py-1 w-60 shadow-lg pointer-events-none">
      {text}
    </span>
  </span>
);

function emptyCap(): BudgetCap {
  return { cap_type: 'absolute', amount: 0, currency: 'EUR' };
}

/** Return the cap for a tier+corridor, or empty default. */
function getCap(
  budgets: PolicyBudgets,
  tierId: string,
  corridor: string,
): BudgetCap {
  return budgets[tierId]?.[corridor] ?? emptyCap();
}

function setCap(
  budgets: PolicyBudgets,
  tierId: string,
  corridor: string,
  cap: BudgetCap,
): PolicyBudgets {
  return {
    ...budgets,
    [tierId]: {
      ...(budgets[tierId] ?? {}),
      [corridor]: cap,
    },
  };
}

type Props = {
  tiers: PolicyTier[];
  budgets: PolicyBudgets;
  onChange: (budgets: PolicyBudgets) => void;
  onBack: () => void;
  onNext: () => void;
};

export const StepBudgets: React.FC<Props> = ({
  tiers,
  budgets,
  onChange,
  onBack,
  onNext,
}) => {
  const [corridors, setCorridors] = useState<{ key: string; label: string }[]>(
    DEFAULT_CORRIDORS,
  );
  const [customCorridor, setCustomCorridor] = useState('');
  const [error, setError] = useState('');

  const addCorridor = () => {
    const key = customCorridor.trim();
    if (!key) return;
    if (corridors.find((c) => c.key === key)) {
      setCustomCorridor('');
      return;
    }
    setCorridors([...corridors, { key, label: key }]);
    setCustomCorridor('');
  };

  const handleNext = () => {
    setError('');
    onNext();
  };

  const updateCap = (tierId: string, corridor: string, patch: Partial<BudgetCap>) => {
    const existing = getCap(budgets, tierId, corridor);
    onChange(setCap(budgets, tierId, corridor, { ...existing, ...patch }));
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-[#0b2b43]">
          Set relocation budgets
          <Tip text="Define the maximum amount the company will cover for each tier and destination. More-specific destinations override the default." />
        </h2>
        <p className="text-sm text-slate-500 mt-1">
          For each tier and destination, set a budget cap. The "Any destination" row is the
          default used when no specific destination matches.
        </p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {/* Scrollable table */}
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-4 py-3 text-left font-semibold text-slate-600 whitespace-nowrap">
                Destination
              </th>
              {tiers.map((t) => (
                <th
                  key={t.id}
                  className="px-4 py-3 text-left font-semibold text-slate-600 whitespace-nowrap"
                >
                  {t.name || `Tier ${tiers.indexOf(t) + 1}`}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {corridors.map((corridor) => (
              <tr key={corridor.key} className="hover:bg-slate-50 transition-colors">
                <td className="px-4 py-3 font-medium text-slate-700 whitespace-nowrap">
                  {corridor.label}
                  {corridor.key === '*' && (
                    <span className="ml-1 text-xs text-slate-400">(default)</span>
                  )}
                </td>
                {tiers.map((tier) => {
                  const cap = getCap(budgets, tier.id, corridor.key);
                  return (
                    <td key={tier.id} className="px-4 py-3">
                      <div className="space-y-2">
                        {/* Cap type toggle */}
                        <div className="flex gap-2 text-xs">
                          <button
                            type="button"
                            className={`px-2 py-0.5 rounded border text-xs transition-colors ${cap.cap_type === 'absolute' ? 'bg-[#0b2b43] text-white border-[#0b2b43]' : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'}`}
                            onClick={() => updateCap(tier.id, corridor.key, { cap_type: 'absolute' })}
                          >
                            Lump sum
                          </button>
                          <button
                            type="button"
                            className={`px-2 py-0.5 rounded border text-xs transition-colors ${cap.cap_type === 'salary_multiple' ? 'bg-[#0b2b43] text-white border-[#0b2b43]' : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'}`}
                            onClick={() => updateCap(tier.id, corridor.key, { cap_type: 'salary_multiple' })}
                          >
                            × salary
                          </button>
                        </div>

                        {cap.cap_type === 'absolute' ? (
                          <div className="flex gap-1 items-center">
                            <input
                              type="number"
                              value={cap.amount === 0 ? '' : String(cap.amount)}
                              onChange={(e) =>
                                updateCap(tier.id, corridor.key, {
                                  amount: parseFloat(e.target.value) || 0,
                                })
                              }
                              placeholder="0"
                              className={`${inlineInput} w-24`}
                            />
                            <Select
                              value={cap.currency ?? 'EUR'}
                              onChange={(v) =>
                                updateCap(tier.id, corridor.key, { currency: v })
                              }
                              options={CURRENCIES}
                              fullWidth={false}
                            />
                          </div>
                        ) : (
                          <div className="flex gap-1 items-center">
                            <input
                              type="number"
                              value={cap.amount === 0 ? '' : String(cap.amount)}
                              onChange={(e) =>
                                updateCap(tier.id, corridor.key, {
                                  amount: parseFloat(e.target.value) || 0,
                                })
                              }
                              placeholder="1.5"
                              className={`${inlineInput} w-20`}
                            />
                            <span className="text-slate-500 text-xs">× monthly salary</span>
                          </div>
                        )}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add custom corridor */}
      <div className="flex gap-2 items-center">
        <input
          type="text"
          value={customCorridor}
          onChange={(e) => setCustomCorridor(e.target.value)}
          placeholder='Add destination, e.g. "FR→DE" or "*→JP"'
          className={`${inlineInput} w-64`}
          onKeyDown={(e) => e.key === 'Enter' && addCorridor()}
        />
        <Button variant="outline" size="sm" onClick={addCorridor} type="button">
          Add destination
        </Button>
        <span className="text-xs text-slate-400 hidden sm:block">
          Use <code>*</code> as a wildcard for any origin or destination.
        </span>
      </div>

      <div className="flex justify-between pt-2">
        <Button variant="outline" onClick={onBack} type="button">
          ← Back
        </Button>
        <Button onClick={handleNext} type="button">
          Next: Documents →
        </Button>
      </div>
    </div>
  );
};
