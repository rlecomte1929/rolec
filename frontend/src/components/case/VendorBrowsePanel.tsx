/**
 * VendorBrowsePanel — AIQ-40-B
 *
 * Slide-over panel that lets HR browse the vendor directory filtered by
 * service category and corridor without leaving the case record.
 *
 * Props:
 *  - isOpen          : controls visibility
 *  - onClose         : close handler
 *  - destCountry     : pre-fills the destination part of the corridor filter
 *  - initialCategory : pre-selects a service category filter (e.g. "Immigration/visa")
 *  - immigrationContext : IMM-15 — case immigration context when opened from the
 *                         immigration panel; surfaces a hint on the panel
 *
 * AIQ-1682: the per-vendor "Request quote" action was removed — HR no longer
 * originates RFQs (RFQs are employee-led; HR is payer/approver).
 *
 * AIQ-1896: with a `caseId`, each vendor gains an "Assign to case" action — the
 * write path public.case_vendor_shortlist never had. Without one the panel stays
 * the read-only directory browser AIQ-1682 left behind.
 */

import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button } from '../antigravity/Button';
import { hrAPI } from '../../api/client';
import type { ImmigrationContext } from './immigrationContext';
import { getCountryName } from '../../utils/countries';

type Vendor = {
  id: string;
  name: string;
  service_categories: string[];
  corridors: string[];
  contact_email: string;
  description?: string;
  is_approved: boolean;
};

const SERVICE_CATEGORIES = [
  'Housing search',
  'Immigration/visa',
  'Moving & shipping',
  'School search',
  'Destination orientation',
  'Other',
];

// BUG-260706-4DE4: the dropdown shows friendly labels, but the vendors table keys on a
// coarser `category` value (e.g. "Immigration Legal"). Send the canonical category so the
// filter actually matches — otherwise real vendors (e.g. the immigration firm) never show.
// Labels without a canonical category fall through unmapped (backend also matches
// service_types), which is honest: an unmatched category simply returns no rows.
const LABEL_TO_VENDOR_CATEGORY: Record<string, string> = {
  'Housing search': 'Housing Search',
  'Immigration/visa': 'Immigration Legal',
  'Moving & shipping': 'Moving & Freight',
  'School search': 'School Search',
};

interface Props {
  isOpen: boolean;
  onClose: () => void;
  destCountry?: string;
  initialCategory?: string;
  immigrationContext?: ImmigrationContext | null;
  /** AIQ-1896 — the case to assign into. Omit for a read-only browse. */
  caseId?: string | null;
}

