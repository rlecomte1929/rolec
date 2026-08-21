/**
 * CaseVendorsPanel — T11 (MVP-7)
 *
 * Shows the vendor shortlist for a given case: supplier name, service
 * category, engagement status badge, and primary contact.
 *
 * Data source: GET /api/hr/cases/:caseId/vendors
 * Fails silently (renders nothing) if the fetch errors or returns an
 * empty list — keeps the HR page clean for cases with no vendors assigned.
 */
import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiGet, hrAPI, CASE_VENDOR_STATUSES } from '../../api/client';
import type { CaseVendorRow, CaseVendorStatus } from '../../api/client';

// ── Types ─────────────────────────────────────────────────────────────────────

// The row contract lives in api/client.ts (AIQ-1896) — the assign endpoint returns
// the same shape, so both producers share one definition.
type VendorRow = CaseVendorRow;

// ── Helpers ───────────────────────────────────────────────────────────────────

const CATEGORY_LABELS: Record<string, string> = {
  immigration:       'Immigration',
  housing:           'Housing',
  moving:            'Moving & Freight',
  tax:               'Tax Advisory',
  banking:           'Banking setup',
  school:            'School search',
  destination:       'Destination services',
};

function categoryLabel(raw: string | null): string {
  if (!raw) return '—';
  return CATEGORY_LABELS[raw.toLowerCase()] ?? raw.replace(/_/g, ' ');
}

const STATUS_STYLES: Record<string, string> = {
  Assigned:    'bg-[#e0f2fe] text-[#0369a1]',
  Briefed:     'bg-[#fef9c3] text-[#854d0e]',
  'In Progress': 'bg-[#e0e7ff] text-[#3730a3]',
  Complete:    'bg-[#dcfce7] text-[#166534]',
};

function statusBadge(status: string) {
  const cls = STATUS_STYLES[status] ?? 'bg-[#f1f5f9] text-[#475569]';
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

interface CaseVendorsPanelProps {
  caseId: string;
}

export const CaseVendorsPanel: React.FC<CaseVendorsPanelProps> = ({ caseId }) => {
  const vendorsQuery = useQuery({
    queryKey: ['case', caseId, 'vendors'],
    queryFn: () => apiGet<VendorRow[]>(`/api/cases/${caseId}/vendors`),
    enabled: !!caseId,
  });
  // Fail silently (errors → []) — preserve the original soft-fail behaviour.
  const vendors: VendorRow[] = vendorsQuery.data ?? [];
  const loading = vendorsQuery.isLoading;

  // [AIQ-2025] The column and its CHECK constraint always supported four states and
  // this panel already rendered a badge for each — but nothing could set them, so
  // three of the four were unreachable and every real row read "Assigned" forever.
  const queryClient = useQueryClient();
  const statusMutation = useMutation({
    mutationFn: ({ shortlistId, status }: { shortlistId: string; status: CaseVendorStatus }) =>
      hrAPI.updateCaseVendorStatus(caseId, shortlistId, status),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['case', caseId, 'vendors'] });
    },
  });

  if (loading || vendors.length === 0) return null;

  return (
    <div className="rounded-lg border border-[#e2e8f0] bg-white overflow-hidden">
      <div className="px-4 py-3 border-b border-[#f1f5f9] flex items-center gap-2">
        <span className="text-base">🏢</span>
        <h3 className="text-sm font-semibold text-[#0b2b43]">Assigned suppliers</h3>
        <span className="ml-auto text-xs text-[#94a3b8]">{vendors.length} vendor{vendors.length !== 1 ? 's' : ''}</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[#f8fafc] border-b border-[#f1f5f9]">
              <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-[#64748b]">
                Supplier
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-[#64748b]">
                Category
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-[#64748b]">
                Status
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-[#64748b]">
                Contact
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#f1f5f9]">
            {vendors.map((v, i) => (
              <tr key={v.shortlist_id ?? i} className="hover:bg-[#f8fafc] transition-colors">
                <td className="px-4 py-3 font-medium text-[#0f172a]">
                  {v.vendor_website ? (
                    <a
                      href={v.vendor_website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[#1d4ed8] hover:underline"
                    >
                      {v.vendor_name ?? '—'}
                    </a>
                  ) : (
                    v.vendor_name ?? '—'
                  )}
                </td>
                <td className="px-4 py-3 text-[#475569]">{categoryLabel(v.category)}</td>
                <td className="px-4 py-3">
                  {v.shortlist_id ? (
                    <select
                      aria-label={`Engagement status for ${v.vendor_name ?? 'vendor'}`}
                      value={v.status}
                      disabled={statusMutation.isPending}
                      onChange={(e) =>
                        statusMutation.mutate({
                          shortlistId: v.shortlist_id as string,
                          status: e.target.value as CaseVendorStatus,
                        })
                      }
                      className="rounded-lg border border-[#e2e8f0] bg-white px-2 py-1 text-xs text-[#475569] focus:outline-none focus:ring-2 focus:ring-[#1f8e8b]"
                    >
                      {CASE_VENDOR_STATUSES.map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  ) : (
                    statusBadge(v.status)
                  )}
                </td>
                <td className="px-4 py-3 text-[#475569]">
                  {v.contact_name ? (
                    <div>
                      <div className="text-[#0f172a]">{v.contact_name}</div>
                      {v.contact_email && (
                        <a
                          href={`mailto:${v.contact_email}`}
                          className="text-xs text-[#1d4ed8] hover:underline"
                        >
                          {v.contact_email}
                        </a>
                      )}
                    </div>
                  ) : (
                    <span className="text-[#94a3b8] text-xs italic">Not assigned</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
