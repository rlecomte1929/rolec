import React, { useEffect, useState } from 'react';
import { Button, Card } from '../../components/antigravity';
import { expenseClaimsAPI, type ExpenseClaim } from '../../api/expenseClaims';
import { formatServicesMoney } from './servicesCurrency';

export const HrExpenseClaimsCard: React.FC<{ caseId: string }> = ({ caseId }) => {
  const [claims, setClaims] = useState<ExpenseClaim[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    expenseClaimsAPI
      .list(caseId)
      .then((rows) => {
        if (!cancelled) setClaims(rows);
      })
      .catch(() => {
        if (!cancelled) setClaims([]);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  const reload = () => {
    expenseClaimsAPI.list(caseId).then(setClaims).catch(() => setClaims([]));
  };

  const act = async (id: string, status: 'approved' | 'rejected' | 'paid') => {
    setBusyId(id);
    try {
      await expenseClaimsAPI.patch(id, { status });
      reload();
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Card padding="lg" className="mt-6">
      <p className="text-sm font-semibold text-navy-900 mb-1">Expense claims</p>
      <p className="text-sm text-navy-600 mb-3">
        Approve, reject, or mark paid. Only approved and paid lines draw down the allowance.
      </p>
      {claims.length === 0 ? (
        <p className="text-sm text-navy-600">No claims on this case yet.</p>
      ) : (
        <ul className="space-y-3">
          {claims.map((claim) => {
            const total = claim.lines.reduce(
              (sum, line) => sum + Number(line.amount_in_cap_currency ?? line.amount ?? 0),
              0,
            );
            const ccy = claim.lines[0]?.cap_currency || claim.lines[0]?.currency || 'EUR';
            return (
              <li key={claim.id} className="border border-navy-100 rounded-lg p-3">
                <p className="text-sm font-medium text-navy-900">
                  {formatServicesMoney(total, ccy)} · {claim.status}
                </p>
                {claim.lines[0]?.vendor_name && (
                  <p className="text-xs text-navy-600">{claim.lines[0].vendor_name}</p>
                )}
                {claim.status === 'submitted' && (
                  <div className="mt-2 flex gap-2">
                    <Button
                      disabled={busyId === claim.id}
                      onClick={() => act(claim.id, 'approved')}
                    >
                      Approve
                    </Button>
                    <Button
                      variant="outline"
                      disabled={busyId === claim.id}
                      onClick={() => act(claim.id, 'rejected')}
                    >
                      Reject
                    </Button>
                  </div>
                )}
                {claim.status === 'approved' && (
                  <div className="mt-2">
                    <Button disabled={busyId === claim.id} onClick={() => act(claim.id, 'paid')}>
                      Mark paid
                    </Button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
};
