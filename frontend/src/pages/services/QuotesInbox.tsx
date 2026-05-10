import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { EmployeeScopedAssignmentPicker } from '../../components/employee/EmployeeScopedAssignmentPicker';
import { Button, Card } from '../../components/antigravity';
import { rfqAPI } from '../../api/client';
import type { RfqSummary } from '../../api/client';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { buildRoute } from '../../navigation/routes';
import { parseAssignmentSearchParam, resolveScopedAssignmentId, withAssignmentQuery } from '../../utils/employeeAssignmentScope';

export const QuotesInbox: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    assignmentId: primaryAssignmentId,
    linkedSummaries,
    isLoading: assignmentLoading,
  } = useEmployeeAssignment();
  const queryAssignmentId = useMemo(() => parseAssignmentSearchParam(location.search), [location.search]);
  const { effectiveId: assignmentId, needsPicker } = useMemo(
    () =>
      resolveScopedAssignmentId({
        linkedSummaries,
        primaryAssignmentId,
        queryAssignmentId,
      }),
    [linkedSummaries, primaryAssignmentId, queryAssignmentId]
  );
  const [rfqs, setRfqs] = useState<RfqSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!assignmentId || needsPicker) {
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
  }, [assignmentId, needsPicker]);

  useEffect(() => {
    load();
  }, [load]);

  if (assignmentLoading) {
    return (
      <AppShell title="Quotes inbox" subtitle="RFQs and vendor replies.">
        <Card padding="lg">
          <p className="text-sm text-[#6b7280]">Loading…</p>
        </Card>
      </AppShell>
    );
  }

  if (!assignmentLoading && needsPicker && linkedSummaries.length > 0) {
    return (
      <AppShell title="Quotes inbox" subtitle="RFQs and vendor replies.">
        <EmployeeScopedAssignmentPicker
          title="Which assignment’s quotes?"
          subtitle="Pick which assignment this inbox is for."
          linkedSummaries={linkedSummaries}
          targetBasePath={buildRoute('quotesInbox')}
        />
      </AppShell>
    );
  }

  if (!assignmentId) {
    return (
      <AppShell title="Quotes inbox" subtitle="RFQs and vendor replies.">
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
      <AppShell title="Quotes inbox" subtitle="Loading…">
        <Card padding="lg">
          <p className="text-sm text-[#6b7280]">Loading...</p>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell title="Quotes inbox" subtitle="RFQs and vendor replies.">
      <Card padding="lg" className="space-y-4">
        {error && (
          <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}
        {rfqs.length === 0 && !error ? (
          <div className="space-y-3">
            <p className="text-sm text-[#6b7280]">
              No RFQs yet. Create one from the services flow after shortlisting vendors.
            </p>
            <Button onClick={() => navigate(withAssignmentQuery(buildRoute('servicesRfqNew'), assignmentId))}>
              Create RFQ
            </Button>
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
