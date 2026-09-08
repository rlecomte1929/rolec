/**
 * Canonical currency list for policy-matrix money-amount rows.
 *
 * Kept intentionally short to the currencies ReloPass actually supports
 * end-to-end (display in employee UI, service cost comparison, provider
 * quotes). Extend here when a new currency has its full downstream
 * chain wired, not opportunistically per HR request.
 *
 * Values are ISO 4217 codes; labels include the symbol + region hint
 * for HR legibility.
 */
export const POLICY_CURRENCY_OPTIONS: { value: string; label: string }[] = [
  { value: 'EUR', label: 'EUR — Euro' },
  { value: 'USD', label: 'USD — US Dollar' },
  { value: 'GBP', label: 'GBP — British Pound' },
  { value: 'CHF', label: 'CHF — Swiss Franc' },
  { value: 'NOK', label: 'NOK — Norwegian Krone' },
  { value: 'SEK', label: 'SEK — Swedish Krona' },
  { value: 'DKK', label: 'DKK — Danish Krone' },
  { value: 'JPY', label: 'JPY — Japanese Yen' },
  { value: 'CNY', label: 'CNY — Chinese Yuan' },
  { value: 'HKD', label: 'HKD — Hong Kong Dollar' },
  { value: 'SGD', label: 'SGD — Singapore Dollar' },
  { value: 'AUD', label: 'AUD — Australian Dollar' },
  { value: 'CAD', label: 'CAD — Canadian Dollar' },
  { value: 'INR', label: 'INR — Indian Rupee' },
  { value: 'BRL', label: 'BRL — Brazilian Real' },
  { value: 'MXN', label: 'MXN — Mexican Peso' },
  { value: 'ZAR', label: 'ZAR — South African Rand' },
  { value: 'AED', label: 'AED — UAE Dirham' },
];

const KNOWN = new Set(POLICY_CURRENCY_OPTIONS.map((o) => o.value));

/**
 * Back-compat for legacy free-text entries (e.g. "euros", "eur", "€").
 * Unknown inputs are returned unchanged so HR can see and fix them
 * manually instead of the select silently snapping them to empty.
 */
export function normalizeCurrencyCode(raw: string | null | undefined): string {
  const s = String(raw ?? '').trim();
  if (!s) return '';
  const upper = s.toUpperCase();
  if (KNOWN.has(upper)) return upper;
  const lower = s.toLowerCase();
  if (lower === 'euros' || lower === 'euro' || lower === '€') return 'EUR';
  if (lower === 'dollars' || lower === 'dollar' || lower === '$') return 'USD';
  if (lower === 'pounds' || lower === 'pound' || lower === '£') return 'GBP';
  if (lower === 'yen' || lower === '¥') return 'JPY';
  return s;
}
