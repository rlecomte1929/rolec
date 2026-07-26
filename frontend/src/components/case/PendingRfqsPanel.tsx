/**
 * PendingRfqsPanel — HR Command Center "Pending RFQs" for a case.
 *
 * [AIQ-1681] Repointed from the retired HR-initiated `rfq_requests` model (where HR hand-typed
 * a vendor RFQ + quote amount) to the CANONICAL employee-led `rfqs` model. It now lists the
 * RFQs an employee submitted for the case (via GET /api/hr/cases/{id}/rfqs, AIQ-1669) and links
 * each to the payer surface (/quotes/rfq/:id, QuoteRfqDetail) where HR reviews and accepts the
 * real supplier quotes. HR no longer runs procurement or types amounts by hand — that path is
 * being retired (parent AIQ-1680; create removed in S2, table archived in S3).
 */

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getCaseRfqs, type CaseRfq } from '../../api/hrCoordination';

interface Props {
  /** The CANONICAL case id (`case_assignments.case_id`), never an assignment id — `rfqs`
   *  is keyed on the former. `null` when the caller could not resolve it; we then fail
   *  closed and query nothing rather than 404 on a wrong id and render that as "none". */
  caseId: string | null;
}

export const PendingRfqsPanel: React.FC<Props> = ({ caseId }) => {
  const rfqsQuery = useQuery({
    queryKey: ['case-rfqs', caseId],
    enabled: !!caseId,
    queryFn: () => getCaseRfqs(caseId as string),
  });
  // Read fails silently (errors → []) — this is a supplementary panel, not a load-bearing view.
  const rfqs: CaseRfq[] = rfqsQuery.data ?? [];
  const loading = !!caseId && rfqsQuery.isLoading;

  // Fail closed: without a canonical case id we cannot tell "no RFQs" from "wrong id",
  // so say so rather than showing a confident — and possibly false — empty state.
  if (!caseId) {
    return (
      <p className="text-sm text-[#94a3b8]">
        Quote requests can&apos;t be loaded for this case yet.
      </p>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-[#94a3b8] py-4">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#0b2b43] border-t-transparent" />
        Loading quote requests…
      </div>
    );
  }

  if (rfqs.length === 0) {
    return (
      <p className="text-sm text-[#94a3b8]">
        No quote requests yet. The employee requests quotes from their Services flow; they&apos;ll
        appear here once submitted.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {rfqs.map((rfq) => (
        <div key={rfq.id} className="rounded-xl border border-[#e2e8f0] bg-white p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-xs font-semibold text-[#0b2b43] truncate">
                  {rfq.rfq_ref ?? rfq.id}
                </span>
                {rfq.status && (
                  <span className="rounded-full px-2 py-0.5 text-xs font-medium text-[#2563eb] bg-[#eff6ff]">
                    {rfq.status}
                  </span>
                )}
              </div>
              {rfq.service_keys.length > 0 && (
                <p className="text-xs text-[#64748b] mt-1">Services: {rfq.service_keys.join(', ')}</p>
              )}
              {rfq.recipients.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {rfq.recipients.map((r, i) => (
                    <li
                      key={r.supplier_id ?? i}
                      className="text-xs text-[#374151] flex items-center justify-between gap-2"
                    >
                      <span className="truncate">{r.supplier_name ?? r.supplier_id ?? 'Provider'}</span>
                      <span className="text-[#94a3b8] shrink-0">{r.status ?? '—'}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Review / accept happens on the canonical payer surface (QuoteRfqDetail). */}
            <Link
              to={`/quotes/rfq/${rfq.id}`}
              className="shrink-0 rounded-lg border border-[#2563eb] bg-white px-3 py-1.5 text-xs font-medium text-[#2563eb] hover:bg-[#eff6ff] transition-colors whitespace-nowrap focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563eb]"
            >
              Review quotes →
            </Link>
          </div>
        </div>
      ))}
    </div>
  );
};

export default PendingRfqsPanel;
