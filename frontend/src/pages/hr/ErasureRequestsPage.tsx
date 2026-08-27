/**
 * ErasureRequestsPage — IMM-18
 *
 * HR/admin review queue for GDPR Art. 17 erasure requests. Lists pending
 * requests with the statutory 30-day deadline and lets the reviewer approve
 * (anonymises the case's immigration profiles in place) or reject (records the
 * decision only). Route: /hr/compliance/erasure-requests
 */

import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AppShell } from '../../components/AppShell';
import { Badge, Button, Card } from '../../components/antigravity';
import { hrAPI } from '../../api/client';

interface ErasureRequest {
  id: string;
  case_id: string;
  employee_id: string;
  status: string;
  reason: string | null;
  requested_at: string | null;
  statutory_due_at: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  completed_at: string | null;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
  });
}

function daysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const target = new Date(dateStr);
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  target.setHours(0, 0, 0, 0);
  return Math.ceil((target.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
}

export const ErasureRequestsPage: React.FC = () => {
  const queryClient = useQueryClient();
  // `error` is also written by the approve/reject mutation, so keep it local.
  const [error, setError] = useState<string | null>(null);
  const [actioning, setActioning] = useState<string | null>(null);

  const requestsQuery = useQuery({
    queryKey: ['hr', 'erasure-requests', 'pending'],
    queryFn: () => hrAPI.listErasureRequests('pending'),
  });
  const requests: ErasureRequest[] = requestsQuery.data?.requests ?? [];
  const pendingCount = requestsQuery.data?.pending_count ?? 0;
  const loading = requestsQuery.isLoading;
  const displayedError = error || (requestsQuery.isError ? 'Could not load erasure requests.' : null);

  const handleAction = async (
    req: ErasureRequest,
    decision: 'approve' | 'reject',
  ) => {
    const confirmMsg = decision === 'approve'
      ? 'Approving permanently anonymises all immigration personal data on this case. This cannot be undone. Continue?'
      : 'Reject this erasure request?';
    if (!window.confirm(confirmMsg)) return;

    setActioning(req.id);
    try {
      await hrAPI.processErasureRequest(req.case_id, {
        request_id: req.id,
        decision,
      });
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ['hr', 'erasure-requests', 'pending'] });
    } catch {
      setError(`Could not ${decision} the request. Please retry.`);
    } finally {
      setActioning(null);
    }
  };

  return (
    <AppShell title="Erasure requests">
      <div className="max-w-3xl mx-auto py-8 px-4">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-[#f1f5f9]">
              GDPR erasure requests
            </h1>
            <p className="text-slate-500 text-sm mt-1">
              Employee right-to-erasure requests awaiting review (GDPR Art. 17).
            </p>
          </div>
          {pendingCount > 0 && (
            <Badge variant="warning">{pendingCount} pending</Badge>
          )}
        </div>

        {displayedError && (
          <div role="alert" className="mb-4 text-sm text-[#fca5a5]">{displayedError}</div>
        )}

        {loading ? (
          <p className="text-slate-500">Loading…</p>
        ) : requests.length === 0 ? (
          <Card className="p-6">
            <p className="text-slate-500">No pending erasure requests. 🎉</p>
          </Card>
        ) : (
          <div className="space-y-4">
            {requests.map((req) => {
              const daysLeft = daysUntil(req.statutory_due_at);
              const overdue = daysLeft !== null && daysLeft < 0;
              const dueSoon = daysLeft !== null && daysLeft >= 0 && daysLeft <= 7;
              return (
                <Card key={req.id} className="p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <p className="text-sm text-[#f1f5f9] font-medium">
                        Case {req.case_id}
                      </p>
                      <p className="text-xs text-slate-500 mt-1">
                        Requested {formatDate(req.requested_at)}
                        {' · due '}{formatDate(req.statutory_due_at)}
                      </p>
                      {req.reason && (
                        <p className="text-sm text-slate-500 mt-2">
                          “{req.reason}”
                        </p>
                      )}
                    </div>
                    {daysLeft !== null && (
                      <Badge variant={overdue ? 'error' : dueSoon ? 'warning' : 'neutral'}>
                        {overdue
                          ? `${Math.abs(daysLeft)}d overdue`
                          : `${daysLeft}d left`}
                      </Badge>
                    )}
                  </div>
                  <div className="flex gap-2 mt-4">
                    <Button
                      variant="primary"
                      size="sm"
                      disabled={actioning === req.id}
                      onClick={() => handleAction(req, 'approve')}
                    >
                      {actioning === req.id ? 'Working…' : 'Approve & erase'}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={actioning === req.id}
                      onClick={() => handleAction(req, 'reject')}
                    >
                      Reject
                    </Button>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </AppShell>
  );
};
