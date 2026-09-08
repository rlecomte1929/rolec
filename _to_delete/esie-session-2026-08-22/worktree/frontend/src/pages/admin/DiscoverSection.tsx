import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Badge, Button, Card } from '../../components/antigravity';
import { Input } from '../../components/antigravity/Input';
import {
  discoverSuppliers,
  getDiscoveryStatus,
  importDiscovered,
  type DiscoveryResult,
  type DiscoveryStatus,
} from '../../api/adminCatalog';

const CATEGORIES = [
  'movers', 'living_areas', 'schools', 'banks', 'insurance', 'legal_admin',
  'tax_finance', 'medical', 'telecom', 'childcare', 'language_integration',
  'storage', 'transport', 'electricity',
];

function errMessage(err: unknown, fallback: string): string {
  const msg =
    err && typeof err === 'object' && 'response' in err
      ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      : (err as Error)?.message;
  return String(msg || fallback);
}

/** GAP 5 — admin discovery: search a maps provider for real businesses, review,
 *  and import selected ones into the vetting queue as pending suppliers. */
export const DiscoverSection: React.FC = () => {
  const [status, setStatus] = useState<DiscoveryStatus | null>(null);
  const [category, setCategory] = useState('movers');
  const [city, setCity] = useState('');
  const [country, setCountry] = useState('');
  const [results, setResults] = useState<DiscoveryResult[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    getDiscoveryStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  const rowKey = (r: DiscoveryResult) => r.place_id || r.name;

  const search = useCallback(async () => {
    if (!city.trim() || !country.trim()) return;
    setLoading(true);
    setError(null);
    setInfo(null);
    setResults([]);
    setSelected({});
    try {
      const data = await discoverSuppliers(category, city.trim(), country.trim());
      setResults(data.results || []);
      if (!data.results?.length) setInfo('No results — try a different destination or provider.');
    } catch (err: unknown) {
      setError(errMessage(err, 'Discovery failed'));
    } finally {
      setLoading(false);
      // Refresh the remaining daily-search budget after each attempt.
      getDiscoveryStatus().then(setStatus).catch(() => {});
    }
  }, [category, city, country]);

  const importSelected = useCallback(async () => {
    const items = results.filter((r) => selected[rowKey(r)] && !r.already_in_catalog);
    if (!items.length) return;
    setImporting(true);
    setError(null);
    try {
      const res = await importDiscovered({
        category,
        city: city.trim(),
        country: country.trim(),
        items: items.map((r) => ({ name: r.name, website: r.website, place_id: r.place_id, formatted_address: r.formatted_address })),
      });
      setInfo(`Imported ${res.created} supplier(s) to the vetting queue as pending.`);
      await search();
    } catch (err: unknown) {
      setError(errMessage(err, 'Import failed'));
    } finally {
      setImporting(false);
    }
  }, [results, selected, category, city, country, search]);

  const isOff = !status?.configured || status?.provider === 'disabled';
  const noBudget = !!status?.configured && status.daily_remaining <= 0;

  return (
    <Card padding="lg" className="mb-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-[#0b2b43]">Discover suppliers</h2>
        <div className="flex items-center gap-2 text-xs text-[#6b7280]">
          {status && !isOff && (
            <span>{status.daily_remaining}/{status.daily_limit} searches left today · up to {status.max_results}/search</span>
          )}
          {isOff
            ? <Badge variant="neutral" size="sm">discovery off</Badge>
            : <Badge variant="success" size="sm">{status!.provider}</Badge>}
        </div>
      </div>
      {error && <div className="mb-3"><Alert variant="error">{error}</Alert></div>}
      {info && <div className="mb-3"><Alert variant="success">{info}</Alert></div>}

      <div className="flex flex-wrap items-end gap-3 mb-4">
        <label className="text-sm">
          <span className="block text-[#6b7280] mb-1">Category</span>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="px-3 py-2 border border-[#e2e8f0] rounded-lg text-sm"
          >
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <Input label="City" value={city} onChange={setCity} placeholder="Oslo" />
        <Input label="Country" value={country} onChange={setCountry} placeholder="Norway" />
        <Button variant="secondary" size="sm" onClick={search} disabled={loading || noBudget || !city.trim() || !country.trim()}>
          {loading ? 'Searching…' : noBudget ? 'Daily limit reached' : 'Search'}
        </Button>
      </div>

      {results.length > 0 && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[#6b7280] border-b border-[#e5e7eb]">
                  <th className="py-2 w-8"></th>
                  <th className="py-2">Name</th>
                  <th className="py-2">Rating</th>
                  <th className="py-2">Address</th>
                  <th className="py-2"></th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => {
                  const k = rowKey(r);
                  return (
                    <tr key={k} className="border-b border-[#f1f5f9]">
                      <td className="py-2">
                        <input
                          type="checkbox"
                          disabled={r.already_in_catalog}
                          checked={!!selected[k]}
                          onChange={(e) => setSelected((prev) => ({ ...prev, [k]: e.target.checked }))}
                        />
                      </td>
                      <td className="py-2 font-medium text-[#0b2b43]">
                        {r.website ? <a href={r.website} target="_blank" rel="noopener noreferrer" className="underline">{r.name}</a> : r.name}
                      </td>
                      <td className="py-2">{r.rating != null ? `${r.rating} (${r.user_ratings_total ?? 0})` : '—'}</td>
                      <td className="py-2 text-[#6b7280]">{r.formatted_address || '—'}</td>
                      <td className="py-2">{r.already_in_catalog && <Badge variant="neutral" size="sm">Already exists</Badge>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="mt-3 flex justify-end">
            <Button variant="secondary" size="sm" onClick={importSelected} disabled={importing}>
              {importing ? 'Importing…' : 'Import selected'}
            </Button>
          </div>
        </>
      )}
    </Card>
  );
};
