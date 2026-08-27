import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Alert, Badge, Select, Input } from '../../components/antigravity';
import { Checkbox } from '../../components/antigravity/Checkbox';
import { suppliersAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { AdminLayout } from './AdminLayout';

export type PendingCapability = {
  supplier_id: string;
  supplier_name: string;
  capability_id: string;
  service_category: string;
  country_code?: string | null;
  city_name?: string | null;
  source?: string | null;
  source_url?: string | null;
  /** [AIQ-1788] Present for registry-harvested suppliers; absent for manually-added ones. */
  accreditation?: {
    body: string;
    number?: string | null;
    valid_until?: string | null;
    status: string;
    evidence_url?: string | null;
  } | null;
  created_at?: string | null;
};

export type CapabilityFilters = { country: string; service: string; name: string };

/**
 * [AIQ-1850] Narrow the pending list by country, service category, and
 * supplier name. All three are AND-combined; empty filters match everything.
 * Name is a case-insensitive substring match on the supplier name.
 */
export function filterCapabilities(
  items: PendingCapability[],
  filters: CapabilityFilters
): PendingCapability[] {
  const name = filters.name.trim().toLowerCase();
  return items.filter((row) => {
    if (filters.country && (row.country_code || '') !== filters.country) return false;
    if (filters.service && row.service_category !== filters.service) return false;
    if (name && !row.supplier_name.toLowerCase().includes(name)) return false;
    return true;
  });
}

/**
 * [AIQ-1850] Distinct companies (by supplier_id, since one supplier can have
 * several pending capabilities) and distinct countries (by country_code,
 * ignoring rows with no country) represented in the given rows.
 */
export function distinctCounts(items: PendingCapability[]): {
  companies: number;
  countries: number;
} {
  const companies = new Set<string>();
  const countries = new Set<string>();
  for (const row of items) {
    companies.add(row.supplier_id);
    if (row.country_code) countries.add(row.country_code);
  }
  return { companies: companies.size, countries: countries.size };
}

function optionsFrom(values: (string | null | undefined)[]): { value: string; label: string }[] {
  const seen = new Set<string>();
  for (const v of values) {
    if (v) seen.add(v);
  }
  return Array.from(seen).map((v) => ({ value: v, label: v }));
}

function errMessage(err: unknown, fallback: string): string {
  const msg =
    err && typeof err === 'object' && 'response' in err
      ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
      : (err as Error)?.message;
  return String(msg || fallback);
}

export const AdminVettingQueue: React.FC = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState<PendingCapability[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [rejectingCapId, setRejectingCapId] = useState<string | null>(null);
  const [rejectNotes, setRejectNotes] = useState('');

  // [AIQ-1850] Filters, multi-select, and batch approval.
  const [filters, setFilters] = useState<CapabilityFilters>({ country: '', service: '', name: '' });
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchFeedback, setBatchFeedback] = useState<'idle' | 'approving' | 'done' | 'error'>('idle');
  const [batchError, setBatchError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await suppliersAPI.listPendingCapabilities();
      setItems((data.capabilities || []) as PendingCapability[]);
    } catch (err: unknown) {
      setError(errMessage(err, 'Failed to load pending capabilities'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => filterCapabilities(items, filters), [items, filters]);
  const counts = useMemo(() => distinctCounts(filtered), [filtered]);
  const countryOptions = useMemo(() => optionsFrom(items.map((r) => r.country_code)), [items]);
  const serviceOptions = useMemo(() => optionsFrom(items.map((r) => r.service_category)), [items]);

  // Selection is keyed by capability_id and scoped to the visible (filtered)
  // rows — changing a filter clears it so "Select all" never carries hidden rows.
  const updateFilter = useCallback((patch: Partial<CapabilityFilters>) => {
    setFilters((f) => ({ ...f, ...patch }));
    setSelectedIds(new Set());
    setBatchFeedback('idle');
    setBatchError(null);
  }, []);

  const selectedRows = useMemo(
    () => filtered.filter((r) => selectedIds.has(r.capability_id)),
    [filtered, selectedIds]
  );
  const allVisibleSelected =
    filtered.length > 0 && filtered.every((r) => selectedIds.has(r.capability_id));

  const toggleRow = useCallback((capabilityId: string, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(capabilityId);
      else next.delete(capabilityId);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(
    (checked: boolean) => {
      setSelectedIds(checked ? new Set(filtered.map((r) => r.capability_id)) : new Set());
    },
    [filtered]
  );

  const approve = useCallback(
    async (row: PendingCapability) => {
      setSaving(true);
      setError(null);
      try {
        await suppliersAPI.approveCapability(row.supplier_id, row.capability_id);
        await load();
      } catch (err: unknown) {
        setError(errMessage(err, 'Failed to approve capability'));
      } finally {
        setSaving(false);
      }
    },
    [load]
  );

  // [AIQ-1850] Batch approve mirrors the employee-cases (AdminAssignments)
  // pattern: Promise.allSettled over the existing single-item endpoint, with
  // partial-failure reporting. There is no dedicated batch backend route.
  const approveSelected = useCallback(async () => {
    if (selectedRows.length === 0) return;
    setBatchFeedback('approving');
    setBatchError(null);
    setError(null);
    const results = await Promise.allSettled(
      selectedRows.map((r) => suppliersAPI.approveCapability(r.supplier_id, r.capability_id))
    );
    const rejected = results.filter(
      (r): r is PromiseRejectedResult => r.status === 'rejected'
    );
    setSelectedIds(new Set());
    await load();
    if (rejected.length === 0) {
      setBatchFeedback('done');
    } else {
      setBatchFeedback('error');
      const detail = errMessage(rejected[0]?.reason, 'unknown error');
      setBatchError(
        rejected.length > 1
          ? `${rejected.length} of ${results.length} failed (first: ${detail})`
          : detail
      );
    }
  }, [selectedRows, load]);

  const reject = useCallback(
    async (row: PendingCapability, notes: string) => {
      if (!notes.trim()) return;
      setSaving(true);
      setError(null);
      try {
        await suppliersAPI.rejectCapability(row.supplier_id, row.capability_id, notes.trim());
        setRejectingCapId(null);
        setRejectNotes('');
        await load();
      } catch (err: unknown) {
        setError(errMessage(err, 'Failed to reject capability'));
      } finally {
        setSaving(false);
      }
    },
    [load]
  );

  const batchBusy = batchFeedback === 'approving';

  return (
    <AdminLayout
      title="Vetting queue"
      subtitle="Supplier capabilities awaiting a platform review decision"
    >
      {error && (
        <div className="mb-4">
          <Alert variant="error">{error}</Alert>
        </div>
      )}

      {/* [AIQ-1850] Filters + summary counts at the top of the page. */}
      <Card padding="lg" className="mb-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Select
            label="Country"
            value={filters.country}
            onChange={(v) => updateFilter({ country: v })}
            options={countryOptions}
            placeholder="All countries"
          />
          <Select
            label="Type of service"
            value={filters.service}
            onChange={(v) => updateFilter({ service: v })}
            options={serviceOptions}
            placeholder="All services"
          />
          <Input
            label="Name"
            value={filters.name}
            onChange={(v) => updateFilter({ name: v })}
            placeholder="Filter by supplier name"
          />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-[#6b7280]">
          <span>
            <span className="font-medium text-[#0b2b43]">{counts.companies}</span>{' '}
            {counts.companies === 1 ? 'company' : 'companies'}
          </span>
          <span>
            <span className="font-medium text-[#0b2b43]">{counts.countries}</span>{' '}
            {counts.countries === 1 ? 'country' : 'countries'}
          </span>
          <span className="text-gray-500">
            {filtered.length} of {items.length} pending
          </span>
        </div>
      </Card>

      <Card padding="lg">
        {loading ? (
          <p className="text-sm text-[#6b7280]">Loading pending capabilities…</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-[#6b7280]">
            No pending capabilities — catalog is fully reviewed.
          </p>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-[#6b7280]">No capabilities match the current filters.</p>
        ) : (
          <>
            {/* [AIQ-1850] Select-all + batch approve toolbar. */}
            <div className="flex flex-wrap items-center justify-between gap-3 pb-3 mb-1 border-b border-[#e5e7eb]">
              <label className="flex items-center gap-2 text-sm text-[#374151] cursor-pointer">
                <Checkbox
                  className="h-4 w-4 rounded border-[#cbd5e1]"
                  checked={allVisibleSelected}
                  onChange={(e) => toggleSelectAll(e.target.checked)}
                  disabled={batchBusy}
                />
                Select all
              </label>
              <div className="flex items-center gap-3 flex-wrap">
                {batchFeedback === 'done' && (
                  <span className="text-sm text-green-600">Approved. List updated.</span>
                )}
                {batchFeedback === 'error' && (
                  <span className="text-sm text-red-600">
                    {batchError ? `Batch approve failed: ${batchError}` : 'Batch approve failed.'}
                  </span>
                )}
                <span className="text-sm text-[#6b7280]">{selectedRows.length} selected</span>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={approveSelected}
                  disabled={selectedRows.length === 0 || batchBusy || saving}
                >
                  {batchBusy ? 'Approving…' : `Approve selected (${selectedRows.length})`}
                </Button>
              </div>
            </div>

            <ul className="divide-y divide-[#e5e7eb]">
              {filtered.map((row) => (
                <li key={row.capability_id} className="py-4 flex justify-between items-start gap-4">
                  <div className="flex items-start gap-3 min-w-0 flex-1">
                    <Checkbox
                      className="h-4 w-4 mt-1 rounded border-[#cbd5e1] shrink-0"
                      checked={selectedIds.has(row.capability_id)}
                      onChange={(e) => toggleRow(row.capability_id, e.target.checked)}
                      disabled={batchBusy}
                      aria-label={`Select ${row.supplier_name}`}
                    />
                    <button
                      type="button"
                      className="text-left min-w-0"
                      onClick={() => navigate(buildRoute('adminSuppliersDetail', { id: row.supplier_id }))}
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-[#0b2b43]">{row.supplier_name}</span>
                        {row.source && <Badge variant="neutral" size="sm">{row.source}</Badge>}
                      </div>
                      <div className="text-sm text-[#6b7280] mt-1">
                        {row.service_category}
                        {row.country_code && ` • ${row.country_code}`}
                        {row.city_name && ` • ${row.city_name}`}
                      </div>
                      {row.created_at && (
                        <div className="text-xs text-gray-500 mt-1">
                          Discovered {new Date(row.created_at).toLocaleDateString()}
                        </div>
                      )}
                    </button>
                  </div>

                  {/* [AIQ-1788] Registry-harvested suppliers arrive with accreditation evidence.
                      Approving one without being able to see WHICH register vouched for it is a
                      rubber stamp, and the evidence is the only thing separating a harvested
                      candidate from a scrape. Absent for manually-added suppliers, so both the
                      block and the link render only when there is something to show. */}
                  {(row.accreditation || row.source_url) && (
                    <div className="text-xs text-[#6b7280] mt-1 min-w-0 flex-1">
                      {row.accreditation && (
                        <div>
                          <span className="text-[#0b2b43]">{row.accreditation.body}</span>
                          {row.accreditation.number && ` · ${row.accreditation.number}`}
                          {row.accreditation.valid_until &&
                            ` · expires ${row.accreditation.valid_until}`}
                          {row.accreditation.status === 'claimed' && (
                            <span className="text-gray-500"> · unverified</span>
                          )}
                        </div>
                      )}
                      {row.source_url && (
                        <a
                          href={
                            row.source_url.startsWith('http')
                              ? row.source_url
                              : `https://${row.source_url}`
                          }
                          target="_blank"
                          rel="noreferrer noopener"
                          className="text-accent-700 underline break-all"
                        >
                          Check the register ↗
                        </a>
                      )}
                    </div>
                  )}

                  <div className="flex flex-col items-end gap-2 shrink-0">
                    <Button variant="secondary" size="sm" onClick={() => approve(row)} disabled={saving || batchBusy}>
                      Approve
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setRejectingCapId((prev) => (prev === row.capability_id ? null : row.capability_id))
                      }
                      disabled={saving || batchBusy}
                    >
                      Reject
                    </Button>
                    {rejectingCapId === row.capability_id && (
                      <div className="w-56">
                        <textarea
                          value={rejectNotes}
                          onChange={(e) => setRejectNotes(e.target.value)}
                          rows={2}
                          placeholder="Reason for rejection (required)"
                          className="w-full border border-[#d1d5db] rounded px-2 py-1 text-sm"
                        />
                        <div className="flex justify-end gap-2 mt-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setRejectingCapId(null);
                              setRejectNotes('');
                            }}
                            disabled={saving}
                          >
                            Cancel
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => reject(row, rejectNotes)}
                            disabled={saving || !rejectNotes.trim()}
                          >
                            Confirm reject
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </Card>
    </AdminLayout>
  );
};
