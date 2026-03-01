import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Button, Card, Input } from '../../components/antigravity';
import { employeeAPI, servicesAPI } from '../../api/client';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { useServicesFlow } from '../../features/services/ServicesFlowContext';

export const ServicesRfqNew: React.FC = () => {
  const navigate = useNavigate();
  const { recommendations, shortlist } = useServicesFlow();
  const { assignmentId } = useEmployeeAssignment();
  const [caseId, setCaseId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState('');
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
    if (!assignmentId) return;
    employeeAPI
      .getAssignmentServices(assignmentId)
      .then((res) => {
        if (!cancelled) setCaseId(res.case_id || null);
      })
      .catch(() => {
        if (!cancelled) setCaseId(null);
      });
    return () => {
      cancelled = true;
    };
  }, [assignmentId]);

  if (shortlisted.length === 0) {
    return (
      <AppShell title="RFQ builder" subtitle="Select vendors before sending RFQs.">
        <Card padding="lg">
          <Button onClick={() => navigate('/services/recommendations')}>Back to recommendations</Button>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell title="RFQ builder" subtitle="Generate quotation requests for shortlisted vendors.">
      <Card padding="lg" className="space-y-4">
        {error && <div className="text-sm text-red-600">{error}</div>}
        {shortlisted.map(({ service, vendor }) => (
          <div key={`${service}-${vendor.item_id}`} className="border border-[#e2e8f0] rounded-lg p-4">
            <div className="font-semibold text-[#0b2b43]">{vendor.name}</div>
            <div className="text-sm text-[#6b7280] mb-2">Service: {service}</div>
            <Input
              label="Optional note"
              value={notes[vendor.item_id] || ''}
              onChange={(val) => setNotes((prev) => ({ ...prev, [vendor.item_id]: val }))}
              placeholder="Add any specific requirements..."
              fullWidth
            />
          </div>
        ))}
        <div className="flex justify-end">
          <Button
            onClick={async () => {
              if (!caseId) {
                setError('Missing case information. Please retry from the services page.');
                return;
              }
              setIsSending(true);
              setError('');
              try {
                const items = shortlisted.map(({ service, vendor }) => ({
                  service_key: service,
                  requirements: { note: notes[vendor.item_id] || '' },
                }));
                const vendorIds = shortlisted.map(({ vendor }) => vendor.item_id);
                await servicesAPI.createRfq(caseId, items, vendorIds);
                navigate('/quotes');
              } catch (err: any) {
                setError(err?.response?.data?.detail || err?.message || 'Unable to send RFQ');
              } finally {
                setIsSending(false);
              }
            }}
            disabled={isSending}
          >
            Send RFQ
          </Button>
        </div>
      </Card>
    </AppShell>
  );
};
