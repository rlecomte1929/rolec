import { useEffect, useState } from 'react';
import { getOutcomeConsent, setOutcomeConsent } from '../../../api/outcomeConsent';

/**
 * P1-07c / AIQ-686 — optional per-case opt-in to anonymized outcome sharing.
 * Distinct from the mandatory Art.13 PrivacyNotice: this does NOT gate submit.
 * Self-contained (own state + hydration + POST) so the large intake page only
 * needs one line. Gracefully no-ops if the case has no assignment yet (404).
 */
export function OutcomeSharingOptIn({ caseId }: { caseId: string }) {
  const [checked, setChecked] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    getOutcomeConsent(caseId)
      .then((s) => {
        if (active && typeof s.consented === 'boolean') setChecked(s.consented);
      })
      .catch(() => {
        /* no assignment yet / not authorised — leave unchecked */
      });
    return () => {
      active = false;
    };
  }, [caseId]);

  const toggle = async (v: boolean) => {
    setChecked(v);
    setSaving(true);
    setError(false);
    try {
      await setOutcomeConsent(caseId, v);
    } catch {
      setError(true);
      setChecked(!v);
    } finally {
      setSaving(false);
    }
  };

  return (
    <label
      className="mt-3 flex items-start gap-2 text-sm text-slate-600"
      data-testid="outcome-consent-optin"
    >
      <input
        type="checkbox"
        className="mt-0.5 h-4 w-4 rounded border-gray-300 text-accent-600"
        checked={checked}
        disabled={saving}
        onChange={(e) => void toggle(e.target.checked)}
      />
      <span>
        <span className="font-medium text-slate-700">Help improve ReloPass (optional).</span>{' '}
        Share my <strong>anonymized</strong> relocation outcome — no name, contact details, or
        documents — to help improve the AI. You can withdraw this anytime.
        {error && <span className="block text-xs text-red-500">Couldn’t save — please try again.</span>}
      </span>
    </label>
  );
}
