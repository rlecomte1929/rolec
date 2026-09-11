import React, { useEffect, useState } from 'react';
import { Card, ProgressBar } from '../../components/antigravity';
import { budgetAPI, type BudgetDrawdown } from '../../api/budget';
import { formatServicesMoney } from './servicesCurrency';

export const ClaimRemainingBar: React.FC<{
  caseId: string;
  className?: string;
  drawdown?: BudgetDrawdown[];
}> = ({ caseId, className = '', drawdown: injected }) => {
  const [rows, setRows] = useState<BudgetDrawdown[]>(injected ?? []);
  const [loaded, setLoaded] = useState(Boolean(injected));

  useEffect(() => {
    if (injected) {
      setRows(injected);
      setLoaded(true);
      return;
    }
    let cancelled = false;
    budgetAPI
      .getBudgetSummary(caseId)
      .then((data) => {
        if (!cancelled) {
          setRows(data.drawdown || []);
          setLoaded(true);
        }
      })
      .catch(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, injected]);

  const withCap = rows.filter((r) => r.cap_amount != null && r.currency);
  if (!loaded || withCap.length === 0) return null;

  return (
    <Card padding="lg" className={className}>
      <p className="text-sm font-semibold text-navy-900 mb-3">Allowance remaining</p>
      <div className="space-y-4">
        {withCap.map((row) => {
          const cap = row.cap_amount ?? 0;
          const remaining = row.remaining;
          const claimed = row.claimed_approved ?? 0;
          const label =
            remaining == null
              ? `${row.name} — not comparable across currencies`
              : `${formatServicesMoney(remaining, row.currency || 'EUR')} of ${formatServicesMoney(cap, row.currency || 'EUR')} remaining`;
          const pct = cap > 0 ? Math.min(100, Math.max(0, (claimed / cap) * 100)) : 0;
          return (
            <div key={row.benefit_key}>
              <p className="text-sm text-navy-800 mb-1">{label}</p>
              <ProgressBar
                value={pct}
                showLabel={false}
                color={row.status === 'over_budget' ? 'red' : 'green'}
              />
            </div>
          );
        })}
      </div>
    </Card>
  );
};
