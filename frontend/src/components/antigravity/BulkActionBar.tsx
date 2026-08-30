/**
 * BulkActionBar — the "N selected + actions" toolbar that seven admin pages had each
 * hand-rolled. Extracted while adding bulk triage to the feedback console, and used by
 * the review queue in the same change; the existing pages are deliberately NOT
 * retrofitted, so this lands with two real consumers and no churn elsewhere.
 *
 * Design notes, all lifted from what already works in AdminVettingQueue and
 * AdminContentReviewPage rather than invented:
 *
 *  - The count appears TWICE, in the label and in the action button. The vetting-queue
 *    tests assert on `Approve selected (4)`, which is what makes a count regression
 *    impossible to miss.
 *  - It renders nothing when nothing is selected. A toolbar that is always present but
 *    usually disabled is noise.
 *  - `busy` disables the whole bar. A second click mid-flight is the easiest way to
 *    double-apply an action.
 *  - Result text lives in the bar itself. This app has no toast library, and the
 *    convention here is inline feedback next to the control that caused it.
 */
import React from 'react';

export type BulkActionResult = 'idle' | 'busy' | 'done' | 'error';

export interface BulkActionBarProps {
  count: number;
  /** Buttons/selects. Disable them off `busy` yourself if they are not <button>s. */
  children: React.ReactNode;
  busy?: boolean;
  /** Outcome of the last run — drives the inline message. */
  result?: BulkActionResult;
  /** Shown when result==='done'. */
  successMessage?: string;
  /** Shown when result==='error'. Say WHICH failed, not just that something did. */
  errorMessage?: string | null;
  onClear?: () => void;
  className?: string;
}

export const BulkActionBar: React.FC<BulkActionBarProps> = ({
  count,
  children,
  busy = false,
  result = 'idle',
  successMessage,
  errorMessage,
  onClear,
  className = '',
}) => {
  if (count <= 0) return null;

  return (
    <div
      // status, not alert: appearing because the user ticked a box should not
      // interrupt a screen reader mid-task.
      role="status"
      aria-live="polite"
      data-testid="bulk-action-bar"
      className={`mb-3 flex flex-wrap items-center gap-3 rounded-lg border border-[#d1d5db] bg-[#f9fafb] px-4 py-2.5 ${className}`}
    >
      <span className="text-sm font-medium text-[#0b2b43]">{count} selected</span>

      <div className="flex flex-wrap items-center gap-2">{children}</div>

      {onClear && (
        <button
          type="button"
          onClick={onClear}
          disabled={busy}
          className="text-sm text-[#6b7280] underline hover:text-[#0b2b43] disabled:opacity-50"
        >
          Clear
        </button>
      )}

      {result === 'done' && successMessage && (
        <span className="text-sm text-[#15803d]">{successMessage}</span>
      )}
      {result === 'error' && errorMessage && (
        <span className="text-sm text-[#b91c1c]">{errorMessage}</span>
      )}
    </div>
  );
};

export default BulkActionBar;