export const VendorBrowsePanel: React.FC<Props> = ({
  isOpen,
  onClose,
  destCountry,
  initialCategory,
  immigrationContext,
  caseId,
}) => {
  // Filters — initialCategory pre-selects service category (e.g. from immigration panel)
  const [selectedCategory, setSelectedCategory] = useState(initialCategory ?? '');
  const [selectedCorridor, setSelectedCorridor] = useState('');

  // Load corridors once on open — soft-fail to [].
  const corridorsQuery = useQuery({
    queryKey: ['vendor-corridors'],
    queryFn: async () => (await hrAPI.getVendorCorridors()).corridors ?? [],
    enabled: isOpen,
  });
  const corridors: string[] = corridorsQuery.data ?? [];

  // Load vendors whenever filters change (or panel opens)
  const vendorsQuery = useQuery({
    queryKey: ['vendors', selectedCategory, selectedCorridor],
    queryFn: async () => {
      const res = await hrAPI.getVendors({
        ...(selectedCategory
          ? { category: LABEL_TO_VENDOR_CATEGORY[selectedCategory] ?? selectedCategory }
          : {}),
        ...(selectedCorridor ? { corridor: selectedCorridor } : {}),
      });
      return res.vendors;
    },
    enabled: isOpen,
  });
  const vendors: Vendor[] = vendorsQuery.data ?? [];
  const loading = vendorsQuery.isLoading;
  const error = vendorsQuery.isError ? 'Failed to load vendors.' : '';

  // ── AIQ-1896: assign a browsed vendor to the case ───────────────────────────
  const queryClient = useQueryClient();
  const [assignError, setAssignError] = useState('');

  // [AIQ-2024] Which vendors are ALREADY on this case, read from the server rather
  // than remembered for the session. AIQ-1896 could only track clicks in local
  // state, because the row contract carried the vendor's NAME and not its id —
  // so the panel forgot every assignment on reload and offered an idle "Assign to
  // case" button for vendors already attached. The rows now carry `vendor_id`.
  const assignedQuery = useQuery({
    queryKey: ['case', caseId, 'vendors'],
    queryFn: () => hrAPI.getCaseVendors(caseId as string),
    enabled: isOpen && !!caseId,
  });
  const assignedIds = new Set(
    (assignedQuery.data ?? []).map((row) => row.vendor_id).filter(Boolean) as string[],
  );

  const assignMutation = useMutation({
    mutationFn: (vendorId: string) =>
      hrAPI.assignVendorToCase(caseId as string, { vendor_id: vendorId }),
    onSuccess: () => {
      setAssignError('');
      // Refetch the case's assigned vendors — this drives both the badge here and
      // the assigned-suppliers panel on the page behind. Fire-and-forget: awaiting
      // it would stall the badge, and the row is already committed server-side.
      void queryClient.invalidateQueries({ queryKey: ['case', caseId, 'vendors'] });
    },
    onError: () => setAssignError('Could not assign that vendor. Please try again.'),
  });
  const canAssign = Boolean(caseId);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      {/* eslint-disable-next-line local/no-clickable-div -- presentational mouse-dismiss overlay (aria-hidden); keyboard users dismiss via the panel's own controls */}
      <div
        className="fixed inset-0 bg-black/30 z-40"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        className="fixed inset-y-0 right-0 z-50 flex flex-col w-full max-w-lg bg-white shadow-2xl"
        role="dialog"
        aria-label="Find a vendor"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#e2e8f0]">
          <div>
            <h2 className="text-base font-semibold text-[#0b2b43]">Find a vendor</h2>
            <p className="text-xs text-[#64748b] mt-0.5">
              {canAssign
                ? 'Assign a vendor to this case'
                : 'Browse the approved vendor directory'}
            </p>
          </div>
          <Button unstyled
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-slate-500 hover:bg-[#f1f5f9] transition-colors"
            aria-label="Close"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </Button>
        </div>

        {/* IMM-15: immigration case context hint */}
        {immigrationContext?.visa_type && (
          <div className="px-6 py-2.5 border-b border-[#bfdbfe] bg-[#eff6ff] text-xs text-[#1d4ed8]">
            Pre-loaded from immigration case
            {immigrationContext.corridor_from && immigrationContext.corridor_to
              ? ` · ${immigrationContext.corridor_from}→${immigrationContext.corridor_to}`
              : ''}
            {' '}— filters are pre-set from that case.
          </div>
        )}

        {/* Filters */}
        <div className="px-6 py-4 border-b border-[#e2e8f0] bg-[#f8fafc] space-y-3">
          <div className="grid grid-cols-2 gap-3">
            {/* Service category */}
            <div>
              <label className="block text-xs font-medium text-[#374151] mb-1" htmlFor="vbp-category">
                Service
              </label>
              <select
                id="vbp-category"
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="w-full rounded-lg border border-[#d1d5db] bg-white px-3 py-2 text-sm text-[#374151] focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
              >
                <option value="">All services</option>
                {SERVICE_CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            {/* Corridor */}
            <div>
              <label className="block text-xs font-medium text-[#374151] mb-1" htmlFor="vbp-corridor">
                Corridor
              </label>
              <select
                id="vbp-corridor"
                value={selectedCorridor}
                onChange={(e) => setSelectedCorridor(e.target.value)}
                className="w-full rounded-lg border border-[#d1d5db] bg-white px-3 py-2 text-sm text-[#374151] focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
              >
                <option value="">All corridors</option>
                {corridors.map((c) => (
                  <option key={c} value={c}>{getCountryName(c) || c}</option>
                ))}
              </select>
              {destCountry && !selectedCorridor && (
                <p className="text-xs text-[#64748b] mt-1">
                  Destination: {getCountryName(destCountry) || destCountry}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Vendor list */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {assignError && (
            <div className="mb-3 rounded-lg border border-[#fecaca] bg-[#fef2f2] px-4 py-3 text-sm text-[#dc2626]">
              {assignError}
            </div>
          )}
          {loading && (
            <div className="flex items-center gap-2 text-sm text-[#64748b] py-8 justify-center">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#0b2b43] border-t-transparent" />
              Loading vendors…
            </div>
          )}

          {!loading && error && (
            <div className="rounded-lg border border-[#fecaca] bg-[#fef2f2] px-4 py-3 text-sm text-[#dc2626]">
              {error}
            </div>
          )}

          {!loading && !error && vendors.length === 0 && (
            <div className="py-12 text-center">
              <div className="text-4xl mb-3">🔍</div>
              <p className="text-sm font-medium text-[#374151]">No vendors found</p>
              <p className="text-xs text-slate-500 mt-1">
                Try removing a filter or{' '}
                <Button unstyled
                  type="button"
                  className="text-[#2563eb] underline"
                  onClick={() => { setSelectedCategory(''); setSelectedCorridor(''); }}
                >
                  clear all
                </Button>
              </p>
            </div>
          )}

          {!loading && !error && vendors.length > 0 && (
            <ul className="space-y-3">
              {vendors.map((vendor) => (
                <li
                  key={vendor.id}
                  className="rounded-xl border border-[#e2e8f0] bg-white p-4 hover:border-[#bfdbfe] transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-[#0b2b43] truncate">{vendor.name}</p>

                      {/* Service category chips */}
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {vendor.service_categories.map((cat) => (
                          <span
                            key={cat}
                            className="rounded-full border border-[#bfdbfe] bg-[#eff6ff] px-2 py-0.5 text-xs text-[#1d4ed8]"
                          >
                            {cat}
                          </span>
                        ))}
                      </div>

                      {/* Corridors */}
                      {vendor.corridors?.length > 0 && (
                        <p className="text-xs text-[#64748b] mt-1.5">
                          Corridors: {vendor.corridors.map((c) => getCountryName(c) || c).join(', ')}
                        </p>
                      )}

                      {/* Description */}
                      {vendor.description && (
                        <p className="text-xs text-[#374151] mt-1.5 leading-relaxed">
                          {vendor.description}
                        </p>
                      )}
                    </div>

                    {/* AIQ-1896: assign action — only with a case to assign into */}
                    {canAssign && (
                      assignedIds.has(vendor.id) ? (
                        <span className="shrink-0 inline-flex items-center gap-1 rounded-full bg-[#dcfce7] px-2.5 py-1 text-xs font-medium text-[#166534]">
                          ✓ Assigned
                        </span>
                      ) : (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="shrink-0"
                          disabled={assignMutation.isPending}
                          onClick={() => assignMutation.mutate(vendor.id)}
                        >
                          {assignMutation.isPending && assignMutation.variables === vendor.id
                            ? 'Assigning…'
                            : 'Assign to case'}
                        </Button>
                      )
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-[#e2e8f0] bg-[#f8fafc] text-xs text-slate-500">
          {vendors.length > 0 && `${vendors.length} vendor${vendors.length !== 1 ? 's' : ''} shown`}
        </div>
      </div>
    </>
  );
};

export default VendorBrowsePanel;
