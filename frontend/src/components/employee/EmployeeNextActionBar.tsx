/**
 * Sticky bottom bar for the employee relocation flow. Tells the user
 * what comes next from this surface and one-clicks them to it.
 *
 * Mounts at the bottom of any in-flow page (case summary, wizard step,
 * services pick, plan view). Mirrors the StickyContinueBar pattern used
 * in services so the visual + spacing feel consistent across the app.
 *
 * Why this component instead of inline buttons per page:
 *   - Single source of truth for "what's the right next step"
 *   - One place to evolve the copy as we learn from real users
 *   - Lets us add multi-step affordances (Back / Save draft / Next) in one
 *     place instead of every page rolling their own
 */
import React from 'react';
import { Link } from 'react-router-dom';

type Props = {
  /** Short label for what the user just finished or is on. e.g. "Step 4 of 6" */
  status?: string;
  /** Primary CTA text. Required. */
  primaryLabel: string;
  /** Where the primary CTA goes. Either a relative path or a full URL. */
  primaryHref?: string;
  /** Or a click handler if the action isn't a navigation. */
  onPrimaryClick?: () => void;
  /** Secondary "Back" or "Skip" link, optional. */
  secondaryLabel?: string;
  secondaryHref?: string;
  /** Supplementary one-liner shown above the buttons. Use for context that
   *  changes per page, e.g. "All checklist items done — your specialist
   *  will reach out next." */
  hint?: string;
  /** Disable the primary CTA (e.g. while saving). */
  disabled?: boolean;
};

export const EmployeeNextActionBar: React.FC<Props> = ({
  status,
  primaryLabel,
  primaryHref,
  onPrimaryClick,
  secondaryLabel,
  secondaryHref,
  hint,
  disabled = false,
}) => {
  const primaryClass =
    'px-5 py-2.5 rounded-lg bg-[#0b2b43] text-white text-sm font-medium ' +
    'hover:bg-[#123651] disabled:opacity-50 disabled:cursor-not-allowed transition-colors';
  return (
    <div
      className={
        // Sticky to the viewport bottom inside the scroll container, full
        // bleed via negative margins (matches StickyContinueBar pattern).
        'sticky bottom-0 left-0 right-0 z-10 mt-8 -mx-4 md:-mx-8 px-4 md:px-8 py-3 ' +
        'bg-white/95 backdrop-blur-sm border-t border-[#e2e8f0]'
      }
      role="region"
      aria-label="Next action"
    >
      {hint && (
        <p className="text-xs text-[#6b7280] mb-2 max-w-3xl">{hint}</p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-[#374151]">
          {status && <span className="font-medium">{status}</span>}
        </div>
        <div className="flex items-center gap-3">
          {secondaryLabel && secondaryHref && (
            <Link
              to={secondaryHref}
              className="text-sm text-[#6b7280] hover:text-[#0b2b43] underline"
            >
              {secondaryLabel}
            </Link>
          )}
          {primaryHref && !onPrimaryClick ? (
            <Link to={primaryHref} className={primaryClass} aria-disabled={disabled}>
              {primaryLabel}
            </Link>
          ) : (
            <button
              type="button"
              onClick={onPrimaryClick}
              disabled={disabled}
              className={primaryClass}
            >
              {primaryLabel}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
