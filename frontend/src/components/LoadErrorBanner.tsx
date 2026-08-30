/**
 * Inline banner for a FAILED READ.
 *
 * Exists because the alternative was worse than an ugly error: several admin pages caught a
 * load failure, set the list to `[]`, and rendered "No categories yet." — indistinguishable
 * from a genuinely empty taxonomy. An admin had no way to tell a broken endpoint from an
 * empty one, and the mutation paths in those same files already surfaced their errors via
 * `alert(...)`, so the read-path silence was an oversight rather than a decision.
 *
 * Markup is lifted from the one page that already did this correctly
 * (`pages/admin/AdminResources.tsx`, the counts banner) so the two look identical.
 */
interface LoadErrorBannerProps {
  /** Null renders nothing, so callers can drop this in unconditionally. */
  message: string | null;
  onRetry?: () => void;
}

export function LoadErrorBanner({ message, onRetry }: LoadErrorBannerProps) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="flex items-center justify-between rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
    >
      <span>{message}</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="ml-3 shrink-0 rounded-md border border-rose-300 px-2.5 py-1 text-xs font-medium hover:bg-rose-100"
        >
          Retry
        </button>
      )}
    </div>
  );
}

/**
 * Pull a human-readable message off an axios-shaped error, falling back to the caller's
 * copy. Mirrors the extraction already inlined in EmployeeDossierPage's loader.
 */
export function loadErrorMessage(e: unknown, fallback: string): string {
  const err = e as { response?: { data?: { detail?: string } }; message?: string };
  return err?.response?.data?.detail || err?.message || fallback;
}
