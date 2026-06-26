/**
 * CaseBudgetPanel — T12 (MVP-7)
 *
 * Displays estimated budget line items for a case, grouped by category,
 * with a grand total row.
 *
 * Data source: GET /api/hr/cases/:caseId/budget-lines
 * Fails silently (renders nothing) if the fetch errors or returns an
 * empty list.
 */
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../../api/client';

// ── Types ─────────────────────────────────────────────────────────────────────

interface BudgetLine {
  id: string;
  case_id: string;
  category: string;
  estimated_eur: number;
  created_at: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatEur(amount: number): string {
  return new Intl.NumberFormat('en-IE', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(amount);
}

const CATEGORY_ICONS: Record<string, string> = {
  immigration:       '📋',
  housing:           '🏠',
  moving:            '🚛',
  tax:               '📊',
  school:            '🎓',
  destination:       '🗺️',
};

function categoryIcon(raw: string): string {
  return CATEGORY_ICONS[raw.toLowerCase()] ?? '💼';
}

// ── Component ─────────────────────────────────────────────────────────────────

interface CaseBudgetPanelProps {
  caseId: string;
}

export const CaseBudgetPanel: React.FC<CaseBudgetPanelProps> = ({ caseId }) => {
  const budgetQuery = useQuery({
    queryKey: ['case', caseId, 'budget-lines'],
    queryFn: () => apiGet<BudgetLine[]>(`/api/cases/${caseId}/budget-lines`),
    enabled: !!caseId,
  });
  // Fail silently (errors → []) — preserve the original soft-fail behaviour.
  const lines: BudgetLine[] = budgetQuery.data ?? [];
  const loading = budgetQuery.isLoading;

  if (loading || lines.length === 0) return null;

  const total = lines.reduce((sum, l) => sum + l.estimated_eur, 0);

  return (
    <div className="rounded-lg border border-[#e2e8f0] bg-white overflow-hidden">
      <div className="px-4 py-3 border-b border-[#f1f5f9] flex items-center gap-2">
        <span className="text-base">💰</span>
        <h3 className="text-sm font-semibold text-[#0b2b43]">Estimated budget</h3>
        <span className="ml-auto text-xs font-semibold text-[#0b2b43]">{formatEur(total)} total</span>
      </div>

      <div className="divide-y divide-[#f1f5f9]">
        {lines.map((line) => (
          <div
            key={line.id}
            className="flex items-center justify-between px-4 py-3 hover:bg-[#f8fafc] transition-colors"
          >
            <div className="flex items-center gap-2.5">
              <span className="text-base leading-none" aria-hidden>
                {categoryIcon(line.category)}
              </span>
              <span className="text-sm text-[#374151]">{line.category}</span>
            </div>
            <span className="text-sm font-semibold text-[#0f172a] tabular-nums">
              {formatEur(line.estimated_eur)}
            </span>
          </div>
        ))}

        {/* Grand total row */}
        <div className="flex items-center justify-between px-4 py-3 bg-[#f8fafc]">
          <span className="text-sm font-semibold text-[#0b2b43]">Total (estimated)</span>
          <span className="text-base font-bold text-[#0b2b43] tabular-nums">
            {formatEur(total)}
          </span>
        </div>
      </div>

      <div className="px-4 py-2.5 border-t border-[#f1f5f9] bg-[#f8fafc]">
        <p className="text-xs text-[#94a3b8]">
          Estimates in EUR · Actuals depend on supplier quotes and currency fluctuation
        </p>
      </div>
    </div>
  );
};
