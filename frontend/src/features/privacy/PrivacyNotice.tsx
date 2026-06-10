/**
 * PrivacyNotice — GDPR Art. 13 notice rendered at a point of data collection
 * (PRIV-005 / AIQ-473).
 *
 * Presents the controller identity, data categories, legal basis, retention,
 * rights, recipients, and complaint route *before* data is submitted — the
 * Art. 13 requirement that a footer link to a privacy page does not satisfy.
 *
 * Parent owns the `checked` acknowledgement state and blocks its own submit on
 * it. When the user checks the box, this component records the acknowledgement
 * via POST /api/privacy/consents (idempotent per notice_version) and only calls
 * onChange(true) once the write succeeds, so a recorded ack always backs a
 * checked box.
 */
import { useState } from 'react';
import { Checkbox } from '../../components/antigravity/Checkbox';
import { apiPost } from '../../api/client';
import { privacyNoticeContent } from './privacyNoticeContent';

export interface PrivacyNoticeProps {
  /** Current notice version, from PRIVACY_NOTICE_VERSION. */
  noticeVersion: string;
  /** Which collection surface is presenting the notice. */
  context: 'onboarding' | 'task_submission';
  /** Parent-owned acknowledgement state. */
  checked: boolean;
  /** Called with true after the ack is recorded, false on uncheck. */
  onChange: (checked: boolean) => void;
  /** 'inline' = embedded in a form step; 'banner' = standalone gate. */
  variant?: 'inline' | 'banner';
}

export function PrivacyNotice({
  noticeVersion,
  context,
  checked,
  onChange,
  variant = 'inline',
}: PrivacyNoticeProps) {
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleToggle = async (next: boolean) => {
    setError(null);
    if (!next) {
      onChange(false);
      return;
    }
    // Record the acknowledgement before reflecting the checked state, so a
    // ticked box is always backed by a stored consent row.
    setSaving(true);
    try {
      await apiPost('/api/privacy/consents', {
        notice_version: noticeVersion,
        context,
      });
      onChange(true);
    } catch {
      setError(
        "We couldn’t save your choice. Try again — your data hasn’t been shared yet.",
      );
    } finally {
      setSaving(false);
    }
  };

  const wrapCls =
    variant === 'banner'
      ? 'rounded-xl border border-amber-200 bg-amber-50 p-5'
      : 'rounded-xl border border-gray-100 bg-gray-50 p-5';

  return (
    <div className={wrapCls} role="region" aria-label="Privacy notice">
      <h3 className="text-sm font-semibold text-gray-900">{privacyNoticeContent.headline}</h3>
      <p className="mt-1 text-sm text-gray-600">{privacyNoticeContent.lede}</p>

      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="mt-2 text-xs font-medium text-accent-600 hover:text-accent-800"
      >
        {expanded ? 'Hide the full notice' : 'Read the full notice →'}
      </button>

      {expanded && (
        <div className="mt-3 space-y-3 border-t border-gray-200 pt-3">
          {privacyNoticeContent.sections.map((s) => (
            <div key={s.title}>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-700">
                {s.title}
              </h4>
              <p className="mt-0.5 text-xs leading-relaxed text-gray-600">{s.body}</p>
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 flex items-start gap-3">
        <Checkbox
          id={`privacy-ack-${context}`}
          checked={checked}
          disabled={saving}
          onChange={(e) => void handleToggle(e.target.checked)}
          className="mt-0.5 accent-accent-600"
        />
        <label
          htmlFor={`privacy-ack-${context}`}
          className="cursor-pointer text-sm font-medium text-gray-900"
        >
          {privacyNoticeContent.acknowledgement}
        </label>
      </div>

      {error && (
        <p role="alert" className="mt-2 text-xs text-red-500">
          {error}
        </p>
      )}
    </div>
  );
}

export default PrivacyNotice;
