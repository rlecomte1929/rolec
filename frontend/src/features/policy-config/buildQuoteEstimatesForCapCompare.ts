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
 * One display/compare row per RFQ item with an attributed amount (for HR cap UI only).
 */
export function buildQuoteCapRowModels(
  quote: {
    total_amount: number;
    currency: string;
    quote_lines?: Array<{ label: string; amount: number }>;
  },
  items: Array<{ service_key: string }>
): QuoteCapRowModel[] {
  const lines = quote.quote_lines ?? [];
  if (!items.length || !Number.isFinite(quote.total_amount)) return [];

  const share = quote.total_amount / items.length;

  return items.map((it, i) => {
    const sk = it.service_key;
    const bk = benefitKeyForProviderService(sk);
    let amount = quote.total_amount;
    if (items.length > 1) {
      if (lines.length === items.length) {
        amount = lines[i]!.amount;
      } else {
        amount = share;
      }
    }
    const lineHint = lines.length === items.length && lines[i] ? ` · ${lines[i]!.label}` : '';
    return {
      key: `${sk}-${i}`,
      label: `${humanizeServiceKey(sk)}${lineHint}`,
      amount,
      currency: quote.currency,
      benefit_key: bk,
    };
  });
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
