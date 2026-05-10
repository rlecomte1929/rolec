import React, { useMemo } from 'react';
import type { QuoteDetail, RfqDetail } from '../../api/client';
import { buildQuoteCapRowModels, quoteRowsToCompareEstimates } from './buildQuoteEstimatesForCapCompare';
import { PolicyCapEstimateRow } from './PolicyCapEstimateRow';
import type { PolicyCapCompareResultRow } from './policyCapCompareTypes';
import { usePolicyCapsCompare } from './usePolicyCapsCompare';

const HrSingleQuoteCapCompare: React.FC<{
  quote: QuoteDetail;
  rfqItems: Array<{ service_key: string }>;
  assignmentType?: string | null;
  familyStatus?: string | null;
}> = ({ quote, rfqItems, assignmentType, familyStatus }) => {
  const rows = useMemo(() => buildQuoteCapRowModels(quote, rfqItems), [quote, rfqItems]);
  const estimates = useMemo(() => quoteRowsToCompareEstimates(rows), [rows]);

  const { results, loading, error } = usePolicyCapsCompare({
    enabled: estimates.length > 0,
    assignmentType,
    familyStatus,
    estimates,
  });

  const paired = useMemo(() => {
    let j = 0;
    return rows.map((row) => {
      if (!row.benefit_key) {
        return { row, unmapped: true as const, result: undefined as PolicyCapCompareResultRow | null | undefined };
      }
      if (loading) {
        return { row, unmapped: false as const, result: null as PolicyCapCompareResultRow | null };
      }
      const r = results?.[j++];
      return { row, unmapped: false as const, result: (r ?? null) as PolicyCapCompareResultRow | null };
    });
  }, [rows, results, loading]);

  return (
    <div className="mt-3 space-y-2 border-t border-[#e2e8f0] pt-3">
      <div className="text-xs font-semibold text-[#0b2b43]">Policy cap comparison (HR / Admin)</div>
      {error ? <div className="text-xs text-red-600">{error}</div> : null}
      {rows.length === 0 ? (
        <p className="text-xs text-[#6b7280]">No RFQ items to compare, or quote has no total.</p>
      ) : (
        paired.map(({ row, unmapped, result }) => (
          <PolicyCapEstimateRow
            key={`${quote.id}-${row.key}`}
            title={row.label}
            subtitle={`Vendor quote · ${quote.currency}`}
            result={unmapped ? undefined : result}
            unmapped={unmapped}
            estimateAmount={row.amount}
            estimateCurrency={row.currency}
          />
        ))
      )}
    </div>
  );
};

/**
 * Read-only cap comparison for HR/Admin on RFQ quote cards. Do not render on employee-only views.
 */
export const HrRfqQuotesPolicyCapsSection: React.FC<{
  rfq: RfqDetail;
  quotes: QuoteDetail[];
  assignmentType?: string | null;
  familyStatus?: string | null;
}> = ({ rfq, quotes, assignmentType, familyStatus }) => {
  const items = rfq.items ?? [];
  if (!quotes.length || !items.length) return null;

  return (
    <div className="rounded-lg border border-dashed border-[#cbd5e1] bg-[#f8fafc] p-4">
      <div className="text-sm font-semibold text-[#0b2b43]">Budget vs vendor quotes</div>
      <p className="text-xs text-[#64748b] mt-1">
        Estimates are compared to published policy caps for this company. This view is not shown to
        employees.
      </p>
      <div className="mt-4 space-y-4">
        {quotes.map((q) => (
          <div key={q.id} className="rounded-lg border border-[#e2e8f0] bg-white p-3">
            <div className="text-xs font-medium text-[#6b7280]">
              Vendor {q.vendor_id.slice(0, 8)}… · Total {q.currency}{' '}
              {q.total_amount.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </div>
            <HrSingleQuoteCapCompare
              quote={q}
              rfqItems={items}
              assignmentType={assignmentType}
              familyStatus={familyStatus}
            />
          </div>
        ))}
      </div>
    </div>
  );
};
