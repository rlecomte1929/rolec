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
import { Info } from 'lucide-react';
import { Checkbox } from '../components/antigravity/Checkbox';
import { Input } from '../components/antigravity/Input';
import { AppShell } from '../components/AppShell';
import { CityPicker, CountryPicker, canonPlace } from '../components/location';
import { getCountryName } from '../utils/countries';
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
  populateVendorsWithAi,
  discoverVendorsForCity,
  type AllowlistedDestination,
  type CurationRow,
  type DestinationRequest,
  type EmployeeDemandRow,
  type PopulateDestinationResult,
  type PopulateWithAiResult,
  type ScrapeQuotaState,
} from '../api/hrCatalog';
import { serviceTypeOptions, filterByServiceType } from './hrVendorServiceTypes';
import { HrPreferredSupplierCard } from './HrPreferredSupplierCard';

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
  pets: 'Pets',
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
  { value: 'pets', label: 'Pets' },
];

/** Sentinel value for the dropdown's "Request a new destination" option. */
const REQUEST_NEW_VALUE = '__request_new__';

/** Prefer a full country NAME over an ISO code, and a title-cased spelling over a lower-cased
 *  one — the convention 71 of 74 allowlist countries already follow. Used to pick which
 *  spelling represents a country once duplicates are collapsed. */
function _betterCountryLabel(candidate: string, current: string): boolean {
  const isCode = (v: string) => v.trim().length === 2;
  if (isCode(candidate) !== isCode(current)) return !isCode(candidate);
  const titled = (v: string) => v.trim().slice(0, 1) === v.trim().slice(0, 1).toUpperCase();
  if (titled(candidate) !== titled(current)) return titled(candidate);
  return false;
}

function destinationKey(d: { city: string; country: string }): string {
  return `${d.city}|${d.country}`;
}

/**
 * `embedded`: when rendered as the "Vendor Management" tab inside another
 * AppShell (HrServiceProvidersPage, NAV-SP-1), skip the outer AppShell so we
 * don't double-nest the platform shell. Default off → the standalone
 * /hr/vendor-curation route is unchanged.
 */
