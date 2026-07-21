/**
 * AIQ-1602 Seg 4 — HR proposes a preferred supplier for the shared ReloPass
 * catalog. Unlike the company-scoped "your own preferred vendors" card, this
 * goes to an admin moderation queue; an admin approves it into the registry.
 * Self-contained so it doesn't thread state through the large HrVendorCuration.
 */
import React, { useEffect, useState } from 'react';
import { Alert, Badge, Button, Card, Input } from '../components/antigravity';
import {
  createSupplierSubmission,
  listMySupplierSubmissions,
  type SupplierSubmission,
} from '../api/hrCatalog';

const STATUS_TONE: Record<SupplierSubmission['status'], 'warning' | 'success' | 'neutral'> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'neutral',
};

export const HrPreferredSupplierCard: React.FC = () => {
  const [name, setName] = useState('');
  const [category, setCategory] = useState('');
  const [country, setCountry] = useState('');
  const [city, setCity] = useState('');
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [submissions, setSubmissions] = useState<SupplierSubmission[]>([]);

  const load = async () => {
    try {
      const res = await listMySupplierSubmissions();
      setSubmissions(res.submissions || []);
    } catch {
      // soft — the form still works even if the history can't load
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const submit = async () => {
    setError(null);
    setInfo(null);
    if (!name.trim() || !category.trim()) {
      setError('Supplier name and service category are required.');
      return;
    }
    setSubmitting(true);
    try {
      await createSupplierSubmission({
        name: name.trim(),
        service_category: category.trim(),
        // Scope follows the fields actually filled: a submission with no country is GLOBAL,
        // not country-scoped-without-a-country — the latter can be created but never approved
        // (admin approval requires a country_code for 'country'/'city' scope). AIQ-1659.
        coverage_scope_type: city.trim() ? 'city' : country.trim() ? 'country' : 'global',
        country_code: country.trim() || null,
        city_name: city.trim() || null,
        contact_email: email.trim() || null,
      });
      setInfo('Sent to the ReloPass team for review — you’ll see the status below.');
      setName('');
      setCategory('');
      setCountry('');
      setCity('');
      setEmail('');
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not submit — try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const inputCls =
    'rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43]';

  return (
    <Card padding="lg" className="mt-6">
      <h2 className="text-lg font-semibold text-[#0b2b43]">
        4. Register a preferred supplier for the ReloPass catalog
      </h2>
      <p className="mt-1 text-sm text-[#6b7280]">
        Propose a vendor for the shared ReloPass catalog. The ReloPass team reviews it before it
        becomes selectable. This is different from “your own preferred vendors” above, which stay
        private to your company.
      </p>

      {error && <Alert variant="error" className="mt-3">{error}</Alert>}
      {info && <Alert variant="success" className="mt-3">{info}</Alert>}

      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
        <label className="block text-sm font-medium text-[#0b2b43]">
          Supplier name
          <Input unstyled type="text" value={name} onChange={(v) => setName(v)}
            placeholder="e.g. ABC Movers Munich" className={`mt-1 w-full ${inputCls}`} />
        </label>
        <label className="block text-sm font-medium text-[#0b2b43]">
          Service category
          <Input unstyled type="text" value={category} onChange={(v) => setCategory(v)}
            placeholder="e.g. movers, banks, insurance" className={`mt-1 w-full ${inputCls}`} />
        </label>
        <label className="block text-sm font-medium text-[#0b2b43]">
          Country
          <Input unstyled type="text" value={country} onChange={(v) => setCountry(v)}
            placeholder="e.g. DE" className={`mt-1 w-full ${inputCls}`} />
        </label>
        <label className="block text-sm font-medium text-[#0b2b43]">
          City <span className="font-normal text-[#6b7280]">(optional)</span>
          <Input unstyled type="text" value={city} onChange={(v) => setCity(v)}
            placeholder="e.g. Munich" className={`mt-1 w-full ${inputCls}`} />
        </label>
        <label className="block text-sm font-medium text-[#0b2b43] md:col-span-2">
          Contact email <span className="font-normal text-[#6b7280]">(optional)</span>
          <Input unstyled type="text" value={email} onChange={(v) => setEmail(v)}
            placeholder="e.g. hello@abcmovers.de" className={`mt-1 w-full ${inputCls}`} />
        </label>
      </div>

      <div className="mt-3 flex justify-end">
        <Button onClick={() => void submit()} disabled={submitting || !name.trim() || !category.trim()}>
          {submitting ? 'Submitting…' : 'Submit for review'}
        </Button>
      </div>

      {submissions.length > 0 && (
        <div className="mt-5">
          <div className="text-sm font-medium text-[#0b2b43] mb-2">Your submissions</div>
          <ul className="divide-y divide-[#e2e8f0] border border-[#e2e8f0] rounded-lg overflow-hidden bg-white">
            {submissions.map((s) => (
              <li key={s.id} className="p-3 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-medium text-[#0b2b43]">{s.name}</div>
                  <div className="text-xs text-[#64748b] mt-0.5">
                    {s.service_category}
                    {s.city_name ? ` · ${s.city_name}` : ''}
                    {s.country_code ? `, ${s.country_code}` : ''}
                  </div>
                  {s.status === 'rejected' && s.review_notes && (
                    <p className="text-xs text-[#b91c1c] mt-1">Reason: {s.review_notes}</p>
                  )}
                </div>
                <Badge variant={STATUS_TONE[s.status]} size="sm">
                  {s.status}
                </Badge>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
};
