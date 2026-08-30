/**
 * AIQ-1521 — the supplier's side of an RFQ. PUBLIC: no account, no login, token in the URL.
 *
 * This page is the risk spike. The employee-led model assumes a moving company will answer a
 * request from a business they have never heard of. If they won't, the model is worth nothing.
 * So this is built to be as close to frictionless as we can make it: open the link, see what is
 * being asked for, type a price, send.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';

const API = import.meta.env.VITE_API_URL || 'https://api.relopass.com';

type BriefRow = { label: string; value: string };
type RfqItem = { service_key: string; brief: BriefRow[] };
type RfqView = {
  rfq_ref: string;
  items: RfqItem[];
  expectations: string[];
  respond_by: string;
  already_quoted: boolean;
};
type Line = { label: string; amount: string };

const SERVICE_LABELS: Record<string, string> = {
  movers: 'Moving / relocation of household goods',
  living_areas: 'Housing',
  schools: 'Schools',
  banks: 'Banking',
  insurance: 'Insurance',
};

export const SupplierQuotePage: React.FC = () => {
  const [params] = useSearchParams();
  const token = params.get('token') || '';

  const [rfq, setRfq] = useState<RfqView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [currency, setCurrency] = useState('EUR');
  const [total, setTotal] = useState('');
  const [validUntil, setValidUntil] = useState('');
  const [lines, setLines] = useState<Line[]>([{ label: '', amount: '' }]);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const auth = useCallback(() => ({ headers: { Authorization: `Bearer ${token}` } }), [token]);

  useEffect(() => {
    if (!token) {
      setError('This link is missing its token. Please use the link from the email.');
      setLoading(false);
      return;
    }
    axios
      .get<RfqView>(`${API}/api/supplier/rfq`, auth())
      .then((r) => {
        setRfq(r.data);
        setDone(r.data.already_quoted);
      })
      .catch((e) => {
        const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setError(detail || 'We could not open this request.');
      })
      .finally(() => setLoading(false));
  }, [token, auth]);

  const submit = async () => {
    const amount = Number(total);
    if (!Number.isFinite(amount) || amount <= 0) {
      setError('Please enter your total price.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await axios.post(
        `${API}/api/supplier/rfq/quote`,
        {
          currency,
          total_amount: amount,
          valid_until: validUntil || null,
          quote_lines: lines
            .filter((l) => l.label.trim() && Number(l.amount) > 0)
            .map((l) => ({ label: l.label.trim(), amount: Number(l.amount) })),
        },
        auth(),
      );
      setDone(true);
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'We could not send your quote. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <Shell><p className="text-slate-500">Opening the request…</p></Shell>;

  if (error && !rfq) {
    return (
      <Shell>
        <h1 className="text-xl font-semibold text-[#0b2b43]">We couldn’t open this request</h1>
        <p className="mt-2 text-slate-600">{error}</p>
      </Shell>
    );
  }

  if (done) {
    return (
      <Shell>
        <h1 className="text-xl font-semibold text-[#0b2b43]">Thank you — your quote is with them</h1>
        <p className="mt-2 text-slate-600">
          The company will be in touch directly if they’d like to go ahead. You don’t need to do
          anything else.
        </p>
      </Shell>
    );
  }

  return (
    <Shell>
      <h1 className="text-xl font-semibold text-[#0b2b43]">A company would like a quote from you</h1>
      <p className="mt-1 text-sm text-slate-500">Request {rfq?.rfq_ref}</p>

      {(rfq?.items ?? []).map((it) => (
        <div key={it.service_key} className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm font-semibold text-[#0b2b43]">
            {SERVICE_LABELS[it.service_key] || it.service_key}
          </p>
          {/* "Not specified" rows are shown on purpose, not hidden: a vendor needs to see what we
              did NOT tell them, so they can ask — rather than guess and price it wrong. */}
          <table className="mt-3 w-full text-sm">
            <tbody>
              {it.brief.map((row) => (
                <tr key={row.label} className="align-top">
                  <td className="w-40 py-1 pr-3 text-slate-500">{row.label}</td>
                  <td
                    className={`py-1 font-medium ${
                      row.value === 'Not specified' ? 'text-slate-500 italic' : 'text-[#0b2b43]'
                    }`}
                  >
                    {row.value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      {rfq?.expectations?.length ? (
        <div className="mt-4 rounded-xl border border-[#1f8e8b]/30 bg-[#1f8e8b]/5 p-4">
          <p className="text-sm font-semibold text-[#0b2b43]">
            What we need back{rfq.respond_by ? ` by ${rfq.respond_by}` : ''}
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
            {rfq.expectations.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="mt-6 space-y-4">
        <div className="flex gap-3">
          <label className="flex-1 text-sm">
            <span className="mb-1 block font-medium text-[#0b2b43]">Your total price</span>
            <input
              data-testid="supplier-total"
              type="number"
              value={total}
              onChange={(e) => setTotal(e.target.value)}
              placeholder="e.g. 4200"
              className="w-full rounded-lg border border-slate-200 px-3 py-2"
            />
          </label>
          <label className="w-28 text-sm">
            <span className="mb-1 block font-medium text-[#0b2b43]">Currency</span>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2"
            >
              {['EUR', 'GBP', 'USD', 'NOK', 'SGD', 'AED'].map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </label>
        </div>

        <label className="block text-sm">
          <span className="mb-1 block font-medium text-[#0b2b43]">Valid until (optional)</span>
          <input
            type="date"
            value={validUntil}
            onChange={(e) => setValidUntil(e.target.value)}
            className="rounded-lg border border-slate-200 px-3 py-2"
          />
        </label>

        <div>
          <p className="text-sm font-medium text-[#0b2b43]">
            What’s included <span className="font-normal text-slate-500">(optional, but it helps them compare fairly)</span>
          </p>
          {lines.map((l, i) => (
            <div key={i} className="mt-2 flex gap-2">
              <input
                value={l.label}
                onChange={(e) =>
                  setLines((p) => p.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))
                }
                placeholder="e.g. Packing and transport"
                className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
              <input
                type="number"
                value={l.amount}
                onChange={(e) =>
                  setLines((p) => p.map((x, j) => (j === i ? { ...x, amount: e.target.value } : x)))
                }
                placeholder="Amount"
                className="w-32 rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </div>
          ))}
          <button
            type="button"
            onClick={() => setLines((p) => [...p, { label: '', amount: '' }])}
            className="mt-2 text-sm font-medium text-[#1f8e8b]"
          >
            + Add another line
          </button>
        </div>

        {error ? <p className="text-sm text-red-600">{error}</p> : null}

        <button
          type="button"
          data-testid="supplier-submit"
          onClick={submit}
          disabled={submitting}
          className="w-full rounded-lg bg-[#1f8e8b] px-4 py-3 font-semibold text-white disabled:opacity-60"
        >
          {submitting ? 'Sending…' : 'Send my quote'}
        </button>
        <p className="text-center text-xs text-slate-500">
          No account needed. This link is unique to you.
        </p>
      </div>
    </Shell>
  );
};

const Shell: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="min-h-screen bg-white px-4 py-10">
    <div className="mx-auto max-w-lg">{children}</div>
  </div>
);

export default SupplierQuotePage;
