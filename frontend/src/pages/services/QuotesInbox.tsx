import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Button, Card } from '../../components/antigravity';
import { rfqAPI } from '../../api/client';
import type { RfqSummary } from '../../api/client';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';

export const QuotesInbox: React.FC = () => {
  const navigate = useNavigate();
  const { assignmentId } = useEmployeeAssignment();
  const [rfqs, setRfqs] = useState<RfqSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!assignmentId) {
      setRfqs([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await rfqAPI.listByAssignment(assignmentId);
      setRfqs(data.rfqs || []);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      setError(String(msg || 'Failed to load RFQs'));
      setRfqs([]);
    } finally {
      setLoading(false);
    }
  }, [assignmentId]);

  useEffect(() => {
    load();
  }, [load]);

  if (!assignmentId) {
    return (
      <AppShell title="Quotes inbox" subtitle="Track vendor replies and quotation threads.">
        <Card padding="lg">
          <p className="text-sm text-[#6b7280]">
            Sign in as an employee or select an assignment to view RFQs and quotes.
          </p>
        </Card>
      </AppShell>
    );
  }

  if (loading) {
    return (
      <AppShell title="Quotes inbox" subtitle="Loading RFQs...">
        <Card padding="lg">
          <p className="text-sm text-[#6b7280]">Loading...</p>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell title="Quotes inbox" subtitle="Track vendor replies and quotation threads.">
      <Card padding="lg" className="space-y-4">
        {error && (
          <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}
        {rfqs.length === 0 && !error ? (
          <div className="space-y-3">
            <p className="text-sm text-[#6b7280]">
              No RFQs yet. Create one from the services flow after shortlisting vendors.
            </p>
            <Button onClick={() => navigate('/services/rfq/new')}>Create RFQ</Button>
          </div>
        ) : (
          <div className="space-y-3">
            {rfqs.map((rfq) => (
              <div
                key={rfq.id}
                className="flex items-center justify-between rounded-lg border border-[#e2e8f0] p-4 hover:bg-[#f8fafc]"
              >
                <div>
                  <div className="font-medium text-[#0b2b43]">{rfq.rfq_ref}</div>
                  <div className="text-sm text-[#6b7280]">
                    {rfq.items?.length || 0} items · {rfq.recipients?.length || 0} recipients ·{' '}
                    {rfq.status}
                  </div>
                </div>
                <Button
                  variant="secondary"
                  onClick={() => navigate(`/quotes/rfq/${rfq.id}`)}
                >
                  View
                </Button>
              </div>
            ))}
          </div>
        )}
      </Card>
    </AppShell>
  );
};
