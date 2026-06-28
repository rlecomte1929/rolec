import React, { useMemo, useState } from 'react';
import { useNavigate, useLocation, useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { EmployeeScopedAssignmentPicker } from '../../components/employee/EmployeeScopedAssignmentPicker';
import { Button, Card, Input } from '../../components/antigravity';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { useServicesFlow } from '../../features/services/ServicesFlowContext';
import { employeeAPI } from '../../api/client';
import { RfqWorkflowDiagram } from '../../features/services/RfqWorkflowDiagram';
import { ServicesNavRibbon } from '../../features/services/ServicesNavRibbon';
import { buildRoute, type RouteKey } from '../../navigation/routes';
import { caseIdForAssignment, parseAssignmentSearchParam, resolveScopedAssignmentId } from '../../utils/employeeAssignmentScope';

const SERVICE_LABELS: Record<string, string> = {
  living_areas: 'Living Areas',
  schools: 'Schools',
  movers: 'Movers',
  banks: 'Banks',
  insurances: 'Insurance',
  electricity: 'Electricity',
};

const RFQ_SUBTITLE =
  'RFQ means Request For Quotation: you ask shortlisted vendors for formal prices, then compare their offers.';

export const ServicesRfqNew: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { recommendations, shortlist } = useServicesFlow();
  const {
    assignmentId: primaryAssignmentId,
    linkedSummaries,
    isLoading: assignmentLoading,
  } = useEmployeeAssignment();
  // [AIQ-1285] caseId from the path is authoritative; fall back to legacy ?assignment=.
  const { caseId: pathCaseId } = useParams<{ caseId?: string }>();
  const queryAssignmentId = useMemo(
    () => pathCaseId ?? parseAssignmentSearchParam(location.search),
    [pathCaseId, location.search],
  );
  const { effectiveId: assignmentId, needsPicker } = useMemo(
    () =>
      resolveScopedAssignmentId({
        linkedSummaries,
        primaryAssignmentId,
        queryAssignmentId,
      }),
    [linkedSummaries, primaryAssignmentId, queryAssignmentId]
  );
  // AIQ-1334: employee case sub-routes are keyed by case_id — build with the resolved case_id.
  const routeCaseId = caseIdForAssignment(linkedSummaries, assignmentId) ?? pathCaseId ?? '';
  const caseStep = (key: RouteKey) => buildRoute(key, { caseId: routeCaseId });
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  const shortlisted = useMemo(() => {
    if (!recommendations) return [];
    const items: Array<{ service: string; vendor: { item_id: string; name: string } }> = [];
    for (const [category, res] of Object.entries(recommendations)) {
      const selectedId = shortlist.get(category);
      if (!selectedId) continue;
      const vendor = res.recommendations.find((r) => r.item_id === selectedId);
      if (vendor) items.push({ service: category, vendor });
    }
    return items;
  }, [recommendations, shortlist]);

  const handleSend = async () => {
    if (!assignmentId || sending || sent || shortlisted.length === 0) return;
    setSending(true);
    setSendError(null);
    try {
      const combinedNotes =
        shortlisted
          .map(({ vendor }) => {
            const note = (notes[vendor.item_id] || '').trim();
            return note ? `${vendor.name}: ${note}` : null;
          })
          .filter(Boolean)
          .join(' | ') || undefined;
      await employeeAPI.createQuoteRequest({
        case_id: assignmentId,
        service_categories: shortlisted.map(({ service }) => service),
        notes: combinedNotes,
      });
      setSent(true);
    } catch (e) {
      setSendError((e as Error).message ?? 'Failed to send. Please try again.');
    } finally {
      setSending(false);
    }
  };

  if (assignmentLoading) {
    return (
      <AppShell title="Request quotations" subtitle={RFQ_SUBTITLE}>
        <ServicesNavRibbon />
        <Card padding="lg" className="border border-[#e2e8f0]">
          <div className="flex items-center gap-3 text-sm text-[#475569]" role="status" aria-live="polite">
            <div className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-[#0b2b43] border-t-transparent" />
            <span>Loading your assignment…</span>
          </div>
        </Card>
      </AppShell>
    );
  }

  if (needsPicker && linkedSummaries.length > 0) {
    return (
      <AppShell title="Request quotations" subtitle={RFQ_SUBTITLE}>
        <ServicesNavRibbon />
        <EmployeeScopedAssignmentPicker
          title="Which assignment is this for?"
          subtitle="Pick the assignment your shortlist belongs to."
          linkedSummaries={linkedSummaries}
          targetBasePath={buildRoute('servicesRfqNew')}
        />
      </AppShell>
    );
  }

  if (!assignmentId) {
    return (
      <AppShell title="Request quotations" subtitle={RFQ_SUBTITLE}>
        <ServicesNavRibbon />
        <Card padding="lg">
          <p className="text-sm text-[#6b7280]">
            Sign in as an employee with an active assignment to use this step.
          </p>
        </Card>
      </AppShell>
    );
  }

  if (shortlisted.length === 0) {
    return (
      <AppShell title="Request quotations" subtitle={RFQ_SUBTITLE}>
        <ServicesNavRibbon />
        <Card padding="lg">
          <p className="text-sm text-[#6b7280] mb-4">
            Build a shortlist first: choose one provider per service on the recommendations page, then come back here.
          </p>
          <Button
            onClick={() =>
              navigate(caseStep('caseServicesRecommendations'))
            }
          >
            Back to recommendations
          </Button>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell title="Request quotations (RFQ)" subtitle={RFQ_SUBTITLE}>
      <ServicesNavRibbon />

      <div className="mb-6 rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 text-sm text-[#334155] leading-relaxed">
        <p>
          <abbr title="Request For Quotation" className="no-underline font-semibold text-[#0b2b43]">
            RFQ
          </abbr>{' '}
          <span className="text-[#64748b]">(Request For Quotation)</span> — you send your requirements to your
          shortlisted vendors; they reply with <strong>proposed prices</strong>. ReloPass routes them to your HR team,
          who follow up — and each request is tracked on your roadmap.
        </p>
      </div>

      <RfqWorkflowDiagram />

      <p className="text-sm font-medium text-[#0b2b43] mt-8 mb-3">Your shortlisted vendors</p>
      <p className="text-xs text-[#64748b] mb-4">
        Add an optional note for each, then send. These are the providers your requests will go to.
      </p>
      {shortlisted.map(({ service, vendor }) => (
        <div key={`${service}-${vendor.item_id}`} className="border border-[#e2e8f0] rounded-lg p-4 mb-3 bg-white">
          <div className="font-semibold text-[#0b2b43]">{vendor.name}</div>
          <div className="text-sm text-[#6b7280] mb-2">Service: {SERVICE_LABELS[service] || service}</div>
          <Input
            label="Optional note"
            value={notes[vendor.item_id] || ''}
            onChange={(val) => setNotes((prev) => ({ ...prev, [vendor.item_id]: val }))}
            placeholder="e.g. Moving date, special requirements…"
            fullWidth
          />
        </div>
      ))}
      {sent ? (
        <div
          data-testid="rfq-sent"
          className="mt-4 flex items-start gap-2 rounded-lg border border-green-100 bg-green-50 p-3 text-sm text-green-700"
        >
          ✅ <span>Quotation requests sent — your HR team will follow up, and we&apos;ve added them to your roadmap.</span>
        </div>
      ) : (
        <div className="mt-4 flex flex-col items-end gap-2">
          {sendError && <p className="text-xs text-red-500">{sendError}</p>}
          <Button type="button" onClick={handleSend} disabled={sending}>
            {sending ? 'Sending…' : 'Send quotation requests'}
          </Button>
        </div>
      )}
    </AppShell>
  );
};
