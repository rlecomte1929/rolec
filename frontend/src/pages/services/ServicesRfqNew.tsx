import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert, Button, Card, Input } from '../../components/antigravity';
import { employeeAPI, servicesAPI } from '../../api/client';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { useServicesFlow } from '../../features/services/ServicesFlowContext';
import { getAuthItem } from '../../utils/demo';
import { ROUTE_DEFS } from '../../navigation/routes';

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
  const { recommendations, shortlist } = useServicesFlow();
  const { assignmentId } = useEmployeeAssignment();
  const [caseId, setCaseId] = useState<string | null>(null);
  const [caseLoading, setCaseLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState('');
  const [notes, setNotes] = useState<Record<string, string>>({});
  const isAdmin = (getAuthItem('relopass_role') || '').toUpperCase() === 'ADMIN';

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
    if (!assignmentId) {
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
  }, [assignmentId]);

  const hasUnregisteredSupplierError = error && /not a registered supplier/i.test(error);

  if (shortlisted.length === 0) {
    return (
      <AppShell title="RFQ builder" subtitle="Select vendors before sending RFQs.">
        <Card padding="lg">
          <p className="text-sm text-[#6b7280] mb-4">
            Go to recommendations, choose one vendor per service, then return here to create your RFQ.
          </p>
          <Button onClick={() => navigate('/services/recommendations')}>Back to recommendations</Button>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell title="RFQ builder" subtitle="Generate quotation requests for shortlisted vendors.">
      <Card padding="lg" className="space-y-4">
        {caseLoading && (
          <Alert variant="info" title="Loading…">
            Loading case information…
          </Alert>
        )}
        {!caseLoading && !caseId && (
          <Alert variant="warning" title="Case information missing">
            Complete your case setup from the services page first, then try again.
            <Button variant="outline" size="sm" className="mt-2" onClick={() => navigate('/services')}>
              Go to Services
            </Button>
          </Alert>
        )}
        {hasUnregisteredSupplierError && (
          <Alert variant="info" title="Vendors need to be registered">
            <p className="mb-2">
              These vendors come from our recommendation database. To send RFQs, they must be registered in the Supplier Registry.
            </p>
            {isAdmin ? (
              <Link
                to={ROUTE_DEFS.adminSuppliers.path}
                className="text-sm font-medium text-[#0b2b43] underline hover:no-underline"
              >
                Register suppliers in Admin →
              </Link>
            ) : (
              <p className="text-sm text-[#4b5563]">
                Ask your administrator to add them in Admin → Suppliers.
              </p>
            )}
          </Alert>
        )}
        {error && !hasUnregisteredSupplierError && (
          <Alert variant="error">{error}</Alert>
        )}

        <p className="text-sm text-[#6b7280]">
          Add optional notes for each vendor. Click Send RFQ when ready.
        </p>
        {shortlisted.map(({ service, vendor }) => (
          <div key={`${service}-${vendor.item_id}`} className="border border-[#e2e8f0] rounded-lg p-4">
            <div className="font-semibold text-[#0b2b43]">{vendor.name}</div>
            <div className="text-sm text-[#6b7280] mb-2">
              Service: {SERVICE_LABELS[service] || service}
            </div>
            <Input
              label="Optional note"
              value={notes[vendor.item_id] || ''}
              onChange={(val) => setNotes((prev) => ({ ...prev, [vendor.item_id]: val }))}
              placeholder="e.g. Moving date, special requirements…"
              fullWidth
            />
          </div>
        ))}
        <div className="flex justify-end">
          <Button
            onClick={async () => {
              if (!caseId) {
                setError('Missing case information. Please complete your case setup and retry.');
                return;
              }
              setIsSending(true);
              setError('');
              try {
                const items = shortlisted.map(({ service, vendor }) => ({
                  service_key: service,
                  requirements: { note: notes[vendor.item_id] || '' },
                }));
                const supplierIds = shortlisted.map(({ vendor }) => vendor.item_id);
                await servicesAPI.createRfq(caseId, items, supplierIds);
                navigate('/quotes');
              } catch (err: any) {
                const detail = err?.response?.data?.detail;
                const msg = typeof detail === 'string' ? detail : err?.message || 'Unable to send RFQ';
                setError(msg);
              } finally {
                setIsSending(false);
              }
            }}
            disabled={isSending || !caseId}
          >
            {isSending ? 'Sending…' : 'Send RFQ'}
          </Button>
        </div>
      </Card>
    </AppShell>
  );
};
