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
import React, { useCallback, useEffect, useState } from 'react';
import { apiGet } from '../../api/client';

// ── Types ─────────────────────────────────────────────────────────────────────

interface VendorRow {
  shortlist_id: string | null;
  category: string | null;
  status: string;
  contact_name: string | null;
  contact_email: string | null;
  vendor_name: string | null;
  vendor_website: string | null;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const CATEGORY_LABELS: Record<string, string> = {
  immigration:       'Immigration',
  housing:           'Housing',
  moving:            'Moving & Freight',
  tax:               'Tax Advisory',
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
  const [vendors, setVendors] = useState<VendorRow[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    if (!caseId) { setLoading(false); return; }
    apiGet<VendorRow[]>(`/api/cases/${caseId}/vendors`)
      .then(setVendors)
      .catch(() => setVendors([]))
      .finally(() => setLoading(false));
  }, [caseId]);

  useEffect(() => { load(); }, [load]);

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
                <td className="px-4 py-3">{statusBadge(v.status)}</td>
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
