import React, { useState } from 'react';
import { leadCaptureAPI } from '../../api/client';
import { emitMarketingEvent } from '../../analytics';

/**
 * [AIQ-1783] Lead form for the two paid-ad landing pages (ADS-3).
 *
 * Deliberately NOT reusing InlineDemoForm: that component takes no props and hardcodes
 * `access-page-inline-form`, and the two ad pages ask different questions. It posts to
 * the same endpoint via the same `leadCaptureAPI.submit`.
 *
 * The extra question rides in `message` rather than a dedicated column. That is a
 * conscious trade: a new column needs a migration, migrations here are applied
 * out-of-band with no automated apply, and a merged-but-unapplied column would leave a
 * paid campaign pointing at a form that 500s. The target-account signal that actually
 * matters is already derived server-side from the work-email domain.
 */

export interface AdLeadFormProps {
  /** Distinguishes the two pages in analytics and in utm_campaign fallback. */
  page: 'mobility-teams' | 'relocation-checklist';
  heading: string;
  submitLabel: string;
  successMessage: string;
  emailLabel?: string;
  /** Free-text question rendered as a text input (segment B's employer capture). */
  textQuestion?: { label: string; required?: boolean };
  /** Single-select question rendered as a dropdown (segment A's volume band). */
  selectQuestion?: { label: string; options: readonly string[]; required?: boolean };
  /** Rendered under the submit button — used for segment B's disclaimer. */
  footnote?: string;
}

export const AdLeadForm: React.FC<AdLeadFormProps> = ({
  page,
  heading,
  submitLabel,
  successMessage,
  emailLabel = 'Work email',
  textQuestion,
  selectQuestion,
  footnote,
}) => {
  const [email, setEmail] = useState('');
  const [answer, setAnswer] = useState('');
  const [status, setStatus] = useState<'idle' | 'sending' | 'done' | 'error'>('idle');

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (status === 'sending') return;
    setStatus('sending');

    const params = new URLSearchParams(window.location.search);
    const question = textQuestion?.label ?? selectQuestion?.label;

    try {
      await leadCaptureAPI.submit({
        email: email.trim(),
        source: 'marketing_site',
        // The question is preserved with its label so an admin reading the lead
        // knows what was asked, not just what was answered.
        message: question && answer ? `${question} ${answer}` : undefined,
        utm_source: params.get('utm_source') || undefined,
        utm_campaign: params.get('utm_campaign') || `ads-${page}`,
      });
      emitMarketingEvent('landing_cta_click', { page, cta: submitLabel });
      setStatus('done');
    } catch {
      // Never dead-end a click we paid for: tell them how to reach us anyway.
      setStatus('error');
    }
  };

  if (status === 'done') {
    return (
      <div
        role="status"
        className="rounded-xl border border-marketing-accent/30 bg-marketing-accent/5 p-6"
      >
        <p className="text-[15px] font-semibold text-marketing-primary">{successMessage}</p>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="rounded-xl border border-black/10 bg-white p-6 shadow-sm">
      <h2 className="text-[18px] font-bold text-marketing-primary">{heading}</h2>

      <label className="mt-4 block text-[13px] font-medium text-marketing-primary" htmlFor={`${page}-email`}>
        {emailLabel}
      </label>
      <input
        id={`${page}-email`}
        type="email"
        required
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="mt-1 w-full rounded-lg border border-black/15 px-3 py-2 text-[14px] focus:border-marketing-accent focus:outline-none focus:ring-2 focus:ring-marketing-accent/30"
      />

      {textQuestion && (
        <>
          <label className="mt-4 block text-[13px] font-medium text-marketing-primary" htmlFor={`${page}-text`}>
            {textQuestion.label}
          </label>
          <input
            id={`${page}-text`}
            type="text"
            required={textQuestion.required}
            autoComplete="organization"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            className="mt-1 w-full rounded-lg border border-black/15 px-3 py-2 text-[14px] focus:border-marketing-accent focus:outline-none focus:ring-2 focus:ring-marketing-accent/30"
          />
        </>
      )}

      {selectQuestion && (
        <>
          <label className="mt-4 block text-[13px] font-medium text-marketing-primary" htmlFor={`${page}-select`}>
            {selectQuestion.label}
          </label>
          <select
            id={`${page}-select`}
            required={selectQuestion.required}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            className="mt-1 w-full rounded-lg border border-black/15 bg-white px-3 py-2 text-[14px] focus:border-marketing-accent focus:outline-none focus:ring-2 focus:ring-marketing-accent/30"
          >
            <option value="">Select…</option>
            {selectQuestion.options.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        </>
      )}

      <button
        type="submit"
        disabled={status === 'sending'}
        className="mt-5 w-full rounded-lg bg-marketing-primary px-4 py-2.5 text-[14px] font-semibold text-white transition hover:opacity-90 disabled:opacity-60"
      >
        {status === 'sending' ? 'Sending…' : submitLabel}
      </button>

      {status === 'error' && (
        <p role="alert" className="mt-3 text-[13px] text-red-700">
          That didn&apos;t go through. Please email us at{' '}
          <a className="underline" href="mailto:hello@relopass.com">
            hello@relopass.com
          </a>
          .
        </p>
      )}

      {footnote && <p className="mt-4 text-[12px] leading-relaxed text-marketing-text-muted">{footnote}</p>}
    </form>
  );
};
