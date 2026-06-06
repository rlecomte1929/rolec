/**
 * PendingRfqsPanel — AIQ-40-D
 *
 * Shows all RFQs sent for a case, grouped by status:
 *   sent          → "Awaiting Reply"  — HR can mark quote received
 *   quote_received → shows amount/deadline — HR can accept
 *   accepted       → green check, amount + deadline locked
 *   cancelled      → grey strike-through
 *
 * "Mark Quote Received" opens an inline form to enter quote details.
 * "Accept Quote" calls PATCH /api/hr/rfq-requests/{id} with status=accepted.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Input } from '../antigravity/Input';
import { Button } from '../antigravity/Button';
import { hrAPI } from '../../api/client';

type Rfq = {
  id: string;
  vendor_name: string;
  service_category: string;
  status: string;
  created_at: string;
  move_date: string | null;
  budget_range: string | null;
  quote_amount?: number | null;
  quote_currency?: string | null;
  quote_deadline?: string | null;
  quote_deliverable?: string | null;
};

interface Props {
  caseId: string;
}

const STATUS_LABEL: Record<string, { label: string; color: string }> = {
  sent:           { label: 'Awaiting reply', color: 'text-[#d97706] bg-[#fef3c7]' },
  quote_received: { label: 'Quote received', color: 'text-[#2563eb] bg-[#eff6ff]' },
  accepted:       { label: 'Accepted',       color: 'text-[#16a34a] bg-[#f0fdf4]' },
  cancelled:      { label: 'Cancelled',      color: 'text-[#94a3b8] bg-[#f1f5f9]' },
};

export const PendingRfqsPanel: React.FC<Props> = ({ caseId }) => {
  const [rfqs, setRfqs] = useState<Rfq[]>([]);
  const [loading, setLoading] = useState(true);

  // Which RFQ is showing the "Mark received" inline form
  const [receivingId, setReceivingId] = useState<string | null>(null);
  const [quoteForm, setQuoteForm] = useState({
    quote_amount: '',
    quote_currency: 'EUR',
    quote_deadline: '',
    quote_deliverable: '',
  });

  const [actingId, setActingId] = useState<string | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    hrAPI
      .getRfqRequests({ case_id: caseId })
      .then((res) => setRfqs(res.rfqs))
      .catch(() => setRfqs([]))
      .finally(() => setLoading(false));
  }, [caseId]);

  useEffect(() => { load(); }, [load]);

  const handleMarkReceived = async (rfq: Rfq) => {
    if (!quoteForm.quote_amount) {
      setError('Please enter the quoted amount.');
      return;
    }
    setError('');
    setActingId(rfq.id);
    try {
      await hrAPI.updateRfqStatus(rfq.id, 'quote_received', {
        quote_amount: parseFloat(quoteForm.quote_amount),
        quote_currency: quoteForm.quote_currency || 'EUR',
        quote_deadline: quoteForm.quote_deadline || undefined,
        quote_deliverable: quoteForm.quote_deliverable || undefined,
      });
      setReceivingId(null);
      setQuoteForm({ quote_amount: '', quote_currency: 'EUR', quote_deadline: '', quote_deliverable: '' });
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to update.');
    } finally {
      setActingId(null);
    }
  };

  const handleAccept = async (rfq: Rfq) => {
    setActingId(rfq.id);
    setError('');
    try {
      await hrAPI.updateRfqStatus(rfq.id, 'accepted');
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to accept quote.');
    } finally {
      setActingId(null);
    }
  };

  const handleCancel = async (rfq: Rfq) => {
    setActingId(rfq.id);
    setError('');
    try {
      await hrAPI.updateRfqStatus(rfq.id, 'cancelled');
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to cancel.');
    } finally {
      setActingId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-[#94a3b8] py-4">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#0b2b43] border-t-transparent" />
        Loading quote requests…
      </div>
    );
  }

  if (rfqs.length === 0) {
    return (
      <p className="text-sm text-[#94a3b8]">
        No quote requests sent yet. Use "Find a vendor" to request quotes from vendors.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {error && (
        <div className="rounded-lg border border-[#fecaca] bg-[#fef2f2] px-4 py-3 text-sm text-[#dc2626]" role="alert">
          {error}
        </div>
      )}

      {rfqs.map((rfq) => {
        const statusMeta = STATUS_LABEL[rfq.status] ?? { label: rfq.status, color: 'text-[#6b7280] bg-[#f3f4f6]' };
        const isReceiving = receivingId === rfq.id;
        const isActing = actingId === rfq.id;

        return (
          <div
            key={rfq.id}
            className={`rounded-xl border p-4 transition-colors ${
              rfq.status === 'accepted'
                ? 'border-[#bbf7d0] bg-[#f0fdf4]'
                : rfq.status === 'cancelled'
                ? 'border-[#e2e8f0] bg-[#f8fafc] opacity-60'
                : 'border-[#e2e8f0] bg-white'
            }`}
          >
            {/* Top row */}
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-[#0b2b43] truncate">
                    {rfq.vendor_name}
                  </span>
                  <span className="text-xs text-[#64748b]">·</span>
                  <span className="text-xs text-[#64748b]">{rfq.service_category}</span>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusMeta.color}`}>
                    {statusMeta.label}
                  </span>
                </div>
                <p className="text-xs text-[#94a3b8] mt-1">
                  Sent {new Date(rfq.created_at).toLocaleDateString()}
                </p>

                {/* Quote details (when received/accepted) */}
                {(rfq.status === 'quote_received' || rfq.status === 'accepted') && rfq.quote_amount && (
                  <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                    <div>
                      <span className="text-[#94a3b8]">Amount: </span>
                      <span className="font-medium text-[#374151]">
                        {rfq.quote_currency ?? 'EUR'} {Number(rfq.quote_amount).toLocaleString()}
                      </span>
                    </div>
                    {rfq.quote_deadline && (
                      <div>
                        <span className="text-[#94a3b8]">Deadline: </span>
                        <span className="font-medium text-[#374151]">{rfq.quote_deadline}</span>
                      </div>
                    )}
                    {rfq.quote_deliverable && (
                      <div className="col-span-2">
                        <span className="text-[#94a3b8]">Deliverable: </span>
                        <span className="text-[#374151]">{rfq.quote_deliverable}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Action buttons */}
              <div className="flex flex-col gap-1.5 shrink-0">
                {rfq.status === 'sent' && !isReceiving && (
                  <>
                    <Button unstyled
                      type="button"
                      disabled={isActing}
                      onClick={() => {
                        setReceivingId(rfq.id);
                        setError('');
                      }}
                      className="rounded-lg border border-[#2563eb] bg-white px-3 py-1.5 text-xs font-medium text-[#2563eb] hover:bg-[#eff6ff] disabled:opacity-50 transition-colors whitespace-nowrap"
                    >
                      Mark quote received
                    </Button>
                    <Button unstyled
                      type="button"
                      disabled={isActing}
                      onClick={() => handleCancel(rfq)}
                      className="rounded-lg border border-[#e2e8f0] bg-white px-3 py-1.5 text-xs text-[#94a3b8] hover:bg-[#f8fafc] disabled:opacity-50 transition-colors"
                    >
                      Cancel
                    </Button>
                  </>
                )}
                {rfq.status === 'quote_received' && (
                  <>
                    <Button unstyled
                      type="button"
                      disabled={isActing}
                      onClick={() => handleAccept(rfq)}
                      className="rounded-lg bg-[#16a34a] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#15803d] disabled:opacity-50 transition-colors whitespace-nowrap"
                    >
                      {isActing ? 'Accepting…' : 'Accept quote'}
                    </Button>
                    <Button unstyled
                      type="button"
                      disabled={isActing}
                      onClick={() => handleCancel(rfq)}
                      className="rounded-lg border border-[#e2e8f0] bg-white px-3 py-1.5 text-xs text-[#94a3b8] hover:bg-[#f8fafc] disabled:opacity-50 transition-colors"
                    >
                      Cancel
                    </Button>
                  </>
                )}
                {rfq.status === 'accepted' && (
                  <span className="text-lg" title="Accepted">✓</span>
                )}
              </div>
            </div>

            {/* Inline "Mark Quote Received" form */}
            {isReceiving && (
              <div className="mt-4 pt-4 border-t border-[#e2e8f0] space-y-3">
                <p className="text-xs font-semibold text-[#374151]">Enter quote details</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-[#64748b] mb-1">
                      Amount <span className="text-[#ef4444]">*</span>
                    </label>
                    <Input unstyled
                      type="number"
                      min="0"
                      step="0.01"
                      value={quoteForm.quote_amount}
                      onChange={(v) => setQuoteForm((f) => ({ ...f, quote_amount: v }))}
                      placeholder="e.g. 2500"
                      className="w-full rounded-lg border border-[#d1d5db] px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-[#64748b] mb-1">Currency</label>
                    <select
                      value={quoteForm.quote_currency}
                      onChange={(e) => setQuoteForm((f) => ({ ...f, quote_currency: e.target.value }))}
                      className="w-full rounded-lg border border-[#d1d5db] px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
                    >
                      {['EUR', 'USD', 'GBP', 'CHF'].map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-[#64748b] mb-1">Deadline</label>
                    <Input unstyled
                      type="date"
                      value={quoteForm.quote_deadline}
                      onChange={(v) => setQuoteForm((f) => ({ ...f, quote_deadline: v }))}
                      className="w-full rounded-lg border border-[#d1d5db] px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-[#64748b] mb-1">Deliverable</label>
                    <Input unstyled
                      type="text"
                      value={quoteForm.quote_deliverable}
                      onChange={(v) => setQuoteForm((f) => ({ ...f, quote_deliverable: v }))}
                      placeholder="e.g. 3 housing options"
                      maxLength={100}
                      className="w-full rounded-lg border border-[#d1d5db] px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
                    />
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button unstyled
                    type="button"
                    disabled={isActing}
                    onClick={() => handleMarkReceived(rfq)}
                    className="rounded-lg bg-[#0b2b43] px-4 py-1.5 text-xs font-medium text-white hover:bg-[#1e4d6b] disabled:opacity-50 transition-colors"
                  >
                    {isActing ? 'Saving…' : 'Save quote details'}
                  </Button>
                  <Button unstyled
                    type="button"
                    onClick={() => { setReceivingId(null); setError(''); }}
                    className="rounded-lg border border-[#e2e8f0] px-4 py-1.5 text-xs text-[#6b7280] hover:bg-[#f8fafc] transition-colors"
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default PendingRfqsPanel;
