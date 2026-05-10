import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Button, Card, Input } from '../../components/antigravity';
import { vendorAPI } from '../../api/client';
import type { RfqDetail, QuoteCreatePayload } from '../../api/client';

export const VendorRfq: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [rfq, setRfq] = useState<RfqDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [totalAmount, setTotalAmount] = useState('');
  const [currency, setCurrency] = useState('EUR');
  const [validUntil, setValidUntil] = useState('');
  const [lines, setLines] = useState<Array<{ label: string; amount: string }>>([
    { label: 'Packing', amount: '' },
    { label: 'Transport', amount: '' },
    { label: 'Insurance', amount: '' },
  ]);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await vendorAPI.getRfq(id);
      setRfq(data);
    } catch (err: unknown) {
      const status = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { status?: number } }).response?.status
        : 0;
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      if (status === 403) {
        setError('Not authorized to view this RFQ.');
      } else {
        setError(String(msg || 'Failed to load RFQ'));
      }
      setRfq(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSubmit = async () => {
    if (!id || !rfq) return;
    const total = parseFloat(totalAmount);
    if (isNaN(total) || total <= 0) {
      setError('Enter a valid total amount.');
      return;
    }
    const quoteLines = lines
      .filter((l) => l.label.trim() && l.amount.trim())
      .map((l) => ({ label: l.label.trim(), amount: parseFloat(l.amount) || 0 }));
    if (quoteLines.length === 0) {
      quoteLines.push({ label: 'Total', amount: total });
    }
    const payload: QuoteCreatePayload = {
      total_amount: total,
      currency: currency || 'EUR',
      valid_until: validUntil.trim() || undefined,
      quote_lines: quoteLines,
    };
    setSubmitting(true);
    setError(null);
    try {
      await vendorAPI.submitQuote(id, payload);
      navigate('/vendor/inbox');
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      setError(String(msg || "Couldn't submit quote. Try again."));
    } finally {
      setSubmitting(false);
    }
  };

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
          <Button className="mt-3" onClick={() => navigate('/vendor/inbox')}>Back to inbox</Button>
        </Card>
      </AppShell>
    );
  }

  if (!rfq) return null;

  return (
    <AppShell title={rfq.rfq_ref} subtitle="Submit quote">
      <Card padding="lg" className="space-y-6">
        {error && (
          <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}
        <Button variant="secondary" onClick={() => navigate('/vendor/inbox')}>
          ← Back to inbox
        </Button>

        <div>
          <h3 className="font-semibold text-[#0b2b43]">Requested items</h3>
          <ul className="mt-2 space-y-1 text-sm text-[#6b7280]">
            {rfq.items?.map((item, i) => (
              <li key={i}>
                {item.service_key}: {JSON.stringify(item.requirements || {}).slice(0, 100)}
              </li>
            ))}
          </ul>
        </div>

        <div className="space-y-4 border-t border-[#e2e8f0] pt-4">
          <h3 className="font-semibold text-[#0b2b43]">Your quote</h3>
          <Input
            label="Total amount"
            type="number"
            value={totalAmount}
            onChange={(v) => setTotalAmount(v)}
            placeholder="e.g. 2500"
          />
          <Input
            label="Currency"
            value={currency}
            onChange={(v) => setCurrency(v)}
            placeholder="EUR"
          />
          <Input
            label="Valid until (YYYY-MM-DD)"
            value={validUntil}
            onChange={(v) => setValidUntil(v)}
            placeholder="2025-06-30"
          />
          <div>
            <div className="mb-2 text-sm font-medium">Line items (optional)</div>
            {lines.map((line, i) => (
              <div key={i} className="mb-2 flex gap-2">
                <Input
                  value={line.label}
                  onChange={(v) =>
                    setLines((prev) => {
                      const next = [...prev];
                      next[i] = { ...next[i], label: v };
                      return next;
                    })
                  }
                  placeholder="Label"
                />
                <Input
                  type="number"
                  value={line.amount}
                  onChange={(v) =>
                    setLines((prev) => {
                      const next = [...prev];
                      next[i] = { ...next[i], amount: v };
                      return next;
                    })
                  }
                  placeholder="Amount"
                />
              </div>
            ))}
          </div>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Submitting…' : 'Submit quote'}
          </Button>
        </div>
      </Card>
    </AppShell>
  );
};
