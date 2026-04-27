/**
 * HR Vendor Curation page (Phase 2e).
 *
 * Per (category, destination_city), HR sees the admin master vendors with
 * an on/off checkbox, plus their own custom vendors. They save in bulk;
 * employees see only what HR has marked selected. The page is the
 * implementation of the middle tier from
 * docs/RECOMMENDATIONS_CATALOG_ROUTINE.md.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AppShell } from '../components/AppShell';
import { Alert, Button, Card } from '../components/antigravity';
import {
  addCustomVendor,
  bulkSelect,
  deleteCustomVendor,
  getCurationView,
  type CurationRow,
} from '../api/hrCatalog';

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

export const HrVendorCuration: React.FC = () => {
  const [category, setCategory] = useState<string>('schools');
  const [city, setCity] = useState<string>('Munich');
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

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getCurationView(category, city || null);
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

  return (
    <AppShell
      title="Vendor curation"
      subtitle="Choose which providers your employees see, per service and destination."
    >
      <Card padding="lg" className="mb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
          <label className="block">
            <span className="text-sm font-medium text-[#0b2b43]">Destination city</span>
            <input
              type="text"
              className="mt-1 w-full rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43]"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="e.g. Munich"
            />
          </label>
          <div className="flex items-end">
            <Button onClick={() => void load()} disabled={loading} variant="outline">
              {loading ? 'Loading…' : 'Reload'}
            </Button>
          </div>
        </div>
      </Card>

      {error && <Alert variant="error" className="mb-4">{error}</Alert>}
      {info && <Alert variant="success" className="mb-4">{info}</Alert>}

      <Card padding="lg" className="mb-6">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div>
            <h2 className="text-lg font-semibold text-[#0b2b43]">Admin master vendors</h2>
            <p className="text-sm text-[#6b7280] mt-1">
              {masters.length} item{masters.length === 1 ? '' : 's'} for {category} in {city || '—'}.
              Untick to hide from your employees.
            </p>
          </div>
          <Button onClick={() => void saveSelections()} disabled={!dirty || saving}>
            {saving ? 'Saving…' : dirty ? `Save ${pendingToggles.size} change${pendingToggles.size === 1 ? '' : 's'}` : 'No changes to save'}
          </Button>
        </div>
        {masters.length === 0 ? (
          <p className="text-sm text-[#6b7280] py-4">
            No master vendors yet for this category × city. Phase 2c scrapers will populate this
            when they ship; for now you can add custom vendors below.
          </p>
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
          <input
            type="text"
            placeholder="Vendor name (e.g. ABC Movers Munich)"
            value={customName}
            onChange={(e) => setCustomName(e.target.value)}
            className="rounded-lg border border-[#cbd5e1] bg-white px-3 py-2 text-sm text-[#0b2b43]"
          />
          <input
            type="text"
            placeholder="Notes for the employee (optional)"
            value={customNotes}
            onChange={(e) => setCustomNotes(e.target.value)}
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
