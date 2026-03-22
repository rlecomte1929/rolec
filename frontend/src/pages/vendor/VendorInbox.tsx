import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Button, Card } from '../../components/antigravity';
import { vendorAPI } from '../../api/client';
import type { RfqSummary } from '../../api/client';

export const VendorInbox: React.FC = () => {
  const navigate = useNavigate();
  const [rfqs, setRfqs] = useState<RfqSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await vendorAPI.listRfqs();
      setRfqs(data.rfqs || []);
    } catch (err: unknown) {
      const status = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { status?: number } }).response?.status
        : 0;
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      if (status === 403) {
        setError('Vendor access only. Sign in with a vendor account to view RFQs.');
      } else {
        setError(String(msg || 'Failed to load RFQs'));
      }
      setRfqs([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <AppShell title="Vendor inbox" subtitle="Loading…">
        <Card padding="lg">
          <p className="text-sm text-[#6b7280]">Loading RFQs...</p>
        </Card>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell title="Vendor inbox" subtitle="RFQs for your account.">
        <Card padding="lg">
          <div className="rounded-lg bg-amber-50 p-4 text-sm text-amber-800">{error}</div>
        </Card>
      </AppShell>
    );
  }

  if (rfqs.length === 0) {
    return (
      <AppShell title="Vendor inbox" subtitle="RFQs for your account.">
        <Card padding="lg">
          <p className="text-sm text-[#6b7280]">No RFQs yet. New requests appear here when employees send them.</p>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell title="Vendor inbox" subtitle="RFQs for your account.">
      <Card padding="lg" className="space-y-4">
        {rfqs.map((rfq) => (
          <div
            key={rfq.id}
            className="flex items-center justify-between rounded-lg border border-[#e2e8f0] p-4 hover:bg-[#f8fafc]"
          >
            <div>
              <div className="font-medium text-[#0b2b43]">{rfq.rfq_ref}</div>
              <div className="text-sm text-[#6b7280]">
                {rfq.items?.length || 0} items · {rfq.status}
              </div>
            </div>
            <Button onClick={() => navigate(`/vendor/rfq/${rfq.id}`)}>
              Respond
            </Button>
          </div>
        ))}
      </Card>
    </AppShell>
  );
};
