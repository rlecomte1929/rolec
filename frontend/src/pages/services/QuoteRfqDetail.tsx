import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Button, Card } from '../../components/antigravity';
import { hrAPI, rfqAPI } from '../../api/client';
import type { RfqDetail, QuoteDetail } from '../../api/client';
import { HrRfqQuotesPolicyCapsSection } from '../../features/policy-config/HrRfqQuotesPolicyCapsSection';
import { getAuthItem, normalizeStoredRole } from '../../utils/demo';

export const QuoteRfqDetail: React.FC = () => {
  const navigate = useNavigate();
  const { rfqId } = useParams<{ rfqId: string }>();
  const [rfq, setRfq] = useState<RfqDetail | null>(null);
  const [quotes, setQuotes] = useState<QuoteDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acceptingId, setAcceptingId] = useState<string | null>(null);
  const [comparison, setComparison] = useState(false);
  const [policyAssignmentType, setPolicyAssignmentType] = useState<string | null>(null);
  const [policyFamilyStatus, setPolicyFamilyStatus] = useState<string | null>(null);

  const sessionRole = normalizeStoredRole(getAuthItem('relopass_role'));
  const showHrCapComparison = sessionRole === 'HR' || sessionRole === 'ADMIN';

  const load = useCallback(async (forComparison = false) => {
    if (!rfqId) return;
    setLoading(true);
    setError(null);
    try {
      const [rfqData, quotesData] = await Promise.all([
        rfqAPI.get(rfqId),
        rfqAPI.listQuotes(rfqId, { comparison: forComparison }),
      ]);
      setRfq(rfqData);
      setQuotes(quotesData.quotes || []);
      if (forComparison) setComparison(true);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      setError(String(msg || 'Failed to load RFQ'));
      setRfq(null);
      setQuotes([]);
    } finally {
      setLoading(false);
    }
  }, [rfqId]);

  useEffect(() => {
    load();
  }, [rfqId]);

  useEffect(() => {
    if (!showHrCapComparison || !rfq?.assignment_id) {
      setPolicyAssignmentType(null);
      setPolicyFamilyStatus(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const pol = await hrAPI.getResolvedPolicy(rfq.assignment_id!);
        if (cancelled) return;
        const rc = (pol.resolution_context || {}) as {
          assignment_type?: string;
          family_status?: string;
        };
        setPolicyAssignmentType(rc.assignment_type ?? null);
        setPolicyFamilyStatus(rc.family_status ?? null);
      } catch {
        if (!cancelled) {
          setPolicyAssignmentType(null);
          setPolicyFamilyStatus(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [showHrCapComparison, rfq?.assignment_id]);

  const handleAccept = async (quoteId: string) => {
    if (!rfqId) return;
    setAcceptingId(quoteId);
    try {
      await rfqAPI.acceptQuote(rfqId, quoteId);
      await load();
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      setError(String(msg || 'Failed to accept quote'));
    } finally {
      setAcceptingId(null);
    }
  };

  const openComparison = useCallback(async () => {
    if (!rfqId || quotes.length < 2) return;
    await load(true);
  }, [rfqId, quotes.length, load]);

  if (loading && !rfq) {
    return (
      <AppShell title="RFQ detail" subtitle="Loading...">
        <Card padding="lg"><p className="text-sm text-[#6b7280]">Loading...</p></Card>
      </AppShell>
    );
  }

  if (error && !rfq) {
    return (
      <AppShell title="RFQ detail" subtitle="Error">
        <Card padding="lg">
          <p className="text-sm text-red-600">{error}</p>
          <Button className="mt-3" onClick={() => navigate('/quotes')}>Back to inbox</Button>
        </Card>
      </AppShell>
    );
  }

  if (!rfq) return null;

  const hasAccepted = quotes.some((q) => q.status === 'accepted');

  return (
    <AppShell title={rfq.rfq_ref} subtitle="RFQ detail and quotes">
      <Card padding="lg" className="space-y-6">
        {error && (
          <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}
        <div className="flex items-center justify-between">
          <Button variant="secondary" onClick={() => navigate('/quotes')}>
            ← Back to inbox
          </Button>
        </div>

        <div>
          <h3 className="font-semibold text-[#0b2b43]">Items</h3>
          <ul className="mt-2 space-y-1 text-sm text-[#6b7280]">
            {rfq.items?.map((item, i) => (
              <li key={i}>
                {item.service_key}: {JSON.stringify(item.requirements || {}).slice(0, 80)}
              </li>
            ))}
          </ul>
        </div>

        {showHrCapComparison && quotes.length > 0 ? (
          <HrRfqQuotesPolicyCapsSection
            rfq={rfq}
            quotes={quotes}
            assignmentType={policyAssignmentType}
            familyStatus={policyFamilyStatus}
          />
        ) : null}

        <div>
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-[#0b2b43]">Quotes</h3>
            {quotes.length >= 2 && !comparison && (
              <Button variant="secondary" onClick={openComparison}>
                Compare quotes
              </Button>
            )}
          </div>

          {quotes.length === 0 ? (
            <p className="mt-2 text-sm text-[#6b7280]">No quotes yet. Vendors will appear here when they respond.</p>
          ) : comparison ? (
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              {quotes.map((q) => (
                <div
                  key={q.id}
                  className={`rounded-lg border p-4 ${
                    q.status === 'accepted' ? 'border-green-500 bg-green-50' : 'border-[#e2e8f0]'
                  }`}
                >
                  <div className="font-medium">Vendor {q.vendor_id.slice(0, 8)}…</div>
                  <div className="mt-1 text-lg font-semibold">
                    {q.currency} {q.total_amount.toLocaleString()}
                  </div>
                  {q.valid_until && (
                    <div className="text-xs text-[#6b7280]">Valid until: {q.valid_until}</div>
                  )}
                  {q.quote_lines?.length ? (
                    <ul className="mt-2 space-y-1 text-sm">
                      {q.quote_lines.map((l, i) => (
                        <li key={i}>
                          {l.label}: {q.currency} {l.amount.toLocaleString()}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  {q.status !== 'accepted' && !hasAccepted && (
                    <Button
                      className="mt-3"
                      disabled={!!acceptingId}
                      onClick={() => handleAccept(q.id)}
                    >
                      {acceptingId === q.id ? 'Accepting…' : 'Accept'}
                    </Button>
                  )}
                  {q.status === 'accepted' && (
                    <div className="mt-2 text-sm font-medium text-green-700">Accepted</div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <ul className="mt-4 space-y-3">
              {quotes.map((q) => (
                <li
                  key={q.id}
                  className={`flex items-center justify-between rounded-lg border p-4 ${
                    q.status === 'accepted' ? 'border-green-500 bg-green-50' : 'border-[#e2e8f0]'
                  }`}
                >
                  <div>
                    <div className="font-medium">Vendor {q.vendor_id.slice(0, 8)}…</div>
                    <div>
                      {q.currency} {q.total_amount.toLocaleString()}
                      {q.valid_until && ` · Valid until ${q.valid_until}`}
                    </div>
                  </div>
                  {q.status !== 'accepted' && !hasAccepted ? (
                    <Button
                      disabled={!!acceptingId}
                      onClick={() => handleAccept(q.id)}
                    >
                      {acceptingId === q.id ? 'Accepting…' : 'Accept'}
                    </Button>
                  ) : q.status === 'accepted' ? (
                    <span className="text-sm font-medium text-green-700">Accepted</span>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>
    </AppShell>
  );
};
