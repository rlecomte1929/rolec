import { benefitKeyForProviderService, humanizeServiceKey } from './providerServiceBenefitMap';

export interface QuoteCapRowModel {
  key: string;
  label: string;
  amount: number;
  currency: string;
  /** When null, show HR “no cap” copy (unmapped service → extend providerServiceBenefitMap). */
  benefit_key: string | null;
}

/**
 * Either a per-item attribution we can stand behind, or an explicit refusal to attribute.
 *
 * HR is signing a payment off this comparison. If we cannot map the quote onto the RFQ items,
 * the honest answer is "we can't compare these, and here's why" — not a confident number we
 * invented. (Previously a multi-item quote whose line count didn't match simply had its total
 * divided evenly across the items, which made a reduced-scope quote look identical to a
 * full-scope one — exactly the scope gap HR most needs to see.)
 */
export type QuoteCapAttribution =
  | { comparable: true; rows: QuoteCapRowModel[] }
  | { comparable: false; reason: string };

/**
 * One display/compare row per RFQ item with an attributed amount (for HR cap UI only).
 *
 * Attribution is only possible in two cases:
 *   1. The RFQ has a single item — the whole total belongs to it, unambiguously.
 *   2. The supplier sent one quote line per RFQ item — that is the supplier's OWN breakdown,
 *      so we use it rather than inventing one.
 * Anything else is not attributable, and we say so.
 */
export function buildQuoteCapAttribution(
  quote: {
    total_amount: number;
    currency: string;
    quote_lines?: Array<{ label: string; amount: number }>;
  },
  items: Array<{ service_key: string }>
): QuoteCapAttribution {
  const lines = quote.quote_lines ?? [];

  if (!items.length) {
    return { comparable: false, reason: 'This request has no line items to compare against.' };
  }
  if (!Number.isFinite(quote.total_amount)) {
    return { comparable: false, reason: 'This quote has no total, so it cannot be compared to a cap.' };
  }

  const perItemAmount = (i: number): number => {
    if (items.length === 1) return quote.total_amount;
    return lines[i]!.amount;
  };

  // Multi-item quote with no matching per-item breakdown → refuse to attribute.
  if (items.length > 1 && lines.length !== items.length) {
    return {
      comparable: false,
      reason:
        lines.length === 0
          ? `This quote gives a single total for ${items.length} requested services, with no breakdown. We can't tell how much covers each one, so it can't be compared to the caps — ask the supplier to itemise it.`
          : `This quote has ${lines.length} line item${lines.length === 1 ? '' : 's'} for ${items.length} requested services. We can't tell which service each line covers, so it can't be compared to the caps — the scope may not match what was asked for.`,
    };
  }

  const rows = items.map((it, i) => {
    const sk = it.service_key;
    const useSupplierLine = items.length > 1;
    const lineHint = useSupplierLine && lines[i] ? ` · ${lines[i].label}` : '';
    return {
      key: `${sk}-${i}`,
      label: `${humanizeServiceKey(sk)}${lineHint}`,
      amount: perItemAmount(i),
      currency: quote.currency,
      benefit_key: benefitKeyForProviderService(sk),
    };
  });

  return { comparable: true, rows };
}

/** Lines to send as `estimates` to caps/compare (subset with benefit_key). */
export function quoteRowsToCompareEstimates(rows: QuoteCapRowModel[]) {
  return rows
    .filter((r) => r.benefit_key)
    .map((r) => ({
      benefit_key: r.benefit_key!,
      amount: r.amount,
      currency: r.currency,
    }));
}
