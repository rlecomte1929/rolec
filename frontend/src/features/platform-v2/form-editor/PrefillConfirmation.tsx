/**
 * PrefillConfirmation — P2-03c.
 *
 * A blocking confirmation gate shown when an employee opens a form that the
 * pre-fill engine (P2-03b, `filled_by='system'`) has populated. It lists every
 * pre-filled value with its source ("From your intake: …") and a confidence
 * indicator, plus any required fields they'll need to complete manually.
 *
 * It is intentionally impossible to skip: there is no close button, no Escape
 * handler, no backdrop dismissal — the only action is "Confirm and continue".
 * Confirming re-saves the values (the caller persists them), so no form data is
 * committed without explicit user action.
 */
import React from 'react';

import { Badge, Button, Card } from '../../../components/antigravity';
import type { FieldValueItem } from '../../../api/formEditor';

interface PrefillConfirmationProps {
  /** Fields the pre-fill engine populated (filled_by='system', with a value). */
  prefilledFields: FieldValueItem[];
  /** Required fields with no pre-filled value — surfaced as "complete manually". */
  manualFields: FieldValueItem[];
  /** Called when the user explicitly confirms. The caller persists + dismisses. */
  onConfirm: () => void;
  /** True while the confirm action is in flight. */
  confirming?: boolean;
}

/** HIGH for a direct/high-confidence mapping, LOW for a derived one. */
function confidenceTier(aiConfidence: number | null): 'HIGH' | 'LOW' | null {
  if (aiConfidence == null) return null;
  return aiConfidence >= 0.8 ? 'HIGH' : 'LOW';
}

export const PrefillConfirmation: React.FC<PrefillConfirmationProps> = ({
  prefilledFields,
  manualFields,
  onConfirm,
  confirming = false,
}) => {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="prefill-confirmation-title"
    >
      <Card padding="lg" className="w-full max-w-lg max-h-[85vh] overflow-y-auto">
        <h2
          id="prefill-confirmation-title"
          className="text-lg font-semibold text-[#0b2b43] mb-1"
        >
          Review your pre-filled details
        </h2>
        <p className="text-sm text-[#4b5563] mb-4">
          We filled in some fields from your intake to save you time. Please review
          them — nothing is saved until you confirm.
        </p>

        <ul className="space-y-2 mb-4">
          {prefilledFields.map((field) => {
            const tier = confidenceTier(field.ai_confidence);
            return (
              <li
                key={field.field_id}
                className="flex items-start justify-between gap-3 rounded-md border border-[#e5e7eb] bg-[#f9fafb] px-3 py-2"
                data-testid="prefill-row"
              >
                <span className="text-sm text-[#374151]">
                  <span className="text-[#6b7280]">From your intake: </span>
                  <span className="font-medium">{field.label}</span>
                  {' = '}
                  <span className="font-medium">{field.value}</span>
                </span>
                {tier && (
                  <Badge variant={tier === 'HIGH' ? 'success' : 'warning'} size="sm">
                    {tier === 'HIGH' ? 'High confidence' : 'Please verify'}
                  </Badge>
                )}
              </li>
            );
          })}
        </ul>

        {manualFields.length > 0 && (
          <div className="mb-4">
            <p className="text-xs font-semibold tracking-wide text-[#6b7280] uppercase mb-1">
              Please complete manually
            </p>
            <ul className="space-y-1">
              {manualFields.map((field) => (
                <li
                  key={field.field_id}
                  className="text-sm text-[#374151]"
                  data-testid="manual-row"
                >
                  • {field.label}
                </li>
              ))}
            </ul>
          </div>
        )}

        <Button onClick={onConfirm} disabled={confirming} className="w-full">
          {confirming ? 'Saving…' : 'Confirm and continue'}
        </Button>
      </Card>
    </div>
  );
};

export default PrefillConfirmation;
