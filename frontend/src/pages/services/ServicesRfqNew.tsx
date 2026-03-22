import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { EmployeeScopedAssignmentPicker } from '../../components/employee/EmployeeScopedAssignmentPicker';
import { Alert, Button, Card, Input } from '../../components/antigravity';
import { employeeAPI } from '../../api/client';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { useServicesFlow } from '../../features/services/ServicesFlowContext';
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

export const ServicesRfqNew: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { recommendations, shortlist } = useServicesFlow();
  const {
    assignmentId: primaryAssignmentId,
    linkedCount,
    linkedSummaries,
    isLoading: assignmentLoading,
  } = useEmployeeAssignment();
  const queryAssignmentId = useMemo(() => parseAssignmentSearchParam(location.search), [location.search]);
  const { effectiveId: assignmentId, needsPicker } = useMemo(
    () =>
      resolveScopedAssignmentId({
        linkedCount,
        linkedSummaries,
        primaryAssignmentId,
        queryAssignmentId,
      }),
    [linkedCount, linkedSummaries, primaryAssignmentId, queryAssignmentId]
  );
  const [caseId, setCaseId] = useState<string | null>(null);
  const [caseLoading, setCaseLoading] = useState(true);
  const [notes, setNotes] = useState<Record<string, string>>({});

  const shortlisted = useMemo(() => {
    if (!recommendations) return [];
    const items: Array<{ service: string; vendor: any }> = [];
    for (const [category, res] of Object.entries(recommendations)) {
      const selectedId = shortlist.get(category);
      if (!selectedId) continue;
      const vendor = res.recommendations.find((r) => r.item_id === selectedId);
      if (vendor) items.push({ service: category, vendor });
    }
    return items;
  }, [recommendations, shortlist]);

  useEffect(() => {
    let cancelled = false;
    if (!assignmentId || needsPicker) {
      setCaseLoading(false);
      return;
    }
    setCaseLoading(true);
    employeeAPI
      .getAssignmentServices(assignmentId)
      .then((res) => {
        if (!cancelled) setCaseId(res.case_id || null);
      })
      .catch(() => {
        if (!cancelled) setCaseId(null);
      })
      .finally(() => {
        if (!cancelled) setCaseLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [assignmentId, needsPicker]);

  if (assignmentLoading) {
    return (
      <AppShell title="RFQ builder" subtitle="Generate quotation requests for shortlisted vendors.">
        <Card padding="lg">
          <p className="text-sm text-[#6b7280]">Loading…</p>
        </Card>
      </AppShell>
    );
  }

  if (needsPicker && linkedSummaries.length > 0) {
    return (
      <AppShell title="RFQ builder" subtitle="Generate quotation requests for shortlisted vendors.">
        <EmployeeScopedAssignmentPicker
          title="Which assignment is this RFQ for?"
          subtitle="You have multiple linked relocations. Choose one to load case details for RFQs."
          linkedSummaries={linkedSummaries}
          targetBasePath={buildRoute('servicesRfqNew')}
        />
      </AppShell>
    );
  }

  if (!assignmentId) {
    return (
      <AppShell title="RFQ builder" subtitle="Generate quotation requests for shortlisted vendors.">
        <Card padding="lg">
          <p className="text-sm text-[#6b7280]">
            Sign in as an employee with an assignment to use the RFQ builder.
          </p>
        </Card>
      </AppShell>
    );
  }

  if (shortlisted.length === 0) {
    return (
      <AppShell title="RFQ builder" subtitle="Select vendors before sending RFQs.">
        <Card padding="lg">
          <p className="text-sm text-[#6b7280] mb-4">
            Go to recommendations, choose one vendor per service, then return here to create your RFQ.
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
    <AppShell title="RFQ builder" subtitle="Generate quotation requests for shortlisted vendors.">
      <Card padding="lg" className="space-y-4">
        {caseLoading && (
          <Alert variant="info" title="Loading your case">
            <p className="text-sm text-[#374151]">Hang on — we&apos;re loading your case details…</p>
          </Alert>
        )}
        {!caseLoading && !caseId && (
          <Alert variant="warning" title="Case information missing">
            Complete your case setup from the services page first, then try again.
            <Button
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={() => navigate(withAssignmentQuery(buildRoute('services'), assignmentId))}
            >
              Go to Services
            </Button>
          </Alert>
        )}
        <Card padding="lg" className="border border-[#bfdbfe] bg-[#f8fafc]">
          <h3 className="text-base font-semibold text-[#0b2b43] mb-2">Quotation requests — coming soon</h3>
          <p className="text-sm text-[#374151] mb-4">
            Sending RFQs to vendors isn&apos;t turned on yet. Your shortlist and budget review are saved; you don&apos;t
            need to do anything on this page right now.
          </p>
          <p className="text-sm font-semibold text-[#0b2b43] mb-2">What to do next</p>
          <ul className="text-sm text-[#374151] list-disc list-inside space-y-2 mb-5">
            <li>
              Open the <strong>Resources</strong> tab (top navigation) for country guides, checklists, and what to
              prepare while you wait on visas, housing, and schools.
            </li>
            <li>
              Review <strong>My Case</strong> for your intake summary and <strong>HR Policy</strong> for benefit caps.
            </li>
            <li>Return here later when RFQ sending is available — your shortlisted providers will still be listed below.</li>
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
        <p className="text-sm text-[#6b7280] mt-6">
          Your shortlisted vendors (for when RFQs go live):
        </p>
        {shortlisted.map(({ service, vendor }) => (
          <div key={`${service}-${vendor.item_id}`} className="border border-[#e2e8f0] rounded-lg p-4">
            <div className="font-semibold text-[#0b2b43]">{vendor.name}</div>
            <div className="text-sm text-[#6b7280] mb-2">
              Service: {SERVICE_LABELS[service] || service}
            </div>
            <Input
              label="Optional note (saved for later)"
              value={notes[vendor.item_id] || ''}
              onChange={(val) => setNotes((prev) => ({ ...prev, [vendor.item_id]: val }))}
              placeholder="e.g. Moving date, special requirements…"
              fullWidth
            />
          </div>
        ))}
        <div className="flex justify-end mt-4">
          <Button type="button" variant="outline" disabled title="RFQ sending is not available yet">
            Send RFQs (not available yet)
          </Button>
        </div>
      </Card>
    </AppShell>
  );
};
