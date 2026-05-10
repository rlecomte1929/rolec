const DEFAULT_LOCALE = typeof navigator !== 'undefined' ? navigator.language : 'en-US';

/**
 * Format a major-unit amount (e.g. dollars) for display. Does not convert FX.
 */
export function formatPolicyCurrency(amount: number, currencyCode: string, locale = DEFAULT_LOCALE): string {
  if (!Number.isFinite(amount)) return '—';
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: currencyCode.trim().toUpperCase(),
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${currencyCode.toUpperCase()} ${amount.toLocaleString(locale, { maximumFractionDigits: 2 })}`;
  }
}

/**
 * Format a ratio as a percentage (e.g. 0.125 → "12.5%"). Pass (part/whole) from the caller.
 */
export function formatPolicyPercentage(ratio: number, locale = DEFAULT_LOCALE, fractionDigits = 1): string {
  if (!Number.isFinite(ratio)) return '—';
  try {
    return new Intl.NumberFormat(locale, {
      style: 'percent',
      maximumFractionDigits: fractionDigits,
      minimumFractionDigits: 0,
    }).format(ratio);
  } catch {
    return `${(ratio * 100).toFixed(fractionDigits)}%`;
  }
}
