/**
 * HR Vendor Curation page (Phase 2e).
 *
 * Per (category, destination_city), HR sees the admin master vendors with
 * an on/off checkbox, plus their own custom vendors. They save in bulk;
 * employees see only what HR has marked selected. The page is the
 * implementation of the middle tier from
 * docs/RECOMMENDATIONS_CATALOG_ROUTINE.md.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Input } from '../components/antigravity/Input';
import { AppShell } from '../components/AppShell';
import { Alert, Button, Card } from '../components/antigravity';
import {
  addCustomVendor,
  bulkSelect,
  deleteCustomVendor,
  getCurationView,
  getScrapeQuota,
  listAllowlistedDestinations,
  listEmployeeDemand,
  populateDestinationWithAi,
  type AllowlistedDestination,
  type CurationRow,
  type DestinationRequest,
  type EmployeeDemandRow,
  type PopulateDestinationResult,
  type ScrapeQuotaState,
} from '../api/hrCatalog';

const CATEGORY_LABELS: Record<string, string> = {
  living_areas: 'Living areas / Housing',
  schools: 'Schools',
  movers: 'Movers',
  banks: 'Banks',
  insurance: 'Insurance',
  electricity: 'Electricity',
  medical: 'Medical',
  telecom: 'Telecom',
  childcare: 'Childcare',
  storage: 'Storage',
  transport: 'Transport',
  language_integration: 'Language / Integration',
  legal_admin: 'Legal & Admin',
  tax_finance: 'Tax & Finance',
};

function formatRelative(iso: string): string {
  try {
    const then = new Date(iso).getTime();
    const ms = Date.now() - then;
    const mins = Math.floor(ms / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  } catch {
    return '';
  }
}

const CATEGORY_OPTIONS: { value: string; label: string }[] = [
  { value: 'living_areas', label: 'Living areas / Housing' },
  { value: 'schools', label: 'Schools' },
  { value: 'movers', label: 'Movers' },
  { value: 'banks', label: 'Banks' },
  { value: 'insurance', label: 'Insurance' },
  { value: 'electricity', label: 'Electricity' },
  { value: 'medical', label: 'Medical' },
  { value: 'telecom', label: 'Telecom' },
  { value: 'childcare', label: 'Childcare' },
  { value: 'storage', label: 'Storage' },
  { value: 'transport', label: 'Transport' },
  { value: 'language_integration', label: 'Language / Integration' },
  { value: 'legal_admin', label: 'Legal & Admin' },
  { value: 'tax_finance', label: 'Tax & Finance' },
];

/** Sentinel value for the dropdown's "Request a new destination" option. */
const REQUEST_NEW_VALUE = '__request_new__';

function destinationKey(d: { city: string; country: string }): string {
  return `${d.city}|${d.country}`;
}

