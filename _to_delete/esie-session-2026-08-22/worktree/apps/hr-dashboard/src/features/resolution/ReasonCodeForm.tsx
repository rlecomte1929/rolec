import { cn } from '../../lib/utils';
import {
  REASON_CODES,
  REASON_CODE_DESCRIPTIONS,
  REASON_CODE_LABELS,
  reasonRequiresFreetext,
  type ReasonCode,
} from './reasonCodes';

interface ReasonCodeFormProps {
  reasonCode: ReasonCode | '';
  reasonFreetext: string;
  onChangeReasonCode: (next: ReasonCode | '') => void;
  onChangeReasonFreetext: (next: string) => void;
  /** Disable inputs while the resolve mutation is in flight. */
  disabled?: boolean;
  /** Surface validation error to the form-level submit button. */
  errorMessage?: string;
}

const FREETEXT_MAX = 500;

/**
 * Reason-code dropdown + conditional free-text field.
 *
 * - Dropdown enumerates the 6 P0-06 codes verbatim.
 * - When `reason_code === 'OTHER'`, the free-text field is required and
 *   becomes the only way to submit. The parent form treats an empty
 *   free-text as a validation failure (see ContradictionPanel).
 */
export function ReasonCodeForm({
  reasonCode,
  reasonFreetext,
  onChangeReasonCode,
  onChangeReasonFreetext,
  disabled,
  errorMessage,
}: ReasonCodeFormProps): JSX.Element {
  const requiresFreetext = reasonRequiresFreetext(reasonCode);
  // [AIQ-945] Per-reason guidance on hover. A native <select> can't carry a tooltip
  // per <option>, so we surface all six reasons + descriptions in one `?` affordance
  // (the selected reason's description still renders inline below the dropdown).
  const reasonHelp = REASON_CODES.map(
    (code) => `${REASON_CODE_LABELS[code]}: ${REASON_CODE_DESCRIPTIONS[code]}`,
  ).join('\n');
  const labelId = 'resolution-reason-label';
  const dropdownId = 'resolution-reason-code';
  const freetextId = 'resolution-reason-freetext';
  const helpId = 'resolution-reason-help';

  return (
    <fieldset className="flex flex-col gap-3" aria-describedby={errorMessage ? helpId : undefined}>
      <legend id={labelId} className="text-sm font-semibold text-foreground">
        Reason for choice (required)
      </legend>

      <div className="flex flex-col gap-1">
        <label
          htmlFor={dropdownId}
          className="flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-muted-foreground"
        >
          Reason code
          <span
            role="img"
            aria-label="What each reason code means"
            title={reasonHelp}
            className="cursor-help rounded-full border border-border px-1 text-[10px] leading-none text-muted-foreground"
          >
            ?
          </span>
        </label>
        <select
          id={dropdownId}
          value={reasonCode}
          onChange={(event) => onChangeReasonCode(event.target.value as ReasonCode | '')}
          disabled={disabled}
          required
          className={cn(
            'rounded-md border border-border bg-background px-3 py-2 text-sm',
            'focus:outline-none focus-visible:shadow-focus',
            disabled && 'cursor-not-allowed opacity-60',
          )}
        >
          <option value="" disabled>
            Select a reason…
          </option>
          {REASON_CODES.map((code) => (
            <option key={code} value={code}>
              {REASON_CODE_LABELS[code]}
            </option>
          ))}
        </select>
        {reasonCode ? (
          <p className="text-xs text-muted-foreground">
            {REASON_CODE_DESCRIPTIONS[reasonCode]}
          </p>
        ) : null}
      </div>

      {requiresFreetext ? (
        <div className="flex flex-col gap-1">
          <label
            htmlFor={freetextId}
            className="text-xs font-medium uppercase tracking-wide text-muted-foreground"
          >
            Explanation (required)
          </label>
          <textarea
            id={freetextId}
            value={reasonFreetext}
            onChange={(event) =>
              onChangeReasonFreetext(event.target.value.slice(0, FREETEXT_MAX))
            }
            disabled={disabled}
            required
            rows={3}
            maxLength={FREETEXT_MAX}
            placeholder="Why is the chosen value correct? This is logged in the audit trail."
            className={cn(
              'rounded-md border border-border bg-background px-3 py-2 text-sm',
              'focus:outline-none focus-visible:shadow-focus',
              disabled && 'cursor-not-allowed opacity-60',
            )}
          />
          <p className="text-xs text-muted-foreground tabular-nums">
            {reasonFreetext.length} / {FREETEXT_MAX}
          </p>
        </div>
      ) : null}

      {errorMessage ? (
        <p id={helpId} role="alert" className="text-sm text-destructive">
          {errorMessage}
        </p>
      ) : null}
    </fieldset>
  );
}
