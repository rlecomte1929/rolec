/**
 * Admin queue for HR-opened destination requests + allowlist management.
 * Phase 2b-secured UI (admin side).
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { Alert, Button, Card } from '../../components/antigravity';
import {
  addAllowlistEntry,
  listAdminDestinationRequests,
  listAllowlist,
  resolveDestinationRequest,
  type AllowlistEntry,
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

  // Manual allowlist add form
  const [newCity, setNewCity] = useState('');
  const [newCountry, setNewCountry] = useState('');
  const [newNotes, setNewNotes] = useState('');
  const [adding, setAdding] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [t, a] = await Promise.all([
        listAdminDestinationRequests(tab),
        listAllowlist(),
      ]);
      setTickets(t);
      setAllowlistState(a);
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

  const allowlistByDest = useMemo(() => {
    const set = new Set<string>();
    for (const e of allowlist) set.add(`${e.city.toLowerCase()}|${e.country.toLowerCase()}`);
    return set;
  }, [allowlist]);

  return (
    <AppShell
      title="Catalog destination queue"
      subtitle="HR-opened scrape requests + admin-managed allowlist."
    >
      {error && <Alert variant="error" className="mb-4">{error}</Alert>}
      {info && <Alert variant="success" className="mb-4">{info}</Alert>}

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
              <button
                key={s.value}
                onClick={() => setTab(s.value)}
                className={`px-3 py-1 rounded-full border text-sm ${
                  tab === s.value
                    ? 'border-[#0b2b43] bg-[#0b2b43] text-white'
                    : 'border-[#cbd5e1] text-[#475569] hover:bg-[#f1f5f9]'
                }`}
              >
                {s.label}
              </button>
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
          <input
            type="text"
            placeholder="City (e.g. Munich)"
            value={newCity}
            onChange={(e) => setNewCity(e.target.value)}
            className="rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43]"
          />
          <input
            type="text"
            placeholder="Country (e.g. Germany)"
            value={newCountry}
            onChange={(e) => setNewCountry(e.target.value)}
            className="rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43]"
          />
          <input
            type="text"
            placeholder="Notes (optional)"
            value={newNotes}
            onChange={(e) => setNewNotes(e.target.value)}
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
    </AppShell>
  );
};