export const HrVendorCuration: React.FC = () => {
  const [category, setCategory] = useState<string>('schools');
  // Destinations come from the admin allowlist — HR can't type free-form.
  const [destinations, setDestinations] = useState<AllowlistedDestination[]>([]);
  const [destinationsLoading, setDestinationsLoading] = useState(false);
  // Selected destination key ("city|country"). Empty until user picks one.
  const [selectedDestinationKey, setSelectedDestinationKey] = useState<string>('');
  const [rows, setRows] = useState<CurationRow[]>([]);
  // Track unsaved master toggles: master_item_id -> next selected.
  const [pendingToggles, setPendingToggles] = useState<Map<string, boolean>>(new Map());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  // Add-custom form
  const [customName, setCustomName] = useState('');
  const [customNotes, setCustomNotes] = useState('');
  const [addingCustom, setAddingCustom] = useState(false);

  // Phase 2b-secured: destination-scoped scraper trigger state
  const [populating, setPopulating] = useState(false);
  const [populateResult, setPopulateResult] = useState<PopulateDestinationResult | null>(null);
  const [pendingTicket, setPendingTicket] = useState<DestinationRequest | null>(null);
  const [quota, setQuota] = useState<ScrapeQuotaState | null>(null);

  // Phase 2 notifications: employee demand backlog (what employees are waiting on).
  const [demand, setDemand] = useState<EmployeeDemandRow[]>([]);
  const [demandLoading, setDemandLoading] = useState(false);
  const [demandError, setDemandError] = useState(false);
  // Curate-jump target: when HR clicks "Curate" on a demand row, we scroll the
  // master-vendors card into view and flash a ring so the action is visible
  // even when (category, destination) didn't change.
  const masterCardRef = useRef<HTMLDivElement | null>(null);
  const [flashMaster, setFlashMaster] = useState(false);

  // "Request a new destination" modal state
  const [requestModalOpen, setRequestModalOpen] = useState(false);
  const [newCity, setNewCity] = useState('');
  const [newCountry, setNewCountry] = useState('');
  const [requesting, setRequesting] = useState(false);

  // Resolve the active destination from the dropdown selection.
  const activeDestination = useMemo<AllowlistedDestination | null>(() => {
    if (!selectedDestinationKey) return null;
    return destinations.find((d) => destinationKey(d) === selectedDestinationKey) || null;
  }, [destinations, selectedDestinationKey]);

  const city = activeDestination?.city || '';
  const country = activeDestination?.country || '';

  const reloadDestinations = useCallback(async (preferKey?: string) => {
    setDestinationsLoading(true);
    try {
      const list = await listAllowlistedDestinations();
      setDestinations(list);
      // Prefer an explicitly-passed key (right after a fresh approval), else
      // keep the current selection if still present, else first item.
      const preferred = preferKey && list.find((d) => destinationKey(d) === preferKey);
      if (preferred) {
        setSelectedDestinationKey(destinationKey(preferred));
      } else if (
        selectedDestinationKey
        && !list.find((d) => destinationKey(d) === selectedDestinationKey)
      ) {
        setSelectedDestinationKey(list.length > 0 ? destinationKey(list[0]) : '');
      } else if (!selectedDestinationKey && list.length > 0) {
        setSelectedDestinationKey(destinationKey(list[0]));
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load destinations.';
      setError(msg);
    } finally {
      setDestinationsLoading(false);
    }
  }, [selectedDestinationKey]);

  useEffect(() => {
    void reloadDestinations();
    // Intentionally fire only on mount — selectedDestinationKey is internal.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const reloadDemand = useCallback(async () => {
    setDemandLoading(true);
    setDemandError(false);
    // B16 fix: abort after 5 s so the widget never hangs on "Checking…" past
    // the validation criterion (5 s). The existing catch sets demandError=true
    // which renders "Could not load — check your connection and retry."
    const ac = new AbortController();
    const timer = window.setTimeout(() => ac.abort(), 5_000);
    try {
      const list = await listEmployeeDemand(ac.signal);
      setDemand(list);
    } catch {
      // Non-fatal — keep the widget visible but show an error state.
      setDemandError(true);
    } finally {
      window.clearTimeout(timer);
      setDemandLoading(false);
    }
  }, []);

  useEffect(() => {
    void reloadDemand();
  }, [reloadDemand]);

  const load = useCallback(async () => {
    if (!city) {
      setRows([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await getCurationView(category, city);
      setRows(data.rows);
      setPendingToggles(new Map());
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load curation.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [category, city]);

  useEffect(() => {
    void load();
  }, [load]);

  // Refresh quota state on category/city change so the badge stays current.
  useEffect(() => {
    void getScrapeQuota().then(setQuota).catch(() => setQuota(null));
    setPopulateResult(null);
    setPendingTicket(null);
  }, [category, city]);

  const onPickDestination = (value: string) => {
    if (value === REQUEST_NEW_VALUE) {
      setRequestModalOpen(true);
      return;
    }
    setSelectedDestinationKey(value);
  };

  const populateAllForDestination = async () => {
    if (!city || !country) {
      setError('Pick a destination first.');
      return;
    }
    setPopulating(true);
    setError(null);
    setPopulateResult(null);
    setPendingTicket(null);
    try {
      const result = await populateDestinationWithAi(city, country);
      if (result.status === 'pending_admin_approval') {
        // Should not happen — destination came from allowlist — but render it
        // gracefully if backend disagrees.
        setPendingTicket(result.request || null);
      } else {
        setPopulateResult(result);
        if (result.quota) setQuota(result.quota);
      }
      await load();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not populate with AI.';
      setError(msg);
      void getScrapeQuota().then(setQuota).catch(() => {});
    } finally {
      setPopulating(false);
    }
  };

  const submitNewDestinationRequest = async () => {
    const c = newCity.trim();
    const co = newCountry.trim();
    if (!c || !co) {
      setError('City and country are required.');
      return;
    }
    setRequesting(true);
    setError(null);
    try {
      const result = await populateDestinationWithAi(c, co);
      if (result.status === 'pending_admin_approval') {
        setPendingTicket(result.request || null);
        setRequestModalOpen(false);
        setNewCity('');
        setNewCountry('');
        setInfo(
          `Request sent for ${c}, ${co}. Once admin allowlists it, it'll appear in the destination dropdown.`,
        );
      } else {
        // Backend says it's already allowlisted — refresh and select it.
        await reloadDestinations(`${c}|${co}`);
        setRequestModalOpen(false);
        setNewCity('');
        setNewCountry('');
        setInfo(`${c}, ${co} is already supported. Selected.`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not open request.';
      setError(msg);
    } finally {
      setRequesting(false);
    }
  };

  const masters = useMemo(() => rows.filter((r) => r.kind === 'master'), [rows]);
  const customs = useMemo(() => rows.filter((r) => r.kind === 'custom'), [rows]);

  const togglePending = (masterId: string, current: boolean) => {
    setPendingToggles((prev) => {
      const next = new Map(prev);
      const target = next.get(masterId);
      const newValue = target === undefined ? !current : !target;
      // If the new value matches the server, drop the pending entry.
      if (newValue === current) {
        next.delete(masterId);
      } else {
        next.set(masterId, newValue);
      }
      return next;
    });
  };

  const effectiveSelected = (row: CurationRow): boolean => {
    if (row.kind !== 'master' || !row.master_item_id) return row.selected;
    const pending = pendingToggles.get(row.master_item_id);
    return pending !== undefined ? pending : row.selected;
  };

  const saveSelections = async () => {
    if (pendingToggles.size === 0) return;
    setSaving(true);
    setError(null);
    setInfo(null);
    try {
      const toggles = Array.from(pendingToggles.entries()).map(([master_item_id, selected]) => ({
        master_item_id,
        selected,
      }));
      const result = await bulkSelect({
        category,
        destination_city: city || null,
        toggles,
      });
      setInfo(`Saved ${result.updated} selection${result.updated === 1 ? '' : 's'}.`);
      await load();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not save selections.';
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  const submitCustom = async () => {
    if (!customName.trim()) {
      setError('Vendor name is required.');
      return;
    }
    setAddingCustom(true);
    setError(null);
    setInfo(null);
    try {
      await addCustomVendor({
        category,
        name: customName.trim(),
        attributes: customNotes.trim() ? { notes: customNotes.trim() } : {},
        destination_city: city || null,
      });
      setCustomName('');
      setCustomNotes('');
      setInfo('Custom vendor added.');
      await load();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not add custom vendor.';
      setError(msg);
    } finally {
      setAddingCustom(false);
    }
  };

  const removeCustom = async (selectionId: string | null) => {
    if (!selectionId) return;
    setError(null);
    try {
      await deleteCustomVendor(selectionId);
      await load();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not remove custom vendor.';
      setError(msg);
    }
  };

  const dirty = pendingToggles.size > 0;

  const totalEmployeesWaiting = useMemo(
    () => demand.reduce((acc, d) => acc + (d.demand_count || 0), 0),
    [demand],
  );
  const distinctCombos = demand.length;

  const jumpToDemand = (row: EmployeeDemandRow) => {
    setCategory(row.category);
    if (row.destination_city && row.destination_country) {
      const key = `${row.destination_city}|${row.destination_country}`;
      // Only switch if the destination is currently allowlisted; otherwise
      // surface a hint so HR knows admin still needs to approve it.
      if (destinations.find((d) => destinationKey(d) === key)) {
        setSelectedDestinationKey(key);
        setInfo(null);
      } else {
        setInfo(
          `${row.destination_city}, ${row.destination_country} isn't on your allowlist yet — ` +
            'use "Request a new destination" to send it to admin.',
        );
      }
    } else if (row.destination_city) {
      // Country missing on the demand row — try matching by city only.
      const match = destinations.find((d) => d.city === row.destination_city);
      if (match) setSelectedDestinationKey(destinationKey(match));
    }
    // Visible feedback even when the (category, destination) didn't change:
    // scroll the master-vendors card into view and briefly flash it.
    setFlashMaster(true);
    window.setTimeout(() => {
      masterCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 0);
    window.setTimeout(() => setFlashMaster(false), 1800);
  };

  return (
    <AppShell
      title="Vendor curation"
      subtitle="Choose which providers your employees see, per service and destination."
    >
      <Card padding="lg" className="mb-6 border border-[#fde68a] bg-[#fffbeb]">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-lg font-semibold text-[#92400e]">
                Employees waiting on you
              </h2>
              <p className="text-sm text-[#92400e]/90 mt-1">
                {demandLoading ? (
                  'Checking…'
                ) : demandError ? (
                  'Could not load — check your connection and retry.'
                ) : demand.length === 0 ? (
                  'No employees are currently waiting on vendor selections.'
                ) : (
                  <>
                    <strong>{totalEmployeesWaiting}</strong> employee view
                    {totalEmployeesWaiting === 1 ? '' : 's'} hit an empty state across{' '}
                    <strong>{distinctCombos}</strong> service / destination combo
                    {distinctCombos === 1 ? '' : 's'}. Pick a row to jump to it.
                  </>
                )}
              </p>
            </div>
            <Button variant="outline" onClick={() => void reloadDemand()} disabled={demandLoading}>
              {demandLoading ? 'Refreshing…' : 'Refresh'}
            </Button>
          </div>
          {demand.length > 0 && (
            <ul className="mt-4 divide-y divide-[#fde68a] border border-[#fde68a] rounded-lg overflow-hidden bg-white">
              {demand.slice(0, 8).map((row) => {
                const catLabel = CATEGORY_LABELS[row.category] || row.category;
                const dest =
                  row.destination_city && row.destination_country
                    ? `${row.destination_city}, ${row.destination_country}`
                    : row.destination_city || '—';
                return (
                  <li key={row.id} className="p-3 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-medium text-[#0b2b43]">
                        {catLabel} · {dest}
                      </div>
                      <div className="text-xs text-[#64748b] mt-0.5">
                        {row.demand_count} hit{row.demand_count === 1 ? '' : 's'} ·
                        {' '}last seen {formatRelative(row.last_seen_at)}
                      </div>
                    </div>
                    <Button variant="outline" onClick={() => jumpToDemand(row)}>
                      Curate
                    </Button>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

      <Card padding="lg" className="mb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <label className="block">
            <span className="text-sm font-medium text-[#0b2b43]">Destination</span>
            <select
              className="mt-1 w-full rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43]"
              value={selectedDestinationKey}
              onChange={(e) => onPickDestination(e.target.value)}
              disabled={destinationsLoading}
            >
              {destinations.length === 0 && !destinationsLoading && (
                <option value="">No destinations supported yet</option>
              )}
              {destinations.map((d) => (
                <option key={destinationKey(d)} value={destinationKey(d)}>
                  {d.city}, {d.country}
                </option>
              ))}
              <option value={REQUEST_NEW_VALUE}>+ Request a new destination…</option>
            </select>
            <p className="mt-1 text-xs text-[#94a3b8]">
              HR can pick from supported destinations only. New destinations need admin approval.
            </p>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-[#0b2b43]">Service category</span>
            <select
              className="mt-1 w-full rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43]"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {CATEGORY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <div className="flex items-end gap-2 flex-wrap">
            <Button
              onClick={() => void populateAllForDestination()}
              disabled={populating || !city || !country}
              title={
                !city || !country
                  ? 'Pick a destination first'
                  : `Populate every service category for ${city}, ${country} with AI`
              }
            >
              {populating ? 'Asking the AI…' : 'Populate all services with AI'}
            </Button>
            <Button onClick={() => void load()} disabled={loading} variant="outline">
              {loading ? 'Loading…' : 'Reload'}
            </Button>
          </div>
        </div>
        {quota && (
          <p className="mt-3 text-xs text-[#64748b]">
            AI catalog quota today: <strong className="text-[#0b2b43]">{quota.used}/{quota.limit}</strong> used
            ({quota.remaining} remaining; resets at midnight UTC). Each service category that
            actually calls the AI counts as 1 — already-populated categories don't.
          </p>
        )}
        {populateResult && populateResult.status === 'completed' && (
          <Alert variant="success" className="mt-3">
            {populateResult.total_inserted ? (
              <>
                AI populated <strong>{populateResult.total_inserted}</strong> vendors across{' '}
                <strong>{populateResult.categories_populated}</strong> service categor
                {populateResult.categories_populated === 1 ? 'y' : 'ies'} for {city}, {country}.{' '}
                {(populateResult.categories_skipped_existing || 0) > 0 && (
                  <>
                    Skipped {populateResult.categories_skipped_existing} already-populated categor
                    {populateResult.categories_skipped_existing === 1 ? 'y' : 'ies'} (no AI tokens used).{' '}
                  </>
                )}
                {(populateResult.categories_quota_blocked || 0) > 0 && (
                  <>
                    {populateResult.categories_quota_blocked} categor
                    {populateResult.categories_quota_blocked === 1 ? 'y' : 'ies'} hit your daily quota — try again tomorrow (UTC).{' '}
                  </>
                )}
                Pick a category below to review and tick the ones to show your employees.
              </>
            ) : (
              <>
                {city} already has master vendors for every service category. Nothing was added — no AI tokens used.
              </>
            )}
          </Alert>
        )}
        {pendingTicket && (
          <Alert variant="info" className="mt-3">
            Ticket opened for {pendingTicket.city}, {pendingTicket.country}. Waiting on admin to
            allowlist this destination.
          </Alert>
        )}
      </Card>

      {requestModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#0b2b43]/40 px-4"
          onClick={(e) => {
            if (e.target === e.currentTarget && !requesting) setRequestModalOpen(false);
          }}
        >
          <Card padding="lg" className="w-full max-w-md bg-white">
            <h3 className="text-lg font-semibold text-[#0b2b43]">Request a new destination</h3>
            <p className="mt-2 text-sm text-[#4b5563]">
              Tell us where your employee is moving. Admin reviews and approves
              new destinations to keep AI usage controlled — once approved you can
              populate every service category with one click.
            </p>
            <label className="mt-4 block text-sm font-medium text-[#0b2b43]">
              City
              <Input unstyled
                type="text"
                className="mt-1 w-full rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43]"
                value={newCity}
                onChange={(v) => setNewCity(v)}
                placeholder="e.g. Tokyo"
                disabled={requesting}
              />
            </label>
            <label className="mt-3 block text-sm font-medium text-[#0b2b43]">
              Country
              <Input unstyled
                type="text"
                className="mt-1 w-full rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43]"
                value={newCountry}
                onChange={(v) => setNewCountry(v)}
                placeholder="e.g. Japan"
                disabled={requesting}
              />
            </label>
            <div className="mt-5 flex flex-wrap items-center justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setRequestModalOpen(false)}
                disabled={requesting}
              >
                Cancel
              </Button>
              <Button
                onClick={() => void submitNewDestinationRequest()}
                disabled={requesting || !newCity.trim() || !newCountry.trim()}
              >
                {requesting ? 'Sending…' : 'Send request to admin'}
              </Button>
            </div>
          </Card>
        </div>
      )}

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}
      {info && <Alert variant="success" className="mb-4">{info}</Alert>}

      <Card
        padding="lg"
        className={`mb-6 transition-shadow ${
          flashMaster ? 'ring-4 ring-[#fde68a] ring-offset-2' : ''
        }`}
      >
        <div ref={masterCardRef} className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div>
            <h2 className="text-lg font-semibold text-[#0b2b43]">Admin master vendors</h2>
            <p className="text-sm text-[#6b7280] mt-1">
              {(() => {
                const selectedMasters = masters.filter((r) => effectiveSelected(r)).length;
                const visibleToEmployees = selectedMasters + customs.length;
                return (
                  <>
                    {selectedMasters} of {masters.length} admin item{masters.length === 1 ? '' : 's'}{' '}
                    selected for {category} in {city || '—'}
                    {customs.length > 0 && (
                      <>
                        {' '}· {customs.length} custom vendor{customs.length === 1 ? '' : 's'} added
                      </>
                    )}
                    {' '}<strong className="text-[#0b2b43]">
                      → {visibleToEmployees} visible to employees
                    </strong>. Untick to hide.
                  </>
                );
              })()}
            </p>
          </div>
          <Button onClick={() => void saveSelections()} disabled={!dirty || saving}>
            {saving ? 'Saving…' : dirty ? `Save ${pendingToggles.size} change${pendingToggles.size === 1 ? '' : 's'}` : 'No changes to save'}
          </Button>
        </div>
        {masters.length === 0 ? (
          <div className="py-2">
            <p className="text-sm text-[#4b5563]">
              No master vendors yet for {category} in {city || 'this destination'}.{' '}
              {city && country ? (
                <>
                  Use <strong>Populate all services with AI</strong> at the top of the page to
                  populate every category in one click, or add your own preferred vendors below.
                </>
              ) : (
                <>Pick a destination at the top to begin, or add your own preferred vendors below.</>
              )}
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-[#e2e8f0] border border-[#e2e8f0] rounded-lg overflow-hidden bg-white">
            {masters.map((row) => {
              const selected = effectiveSelected(row);
              const pending = row.master_item_id ? pendingToggles.has(row.master_item_id) : false;
              return (
                <li key={row.master_item_id || row.name} className="p-3 flex items-center justify-between gap-3">
                  <label className="flex items-center gap-3 min-w-0 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => row.master_item_id && togglePending(row.master_item_id, row.selected)}
                      className="h-4 w-4 shrink-0"
                    />
                    <span className="min-w-0">
                      <span className="font-medium text-[#0b2b43]">{row.name}</span>
                      {row.source && (
                        <span className="ml-2 text-xs text-[#94a3b8]">source: {row.source}</span>
                      )}
                      {pending && (
                        <span className="ml-2 inline-flex items-center rounded-full border border-[#fde68a] bg-[#fef9c3] px-2 py-0.5 text-xs font-medium text-[#854d0e]">
                          unsaved
                        </span>
                      )}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <Card padding="lg">
        <h2 className="text-lg font-semibold text-[#0b2b43]">Your own preferred vendors</h2>
        <p className="text-sm text-[#6b7280] mt-1">
          Add vendors not in the admin master list. Visible to your employees alongside the
          ticked admin items above.
        </p>

        {customs.length > 0 && (
          <ul className="mt-4 divide-y divide-[#e2e8f0] border border-[#e2e8f0] rounded-lg overflow-hidden bg-white">
            {customs.map((row) => {
              const notes = (row.attributes?.notes as string | undefined) || '';
              return (
                <li key={row.selection_id || row.name} className="p-3 flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-medium text-[#0b2b43]">{row.name}</div>
                    {notes && (
                      <p className="mt-1 text-sm text-[#475569] whitespace-pre-line">{notes}</p>
                    )}
                  </div>
                  <Button variant="outline" onClick={() => void removeCustom(row.selection_id)}>
                    Remove
                  </Button>
                </li>
              );
            })}
          </ul>
        )}

        <div className="mt-4 grid grid-cols-1 md:grid-cols-[2fr,3fr] gap-3">
          <Input unstyled
            type="text"
            placeholder="Vendor name (e.g. ABC Movers Munich)"
            value={customName}
            onChange={(v) => setCustomName(v)}
            className="rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43]"
          />
          <Input unstyled
            type="text"
            placeholder="Notes for the employee (optional)"
            value={customNotes}
            onChange={(v) => setCustomNotes(v)}
            className="rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43]"
          />
        </div>
        <div className="mt-3 flex justify-end">
          <Button onClick={() => void submitCustom()} disabled={addingCustom || !customName.trim()}>
            {addingCustom ? 'Adding…' : 'Add vendor'}
          </Button>
        </div>
      </Card>
    </AppShell>
  );
};
