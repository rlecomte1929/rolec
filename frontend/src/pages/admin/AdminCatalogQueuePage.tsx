/**
 * Admin queue for HR-opened destination requests + allowlist management.
 * Phase 2b-secured UI (admin side).
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Input } from '../../components/antigravity/Input';
import { AdminLayout } from './AdminLayout';
import { Alert, Button, Card } from '../../components/antigravity';
import {
  addAllowlistEntry,
  fillDemandGap,
  listAdminDestinationRequests,
  listAllowlist,
  listDemandGaps,
  listIntakeCorridors,
  resolveDestinationRequest,
  type AllowlistEntry,
  type DemandGap,
  type IntakeCorridor,
} from '../../api/adminCatalog';
import type { DestinationRequest } from '../../api/hrCatalog';

const STATUS_TABS: { value: 'pending' | 'approved' | 'rejected'; label: string }[] = [
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
];

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export const AdminCatalogQueuePage: React.FC = () => {
  const [tab, setTab] = useState<'pending' | 'approved' | 'rejected'>('pending');
  const [tickets, setTickets] = useState<DestinationRequest[]>([]);
  const [allowlist, setAllowlistState] = useState<AllowlistEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [resolvingId, setResolvingId] = useState<string | null>(null);

  // CATALOG-1: demand-driven coverage worklist
  const [gaps, setGaps] = useState<DemandGap[]>([]);
  const [fillingKey, setFillingKey] = useState<string | null>(null);
  // CATALOG-4: proactive intake-driven corridors
  const [corridors, setCorridors] = useState<IntakeCorridor[]>([]);

  // Manual allowlist add form
  const [newCity, setNewCity] = useState('');
  const [newCountry, setNewCountry] = useState('');
  const [newNotes, setNewNotes] = useState('');
  const [adding, setAdding] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [t, a, g, c] = await Promise.all([
        listAdminDestinationRequests(tab),
        listAllowlist(),
        listDemandGaps(),
        listIntakeCorridors(),
      ]);
      setTickets(t);
      setAllowlistState(a);
      setGaps(g);
      setCorridors(c);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const resolve = async (id: string, status: 'approved' | 'rejected') => {
    setResolvingId(id);
    setError(null);
    setInfo(null);
    try {
      const updated = await resolveDestinationRequest(id, status);
      setInfo(
        status === 'approved'
          ? `Approved ${updated.city}, ${updated.country}. It's now on the allowlist for all companies.`
          : `Rejected ${updated.city}, ${updated.country}.`,
      );
      await loadAll();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not resolve ticket.';
      setError(msg);
    } finally {
      setResolvingId(null);
    }
  };

  const addEntry = async () => {
    if (!newCity.trim() || !newCountry.trim()) {
      setError('City and country are required.');
      return;
    }
    setAdding(true);
    setError(null);
    setInfo(null);
    try {
      const entry = await addAllowlistEntry(newCity.trim(), newCountry.trim(), newNotes.trim() || undefined);
      setInfo(`Added ${entry.city}, ${entry.country} to the allowlist.`);
      setNewCity('');
      setNewCountry('');
      setNewNotes('');
      await loadAll();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not add to allowlist.';
      setError(msg);
    } finally {
      setAdding(false);
    }
  };

  const fillGap = async (g: DemandGap) => {
    const key = `${g.category}|${g.city}|${g.country}`;
    setFillingKey(key);
    setError(null);
    setInfo(null);
    try {
      const res = await fillDemandGap(g.category, g.city, g.country);
      setInfo(
        res.scraped_count > 0
          ? `Added ${res.scraped_count} ${g.category} provider${res.scraped_count === 1 ? '' : 's'} for ${g.city}.`
          : `${g.city} is now allowlisted. The scraper returned nothing yet (it may be disabled or have no API key) — re-run once it's configured.`,
      );
      await loadAll();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not fill this gap.';
      setError(msg);
    } finally {
      setFillingKey(null);
    }
  };

  // CATALOG-4: pre-warm one uncovered category for an emerging corridor — reuses
  // the same allowlist+scrape action as the reactive demand worklist.
  const fillCorridorCategory = async (corridor: IntakeCorridor, category: string) => {
    const key = `${category}|${corridor.city}|${corridor.country}`;
    setFillingKey(key);
    setError(null);
    setInfo(null);
    try {
      const res = await fillDemandGap(category, corridor.city, corridor.country);
      setInfo(
        res.scraped_count > 0
          ? `Added ${res.scraped_count} ${category} provider${res.scraped_count === 1 ? '' : 's'} for ${corridor.city}.`
          : `${corridor.city} is now allowlisted. The scraper returned nothing yet (it may be disabled or have no API key) — re-run once it's configured.`,
      );
      await loadAll();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not pre-warm this corridor.';
      setError(msg);
    } finally {
      setFillingKey(null);
    }
  };

  const allowlistByDest = useMemo(() => {
    const set = new Set<string>();
    for (const e of allowlist) set.add(`${e.city.toLowerCase()}|${e.country.toLowerCase()}`);
    return set;
  }, [allowlist]);

  return (
    <AdminLayout
      title="Catalog destination queue"
      subtitle="HR-opened scrape requests + admin-managed allowlist."
    >
      {error && <Alert variant="error" className="mb-4">{error}</Alert>}
      {info && <Alert variant="success" className="mb-4">{info}</Alert>}

      {/* CATALOG-1: demand-driven worklist — what employees are asking for that
          the catalog can't cover yet. One click allowlists + scrapes it. */}
      <Card padding="lg" className="mb-6">
        <div className="mb-1 text-lg font-semibold text-[#0b2b43]">Coverage gaps employees are hitting</div>
        <p className="text-sm text-[#64748b] mb-4">
          Highest-demand service + destination combos with no catalog coverage yet, across all companies.
          Filling one allowlists the destination and runs the scraper — no manual search.
        </p>
        {gaps.length === 0 ? (
          <p className="text-sm text-[#94a3b8] py-2">
            {loading ? 'Loading…' : 'No uncovered demand right now. New gaps appear here as employees hit them.'}
          </p>
        ) : (
          <ul className="divide-y divide-[#e2e8f0] border border-[#e2e8f0] rounded-lg overflow-hidden bg-white">
            {gaps.map((g) => {
              const key = `${g.category}|${g.city}|${g.country}`;
              return (
                <li key={key} className="p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-medium text-[#0b2b43]">
                      <span className="capitalize">{g.category}</span> · {g.city}
                      {g.country ? `, ${g.country}` : ''}
                    </div>
                    <div className="text-sm text-[#64748b]">
                      {g.demand} request{g.demand === 1 ? '' : 's'} from {g.companies} compan{g.companies === 1 ? 'y' : 'ies'}
                      {' · last '}{formatDate(g.last_seen_at)}
                      {g.allowlisted ? ' · already allowlisted' : ''}
                    </div>
                  </div>
                  <Button
                    onClick={() => void fillGap(g)}
                    disabled={fillingKey === key}
                  >
                    {fillingKey === key ? 'Filling…' : 'Allowlist & scrape'}
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      {/* CATALOG-4: proactive intake-driven worklist — corridors employees are
          moving to (from intake) that the catalog can't fully cover yet. Pre-warm
          before anyone hits an empty state. Same allowlist+scrape action. */}
      <Card padding="lg" className="mb-6">
        <div className="mb-1 text-lg font-semibold text-[#0b2b43]">Emerging corridors (from intake)</div>
        <p className="text-sm text-[#64748b] mb-4">
          Destinations employees are moving to, ranked by intake volume, with the service categories
          still missing catalog coverage. Pre-warm them here before employees hit an empty state.
        </p>
        {corridors.length === 0 ? (
          <p className="text-sm text-[#94a3b8] py-2">
            {loading ? 'Loading…' : 'Every intake destination is covered. New corridors appear here as intake grows.'}
          </p>
        ) : (
          <ul className="divide-y divide-[#e2e8f0] border border-[#e2e8f0] rounded-lg overflow-hidden bg-white">
            {corridors.map((c) => (
              <li key={`${c.city}|${c.country}`} className="p-4 flex flex-col gap-2">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div className="font-medium text-[#0b2b43]">
                    {c.top_origin ? `${c.top_origin} → ` : ''}{c.city}{c.country ? `, ${c.country}` : ''}
                  </div>
                  <div className="text-sm text-[#64748b]">
                    {c.intake_count} intake{c.intake_count === 1 ? '' : 's'}
                    {' · last '}{formatDate(c.last_intake_at)}
                    {c.allowlisted ? ' · already allowlisted' : ''}
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-[#94a3b8]">Uncovered:</span>
                  {c.uncovered_categories.map((cat) => {
                    const key = `${cat}|${c.city}|${c.country}`;
                    return (
                      <Button
                        key={cat}
                        variant="outline"
                        onClick={() => void fillCorridorCategory(c, cat)}
                        disabled={fillingKey === key}
                      >
                        {fillingKey === key ? 'Filling…' : <span className="capitalize">{cat}</span>}
                      </Button>
                    );
                  })}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card padding="lg" className="mb-6">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="text-lg font-semibold text-[#0b2b43]">HR scrape requests</h2>
            <p className="text-sm text-[#6b7280] mt-1">
              Tickets opened by HR when they ask the AI to populate a destination that isn't yet
              on our supported list. Approving auto-adds (city, country) to the allowlist for
              every company.
            </p>
          </div>
          <div className="flex flex-wrap gap-1">
            {STATUS_TABS.map((s) => (
              <Button unstyled
                key={s.value}
                onClick={() => setTab(s.value)}
                className={`px-3 py-1 rounded-full border text-sm ${
                  tab === s.value
                    ? 'border-[#0b2b43] bg-[#0b2b43] text-white'
                    : 'border-[#cbd5e1] text-[#475569] hover:bg-[#f1f5f9]'
                }`}
              >
                {s.label}
              </Button>
            ))}
          </div>
        </div>
        {loading && tickets.length === 0 ? (
          <div className="space-y-2 py-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-14 rounded-lg bg-[#f1f5f9] animate-pulse" />
            ))}
          </div>
        ) : tickets.length === 0 ? (
          <div className="rounded-lg border border-dashed border-[#cbd5e1] py-6 text-center text-sm text-[#6b7280]">
            No {tab} requests.
          </div>
        ) : (
          <ul className="divide-y divide-[#e2e8f0] border border-[#e2e8f0] rounded-lg overflow-hidden bg-white">
            {tickets.map((t) => {
              const onAllowlist = allowlistByDest.has(`${t.city.toLowerCase()}|${t.country.toLowerCase()}`);
              const saving = resolvingId === t.id;
              return (
                <li key={t.id} className="p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-medium text-[#0b2b43]">
                        {t.city}, {t.country}
                        <span className="ml-2 text-xs font-normal text-[#94a3b8]">
                          category: {t.category}
                        </span>
                        {onAllowlist && (
                          <span className="ml-2 inline-flex items-center rounded-full border border-[#bbf7d0] bg-[#dcfce7] px-2 py-0.5 text-xs font-medium text-[#166534]">
                            on allowlist
                          </span>
                        )}
                      </div>
                      <div className="mt-1 text-xs text-[#6b7280]">
                        Opened {formatDate(t.created_at)} · by {t.requested_by.slice(0, 8)} ·
                        company {t.company_id.slice(0, 8)}
                      </div>
                      {t.notes && (
                        <p className="mt-2 text-sm text-[#334155] whitespace-pre-line">{t.notes}</p>
                      )}
                      {t.status !== 'pending' && (
                        <p className="mt-2 text-xs text-[#94a3b8]">
                          {t.status === 'approved' ? 'Approved' : 'Rejected'}{' '}
                          {t.resolved_at ? `· ${formatDate(t.resolved_at)}` : ''}
                          {t.resolved_by ? ` by ${t.resolved_by.slice(0, 8)}` : ''}
                        </p>
                      )}
                    </div>
                    {t.status === 'pending' && (
                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="outline"
                          onClick={() => void resolve(t.id, 'rejected')}
                          disabled={saving}
                        >
                          Reject
                        </Button>
                        <Button
                          onClick={() => void resolve(t.id, 'approved')}
                          disabled={saving}
                        >
                          {saving ? 'Saving…' : 'Approve & allowlist'}
                        </Button>
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <Card padding="lg">
        <h2 className="text-lg font-semibold text-[#0b2b43]">Destination allowlist</h2>
        <p className="text-sm text-[#6b7280] mt-1">
          Where HR is allowed to fire the AI scraper without going through the ticket queue.
          Adding a row here is the same as approving a pending ticket.
        </p>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-[2fr,2fr,3fr,auto] gap-3 items-end">
          <Input unstyled
            type="text"
            placeholder="City (e.g. Munich)"
            value={newCity}
            onChange={(v) => setNewCity(v)}
            className="rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43]"
          />
          <Input unstyled
            type="text"
            placeholder="Country (e.g. Germany)"
            value={newCountry}
            onChange={(v) => setNewCountry(v)}
            className="rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43]"
          />
          <Input unstyled
            type="text"
            placeholder="Notes (optional)"
            value={newNotes}
            onChange={(v) => setNewNotes(v)}
            className="rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43]"
          />
          <Button onClick={() => void addEntry()} disabled={adding || !newCity.trim() || !newCountry.trim()}>
            {adding ? 'Adding…' : 'Add'}
          </Button>
        </div>
        {allowlist.length > 0 ? (
          <ul className="mt-4 divide-y divide-[#e2e8f0] border border-[#e2e8f0] rounded-lg overflow-hidden bg-white">
            {allowlist.map((e) => (
              <li
                key={`${e.city}|${e.country}`}
                className="p-3 flex items-start justify-between gap-3"
              >
                <div className="min-w-0">
                  <span className="font-medium text-[#0b2b43]">{e.city}, {e.country}</span>
                  <span className="ml-2 text-xs text-[#94a3b8]">
                    added {formatDate(e.approved_at)}
                    {e.approved_by ? ` · by ${e.approved_by.slice(0, 8)}` : ''}
                  </span>
                  {e.notes && (
                    <p className="mt-1 text-sm text-[#475569]">{e.notes}</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-4 text-sm text-[#6b7280]">No allowlisted destinations yet.</p>
        )}
      </Card>
    </AdminLayout>
  );
};