export const HrVendorCuration: React.FC<{ embedded?: boolean }> = ({ embedded = false }) => {
  // AIQ-1444 pt3: start with no service type chosen so the Admin master-vendors
  // section stays hidden until HR explicitly picks a category.
  const [category, setCategory] = useState<string>('');
  // Destinations come from the admin allowlist — HR can't type free-form.
  const [destinations, setDestinations] = useState<AllowlistedDestination[]>([]);
  const [destinationsLoading, setDestinationsLoading] = useState(false);
  // Selected destination key ("city|country"). Empty until user picks one.
  const [selectedDestinationKey, setSelectedDestinationKey] = useState<string>('');
  // AIQ-1444 pt2: country is picked first, then a dependent city dropdown resolves
  // the destination. Kept in sync with the active destination (below) so programmatic
  // selections (approval flow, edit-row) keep the country dropdown correct.
  const [selectedCountry, setSelectedCountry] = useState<string>('');
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
  // AIQ-1465: per-category progress while "Populate all" fans the scrape out
  // one category at a time (so no single request outlives the gateway timeout).
  const [populateProgress, setPopulateProgress] = useState<{ done: number; total: number; label: string } | null>(null);
  const [populateResult, setPopulateResult] = useState<PopulateDestinationResult | null>(null);
  const [pendingTicket, setPendingTicket] = useState<DestinationRequest | null>(null);
  const [quota, setQuota] = useState<ScrapeQuotaState | null>(null);

  // VEN-12: real-business discovery for this (category, city) when the list is empty.
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [discoverError, setDiscoverError] = useState<string | null>(null);

  // Phase 2 notifications: employee demand backlog (what employees are waiting on).
  const [demand, setDemand] = useState<EmployeeDemandRow[]>([]);
  const [demandLoading, setDemandLoading] = useState(false);
  const [demandError, setDemandError] = useState(false);
  // Curate-jump target: when HR clicks "Curate" on a demand row, we scroll the
  // master-vendors card into view and flash a ring so the action is visible
  // even when (category, destination) didn't change.
  const masterCardRef = useRef<HTMLDivElement | null>(null);
  const [flashMaster, setFlashMaster] = useState(false);

  // AIQ-1576: one-time "how this page works" banner, dismissed per browser.
  const [instructionsDismissed, setInstructionsDismissed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('relopass_sp_instructions_dismissed') === '1';
    } catch {
      return false;
    }
  });
  const dismissInstructions = () => {
    try {
      localStorage.setItem('relopass_sp_instructions_dismissed', '1');
    } catch {
      // ignore — storage blocked; banner just reappears next load
    }
    setInstructionsDismissed(true);
  };
  const scrollToMasterCard = () => {
    setFlashMaster(true);
    masterCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    window.setTimeout(() => setFlashMaster(false), 1800);
  };

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

  // AIQ-1444: show the destination dropdown sorted alphabetically by country, then
  // city (locale-aware) — the raw list came back unordered.
  const sortedDestinations = useMemo(
    () =>
      [...destinations].sort(
        (a, b) => a.country.localeCompare(b.country) || a.city.localeCompare(b.city),
      ),
    [destinations],
  );

  // AIQ-1444 pt2: distinct countries (A-Z) for the country dropdown, and the
  // cities (A-Z) available under the currently-selected country for the dependent
  // city dropdown.
  // De-duped by CANONICAL key, not by exact string. The allowlist held Ireland as 'IE',
  // 'Ireland' and 'ireland', so a raw Set offered three Irelands — and picking the
  // lower-cased one sent destination_city='dublin', which the master-item filter then
  // failed to match, hiding 29 curated vendors. One entry per country, and the
  // best-formed spelling wins (title-cased full name over an ISO code).
  const countryOptions = useMemo(() => {
    const best = new Map<string, string>();
    for (const d of destinations) {
      const key = canonPlace(d.country);
      if (!key) continue;
      const current = best.get(key);
      if (current === undefined || _betterCountryLabel(d.country, current)) {
        best.set(key, d.country);
      }
    }
    return Array.from(best.values()).sort((a, b) => a.localeCompare(b));
  }, [destinations]);

  // Canonical match, so a country picked as 'Ireland' still finds a row stored as 'ireland'.
  const citiesForCountry = useMemo(
    () =>
      selectedCountry
        ? sortedDestinations.filter(
            (d) => canonPlace(d.country) === canonPlace(selectedCountry),
          )
        : [],
    [sortedDestinations, selectedCountry],
  );

  // Keep the country dropdown aligned when the destination is set programmatically
  // (approval flow, edit-row) rather than via the country dropdown itself.
  useEffect(() => {
    if (activeDestination && activeDestination.country !== selectedCountry) {
      setSelectedCountry(activeDestination.country);
    }
  }, [activeDestination, selectedCountry]);

  const city = activeDestination?.city || '';
  const country = activeDestination?.country || '';

  const reloadDestinations = useCallback(async (preferKey?: string) => {
    setDestinationsLoading(true);
    try {
      const list = await listAllowlistedDestinations();
      setDestinations(list);
      // Prefer an explicitly-passed key (right after a fresh approval), else
      // keep the current selection if still present, else first item.
      const first = list[0];
      const preferred = preferKey && list.find((d) => destinationKey(d) === preferKey);
      if (preferred) {
        setSelectedDestinationKey(destinationKey(preferred));
      } else if (
        selectedDestinationKey
        && !list.find((d) => destinationKey(d) === selectedDestinationKey)
      ) {
        // Current selection disappeared (e.g. destination removed) — fall back to first.
        setSelectedDestinationKey(first ? destinationKey(first) : '');
      }
      // AIQ-1577: do NOT auto-select the first destination on mount. HR should start
      // from an empty "Select a country / city" state and choose deliberately, rather
      // than landing on a pre-filled destination that looks like a made choice.
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
    if (!city || !category) {
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

  // VEN-12: find real, quality-vetted vendors for this (category, city) and
  // refresh the list so they appear.
  const handleFetchVendors = useCallback(async () => {
    if (!city || !country) return;
    setIsDiscovering(true);
    setDiscoverError(null);
    try {
      const res = await discoverVendorsForCity(category, city, country);
      if (res.status === 'pending_admin_approval') {
        setDiscoverError(res.message || 'This destination needs admin approval first.');
      } else if (!res.count) {
        setDiscoverError(res.message || 'No verified vendors found for this city yet.');
      }
      await load();
    } catch {
      setDiscoverError('Could not find vendors right now. Please try again.');
    } finally {
      setIsDiscovering(false);
    }
  }, [category, city, country, load]);

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

  // AIQ-1444 pt2: picking a country resets the dependent city selection.
  const onPickCountry = (value: string) => {
    if (value === REQUEST_NEW_VALUE) {
      setRequestModalOpen(true);
      return;
    }
    setSelectedCountry(value);
    setSelectedDestinationKey('');
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
    // AIQ-1465: fan the populate out one category per request (each a single short
    // LLM call) instead of one long request that ran the whole multi-category scrape
    // server-side — that request outlived the edge/gateway timeout, the connection was
    // dropped, and the client surfaced the generic "Unable to reach the server." Each
    // per-category call here also runs the backfill, so this matches the old behaviour.
    const cats = CATEGORY_OPTIONS;
    const perCategory: Array<{ category: string; status: string; inserted: number }> = [];
    let populated = 0;
    let skipped = 0;
    let quotaBlocked = 0;
    let totalInserted = 0;
    let latestQuota: ScrapeQuotaState | null = null;
    try {
      for (let i = 0; i < cats.length; i += 1) {
        const cat = cats[i];
        if (!cat) continue;
        setPopulateProgress({ done: i, total: cats.length, label: cat.label });
        let res: PopulateWithAiResult;
        try {
          res = await populateVendorsWithAi(cat.value, city, country);
        } catch (err: unknown) {
          // Daily quota reached mid-run (429): the rest would all fail the same way,
          // so stop and count the remainder as quota-blocked.
          if ((err as { status?: number })?.status === 429) {
            quotaBlocked += cats.length - i;
            for (let j = i; j < cats.length; j += 1) {
              const cj = cats[j];
              if (cj) perCategory.push({ category: cj.value, status: 'quota_blocked', inserted: 0 });
            }
            break;
          }
          perCategory.push({ category: cat.value, status: 'error', inserted: 0 });
          continue;
        }
        if (res.status === 'pending_admin_approval') {
          // Destination isn't on the allowlist — the whole (city,country) needs approval,
          // so stop and surface the ticket exactly as before.
          setPendingTicket(res.request || null);
          return;
        }
        if (res.quota) latestQuota = res.quota;
        const inserted = res.inserted ?? 0;
        if (inserted > 0) {
          populated += 1;
          totalInserted += inserted;
          perCategory.push({ category: cat.value, status: 'populated', inserted });
        } else {
          // Already-populated (L1 short-circuit) or nothing found — no new rows either way.
          skipped += 1;
          perCategory.push({ category: cat.value, status: 'skipped_existing', inserted: 0 });
        }
      }
      setPopulateResult({
        status: 'completed',
        destination_city: city,
        country,
        categories_total: cats.length,
        categories_populated: populated,
        categories_skipped_existing: skipped,
        categories_quota_blocked: quotaBlocked,
        total_inserted: totalInserted,
        per_category: perCategory,
        quota: latestQuota ?? undefined,
      });
      if (latestQuota) setQuota(latestQuota);
      await load();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not populate with AI.';
      setError(msg);
      void getScrapeQuota().then(setQuota).catch(() => {});
    } finally {
      setPopulating(false);
      setPopulateProgress(null);
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
          `Request sent for ${c}, ${co} — we've emailed the ReloPass team. Once they source and allowlist it, it'll appear in the destination dropdown.`,
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

  // Service-type filter. Tags are free-form (assigned by AI populate) and live
  // in row.attributes.service_types. Options + filtering are pure helpers (tested
  // in hrVendorServiceTypes.test.ts).
  const [serviceTypeFilter, setServiceTypeFilter] = useState<string>('');

  const serviceTypeOptionList = useMemo(() => serviceTypeOptions(masters), [masters]);

  // Reset the filter when the scope changes, so a stale tag never hides the list.
  useEffect(() => {
    setServiceTypeFilter('');
  }, [category, selectedDestinationKey]);

  const visibleMasters = useMemo(
    () => filterByServiceType(masters, serviceTypeFilter),
    [masters, serviceTypeFilter],
  );

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
          `${row.destination_city}, ${getCountryName(row.destination_country) || row.destination_country} isn't on your allowlist yet — ` +
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

  const inner = (
    <>
      {/* AIQ-1576: first-visit orientation for HR — what this page is for and how to use it. */}
      {!instructionsDismissed && (
        <Card padding="lg" className="mb-6 border border-accent-200 bg-accent-50">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-navy-800">
                Choose the vendors your employees can use
              </h2>
              <p className="text-sm text-slate-600 mt-1 max-w-2xl">
                Pick a destination and a service category, then review the vendor list below and
                tick the ones you approve. Employees only ever see vendors you have approved here.
                Use “Find vendors with AI” to add real, review-verified vendors for a destination.
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Button onClick={scrollToMasterCard}>Start reviewing</Button>
              <Button variant="outline" onClick={dismissInstructions}>
                Got it
              </Button>
            </div>
          </div>
        </Card>
      )}

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
                    ? `${row.destination_city}, ${getCountryName(row.destination_country) || row.destination_country}`
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
        <h2 className="text-lg font-semibold text-[#0b2b43] mb-3">1. Find providers</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <label className="block">
            <span className="text-sm font-medium text-[#0b2b43]">Country</span>
            <select
              aria-label="Destination country"
              className="mt-1 w-full rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43]"
              value={selectedCountry}
              onChange={(e) => onPickCountry(e.target.value)}
              disabled={destinationsLoading}
            >
              <option value="">Select a country…</option>
              {countryOptions.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
              <option value={REQUEST_NEW_VALUE}>+ Request a new destination…</option>
            </select>
            <p className="mt-1 text-xs text-slate-500">
              HR can pick from supported destinations only. New destinations need admin approval.
            </p>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-[#0b2b43]">City</span>
            <select
              aria-label="Destination city"
              className="mt-1 w-full rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43] disabled:bg-[#f1f5f9] disabled:text-slate-500"
              value={selectedDestinationKey}
              onChange={(e) => onPickDestination(e.target.value)}
              disabled={destinationsLoading || !selectedCountry}
            >
              <option value="">
                {selectedCountry ? 'Select a city…' : 'Select a country first'}
              </option>
              {citiesForCountry.map((d) => (
                <option key={destinationKey(d)} value={destinationKey(d)}>
                  {d.city}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-[#0b2b43]">Service category</span>
            <select
              aria-label="Service category"
              className="mt-1 w-full rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43]"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="">Select a service type…</option>
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
                  : `Find real, review-verified vendors across every service category for ${city}, ${country}`
              }
            >
              {populating
                ? (populateProgress
                    ? `Finding ${populateProgress.label} vendors… (${populateProgress.done + 1}/${populateProgress.total})`
                    : 'Asking the AI…')
                : 'Find vendors with AI'}
            </Button>
            <Button onClick={() => void load()} disabled={loading} variant="outline">
              {loading ? 'Loading…' : 'Reload'}
            </Button>
          </div>
        </div>
        {quota && (
          <p className="mt-3 flex items-start gap-1.5 text-xs text-[#64748b]">
            <Info
              className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-500"
              aria-hidden="true"
            />
            <span
              title={
                'Each AI catalog search spends 1 quota unit to find real, review-verified '
                + 'vendors for one service category in your selected destination. Those vendors '
                + 'appear in the Admin master-vendors list below, where you tick the ones to show '
                + 'your employees. Already-populated categories are reused and cost nothing. '
                + 'Quota resets daily at midnight UTC.'
              }
            >
              AI catalog searches used today:{' '}
              <strong className="text-[#0b2b43]">{quota.used} / {quota.limit}</strong>{' '}
              ({quota.remaining} left). Each search adds real vendors for one service category
              to your list below — hover the ⓘ for details.
            </span>
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
              // AIQ-1873: 0 inserted does NOT mean "already has master vendors for
              // every category" — it can also mean quota-blocked or nothing found.
              // Claiming full coverage here contradicted section 2 showing 0 masters
              // for the selected category. Report what actually happened instead.
              <>
                No new vendors were added for {city}, {country}
                {(populateResult.categories_skipped_existing || 0) > 0 && (
                  <>
                    {' '}— {populateResult.categories_skipped_existing} categor
                    {populateResult.categories_skipped_existing === 1 ? 'y' : 'ies'} already had vendors
                  </>
                )}
                {(populateResult.categories_quota_blocked || 0) > 0 && (
                  <>
                    {(populateResult.categories_skipped_existing || 0) > 0 ? ';' : ' —'}{' '}
                    {populateResult.categories_quota_blocked} hit your daily quota (try again tomorrow, UTC)
                  </>
                )}
                . Pick a category below to review the available vendors.
              </>
            )}
          </Alert>
        )}
        {pendingTicket && (
          <Alert variant="info" className="mt-3">
            Request sent for {pendingTicket.city}, {pendingTicket.country} — the ReloPass team has
            been emailed and will source providers for this destination.
          </Alert>
        )}
      </Card>

      {requestModalOpen && (
        // eslint-disable-next-line local/no-clickable-div, jsx-a11y/no-noninteractive-element-interactions -- role="dialog" is the correct ARIA role; backdrop-click + Escape are the standard dismiss interactions
        <div
          role="dialog"
          aria-modal="true"
          tabIndex={-1}
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#0b2b43]/40 px-4"
          onClick={(e) => {
            if (e.target === e.currentTarget && !requesting) setRequestModalOpen(false);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape' && !requesting) setRequestModalOpen(false);
          }}
        >
          <Card padding="lg" className="w-full max-w-md bg-white">
            <h3 className="text-lg font-semibold text-[#0b2b43]">Request a new destination</h3>
            <p className="mt-2 text-sm text-[#4b5563]">
              Tell us where your employee is moving. We will email the ReloPass team to
              source and approve providers for this destination — once approved you can
              populate every service category with one click.
            </p>
            {/* Pass `label` to the picker rather than wrapping it in a bare <label>.
                A <label> around a custom component associates with nothing: the control it
                wraps is several layers down, so a screen reader announces no name and
                getByLabelText cannot find it — which is why jsx-a11y/label-has-associated-control
                errors here. Combobox already renders the visible label AND forwards
                `aria-label` to its Input (see the note in Combobox.tsx), so this is a real
                association, not a lint silencer. */}
            <div className="mt-4">
              <CityPicker
                value={newCity}
                onChange={setNewCity}
                country={newCountry}
                label="City"
                disabled={requesting}
                testId="request-destination-city"
                placeholder={newCountry ? 'Select or type a city…' : 'Pick a country first'}
              />
            </div>
            <div className="mt-3">
              <CountryPicker
                value={newCountry}
                onChange={setNewCountry}
                label="Country"
                disabled={requesting}
                testId="request-destination-country"
              />
            </div>
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

      {/* AIQ-1444 pt3: the Admin master-vendors section only appears once HR has
          picked a service type — otherwise a placeholder prompts the selection. */}
      {!category ? (
        <Card padding="lg" className="mb-6">
          <p className="text-sm text-[#4b5563]">
            Select a service type above to view and curate the available vendors.
          </p>
        </Card>
      ) : (
      <Card
        padding="lg"
        className={`mb-6 transition-shadow ${
          flashMaster ? 'ring-4 ring-[#fde68a] ring-offset-2' : ''
        }`}
      >
        <div ref={masterCardRef} className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div>
            <h2 className="text-lg font-semibold text-[#0b2b43]">2. Approve providers for employees</h2>
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
                  Use <strong>Find vendors with AI</strong> at the top of the page to add
                  real vendors across every category in one click, or add your own preferred
                  vendors below.
                </>
              ) : (
                <>Pick a destination at the top to begin, or add your own preferred vendors below.</>
              )}
            </p>
            {city && country && (
              <div className="mt-3">
                <Button onClick={() => void handleFetchVendors()} disabled={isDiscovering}>
                  {isDiscovering ? 'Searching…' : `Find verified vendors in ${city}`}
                </Button>
                <p className="mt-1.5 text-xs text-[#6b7280]">
                  Pulls the top-rated, review-verified vendors for this service in {city}.
                </p>
                {discoverError && <p className="mt-2 text-sm text-[#b91c1c]">{discoverError}</p>}
                {/* Seg 3: gap request — no providers here, ask the ReloPass team to source them. */}
                <div className="mt-4 border-t border-[#e2e8f0] pt-3">
                  <p className="text-sm text-[#4b5563]">
                    Still nothing suitable? Ask the ReloPass team to source vetted providers for
                    this destination.
                  </p>
                  <Button
                    variant="outline"
                    className="mt-2"
                    onClick={() => {
                      setNewCity(city);
                      setNewCountry(country);
                      setRequestModalOpen(true);
                    }}
                  >
                    Request the ReloPass team to source providers
                  </Button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <>
            {serviceTypeOptionList.length > 0 && (
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <label htmlFor="vendor-service-type" className="text-sm font-medium text-[#0b2b43]">
                  Service type
                </label>
                <select
                  id="vendor-service-type"
                  value={serviceTypeFilter}
                  onChange={(e) => setServiceTypeFilter(e.target.value)}
                  className="rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43]"
                >
                  <option value="">All service types</option>
                  {serviceTypeOptionList.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
                {serviceTypeFilter && (
                  <span className="text-xs text-[#6b7280]">
                    Showing {visibleMasters.length} of {masters.length}
                  </span>
                )}
              </div>
            )}
            {visibleMasters.length === 0 ? (
              <p className="py-2 text-sm text-[#4b5563]">
                No master vendors match “{serviceTypeFilter}”.{' '}
                <Button unstyled type="button" onClick={() => setServiceTypeFilter('')} className="underline text-[#0b2b43]">
                  Clear filter
                </Button>
              </p>
            ) : (
            <ul className="divide-y divide-[#e2e8f0] border border-[#e2e8f0] rounded-lg overflow-hidden bg-white">
            {visibleMasters.map((row) => {
              const selected = effectiveSelected(row);
              const pending = row.master_item_id ? pendingToggles.has(row.master_item_id) : false;
              const attrs = (row.attributes || {}) as Record<string, unknown>;
              const rating = typeof attrs.rating === 'number' ? attrs.rating : null;
              const reviews = typeof attrs.review_count === 'number' ? attrs.review_count : null;
              const accreditation = Array.isArray(attrs.accreditation_tags)
                ? (attrs.accreditation_tags as unknown[]).filter((t): t is string => typeof t === 'string')
                : [];
              return (
                <li key={row.master_item_id || row.name} className="p-3 flex items-center justify-between gap-3">
                  <label className="flex items-center gap-3 min-w-0 cursor-pointer">
                    <Checkbox
                      checked={selected}
                      onChange={() => row.master_item_id && togglePending(row.master_item_id, row.selected)}
                      className="h-4 w-4 shrink-0"
                    />
                    <span className="min-w-0">
                      <span className="font-medium text-[#0b2b43]">{row.name}</span>
                      {rating != null && (
                        <span className="ml-2 text-xs text-[#6b7280]">
                          ★ {rating.toFixed(1)}{reviews != null && ` (${reviews})`}
                        </span>
                      )}
                      {accreditation.map((tag) => (
                        <span
                          key={tag}
                          className="ml-1 inline-flex items-center rounded bg-[#eaf5f4] px-1.5 py-0.5 text-[10px] font-semibold text-[#105d5b]"
                        >
                          {tag}
                        </span>
                      ))}
                      {row.verified ? (
                        <span
                          className="ml-2 inline-flex items-center rounded-full bg-[#eaf5f4] px-2 py-0.5 text-[11px] font-semibold text-[#105d5b]"
                          title="ReloPass has confirmed this provider's accreditation."
                        >
                          Verified
                        </span>
                      ) : (
                        // Flagged, never hidden: an unverified provider stays selectable, but HR
                        // must be able to see that nobody has checked its accreditation yet.
                        <span
                          className="ml-2 inline-flex items-center rounded-full border border-[#fde68a] bg-[#fef9c3] px-2 py-0.5 text-[11px] font-medium text-[#854d0e]"
                          title="Pending ReloPass verification — confirm accreditation before relying on this provider."
                        >
                          Pending verification
                        </span>
                      )}
                      {row.source === 'hr_promoted' && (
                        <span className="ml-2 text-xs text-slate-500">Added by your team</span>
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
          </>
        )}
      </Card>
      )}

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

      {/* AIQ-1602 Seg 4: propose a supplier to the shared ReloPass catalog. */}
      <HrPreferredSupplierCard />
    </>
  );

  return embedded ? (
    inner
  ) : (
    <AppShell
      section="HR Operations"
      title="Service providers"
      subtitle="Choose which providers your employees see, and add your own, per service and destination."
    >
      {inner}
    </AppShell>
  );
};
