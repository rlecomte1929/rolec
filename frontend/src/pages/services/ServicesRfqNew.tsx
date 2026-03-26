import React, { useMemo, useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { EmployeeScopedAssignmentPicker } from '../../components/employee/EmployeeScopedAssignmentPicker';
import { Button, Card, Input } from '../../components/antigravity';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { useServicesFlow } from '../../features/services/ServicesFlowContext';
import { RfqWorkflowDiagram } from '../../features/services/RfqWorkflowDiagram';
import { ServicesNavRibbon } from '../../features/services/ServicesNavRibbon';
import { buildRoute } from '../../navigation/routes';
import { parseAssignmentSearchParam, resolveScopedAssignmentId, withAssignmentQuery } from '../../utils/employeeAssignmentScope';

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
  const [notes, setNotes] = useState<Record<string, string>>({});

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
              navigate(withAssignmentQuery(buildRoute('servicesRecommendations'), assignmentId))
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
          <span className="text-[#64748b]">(Request For Quotation)</span> — you send your requirements to vendors; they
          reply with <strong>proposed prices</strong>. ReloPass will help you manage that flow; sending requests from
          here is <strong>not available yet</strong>.
        </p>
      </div>

      <RfqWorkflowDiagram />

      <Card padding="lg" className="mt-6 border border-[#bfdbfe] bg-[#f8fafc]">
        <h3 className="text-base font-semibold text-[#0b2b43] mb-2">Coming soon</h3>
        <p className="text-sm text-[#374151] mb-4 leading-relaxed">
          We&apos;re still building the step where your quotation requests go out to vendors automatically. Your
          shortlist and notes below stay saved in this browser for when sending goes live.
        </p>
        <p className="text-sm font-semibold text-[#0b2b43] mb-2">What you can do now</p>
        <ul className="text-sm text-[#374151] list-disc list-inside space-y-2 mb-5">
          <li>
            Use <strong>Resources</strong> for guides (visas, housing, schools, and more).
          </li>
          <li>
            Use <strong>My case</strong>, <strong>HR Policy</strong>, and <strong>Compensation &amp; Allowance</strong>{' '}
            for intake details and policy limits.
          </li>
          <li>Review your shortlist below and add optional notes for each vendor (saved locally until RFQ send is live).</li>
        </ul>
        <div className="flex flex-wrap gap-3">
          <Link
            to={withAssignmentQuery(buildRoute('resources'), assignmentId)}
            className="inline-flex items-center justify-center font-medium rounded-lg px-4 py-2.5 bg-[#0b2b43] text-white hover:bg-[#123651] transition-colors"
          >
            Explore Resources
          </Link>
          <Button
            variant="outline"
            onClick={() =>
              navigate(withAssignmentQuery(buildRoute('servicesRecommendations'), assignmentId))
            }
          >
            Back to recommendations
          </Button>
        </div>
      </Card>

      <p className="text-sm font-medium text-[#0b2b43] mt-8 mb-3">Your shortlisted vendors</p>
      <p className="text-xs text-[#64748b] mb-4">
        When quotation requests go live, these are the providers we&apos;ll use as your starting list.
      </p>
      {shortlisted.map(({ service, vendor }) => (
        <div key={`${service}-${vendor.item_id}`} className="border border-[#e2e8f0] rounded-lg p-4 mb-3 bg-white">
          <div className="font-semibold text-[#0b2b43]">{vendor.name}</div>
          <div className="text-sm text-[#6b7280] mb-2">Service: {SERVICE_LABELS[service] || service}</div>
          <Input
            label="Optional note (saved in this browser for later)"
            value={notes[vendor.item_id] || ''}
            onChange={(val) => setNotes((prev) => ({ ...prev, [vendor.item_id]: val }))}
            placeholder="e.g. Moving date, special requirements…"
            fullWidth
          />
        </div>
      ))}
      <div className="flex justify-end mt-4">
        <Button type="button" variant="outline" disabled title="Available when vendor quoting goes live">
          Send quotation requests (coming soon)
        </Button>
      </div>
    </AppShell>
  );
};
