/** localStorage key — must match ServicesFlowContext. */
export const SERVICES_DISPLAY_CURRENCY_STORAGE_KEY = 'services_display_currency';

/**
 * Display-only conversion from USD (backend / recommendation baseline) to the employee's chosen currency.
 * Rates are indicative planning values, not live FX.
 */
export const SERVICES_DISPLAY_CURRENCIES = [
  { code: 'USD', label: 'US Dollar (USD)' },
  { code: 'EUR', label: 'Euro (EUR)' },
  { code: 'GBP', label: 'British Pound (GBP)' },
  { code: 'CHF', label: 'Swiss Franc (CHF)' },
  { code: 'CAD', label: 'Canadian Dollar (CAD)' },
  { code: 'AUD', label: 'Australian Dollar (AUD)' },
  { code: 'NOK', label: 'Norwegian Krone (NOK)' },
  { code: 'SEK', label: 'Swedish Krona (SEK)' },
  { code: 'DKK', label: 'Danish Krone (DKK)' },
  { code: 'JPY', label: 'Japanese Yen (JPY)' },
] as const;

const USD_TO: Record<string, number> = {
  USD: 1,
  EUR: 0.92,
  GBP: 0.79,
  CHF: 0.9,
  CAD: 1.38,
  AUD: 1.54,
  NOK: 10.85,
  SEK: 10.65,
  DKK: 6.9,
  JPY: 150,
};

export function normalizeServicesCurrency(code: string | null | undefined): string {
  const c = String(code || 'USD')
    .trim()
    .toUpperCase();
  return c in USD_TO ? c : 'USD';
}

/** Convert an amount stored as USD nominal into the display currency (same basis as caps in PackageSummary). */
export function convertUsdToDisplay(usd: number, displayCurrency: string): number {
  const cur = normalizeServicesCurrency(displayCurrency);
  const mult = USD_TO[cur] ?? 1;
  return usd * mult;
}

export function formatServicesMoney(amount: number, currencyCode: string): string {
  const cur = normalizeServicesCurrency(currencyCode);
  const maxFrac = cur === 'JPY' ? 0 : 2;
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency: cur,
      maximumFractionDigits: maxFrac,
      minimumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${cur} ${amount.toLocaleString(undefined, { maximumFractionDigits: maxFrac })}`;
  }
}

export function formatEstimationFromUsd(
  usd: number | undefined | null,
  costType: 'monthly' | 'annual' | 'one_time' | undefined,
  displayCurrency: string
): string | null {
  if (usd == null || !Number.isFinite(usd)) return null;
  const amt = convertUsdToDisplay(usd, displayCurrency);
  const base = formatServicesMoney(amt, displayCurrency);
  if (costType === 'monthly') return `${base}/mo`;
  if (costType === 'annual') return `${base}/yr`;
  return base;
}

export const SERVICES_CURRENCY_FOOTNOTE =
  'Amounts are converted from USD using indicative rates for display. Final quotes may differ.';
