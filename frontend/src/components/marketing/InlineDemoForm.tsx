import React, { useState } from 'react';
import { submitDemoBooking } from '../../api/demoBooking';
import { track } from '../../analytics';
import { accessContent } from '../../pages/public/accessContent';

const PERSONAL_EMAIL_DOMAINS = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com'];
const FALLBACK_CHALLENGE = 'Inline /access form: corridor not specified.';

interface FormState {
  name: string;
  email: string;
  company: string;
  corridor: string;
}

const EMPTY_FORM: FormState = { name: '', email: '', company: '', corridor: '' };

type SubmitState = 'idle' | 'submitting' | 'success';

function validateClient(form: FormState): Record<string, string> {
  const errors: Record<string, string> = {};
  if (form.name.trim().length < 2) errors.name = 'Please enter your name.';

  const email = form.email.trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    errors.email = 'Please enter a valid email address.';
  } else {
    const domain = email.split('@')[1]?.toLowerCase() ?? '';
    if (PERSONAL_EMAIL_DOMAINS.includes(domain)) {
      errors.email = 'Please use your work email.';
    }
  }

  if (form.company.trim().length < 2) errors.company = 'Please enter your company name.';
  return errors;
}

export const InlineDemoForm: React.FC = () => {
  const c = accessContent.bookingForm;
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [state, setState] = useState<SubmitState>('idle');
  const [showSuccess, setShowSuccess] = useState(false);
  const submitted = state === 'success';

  const update = (field: keyof FormState) => (value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[field];
        return next;
      });
    }
    if (formError) setFormError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (state !== 'idle') return;

    const validationErrors = validateClient(form);
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setState('submitting');
    setFormError(null);

    const corridor = form.corridor.trim();
    const result = await submitDemoBooking({
      firstName: form.name.trim(),
      email: form.email.trim(),
      company: form.company.trim(),
      challenge: corridor.length >= 10 ? corridor : FALLBACK_CHALLENGE,
      sourcePage: 'access-page-inline-form',
    });

    if (result.ok) {
      track('demo_request_submitted', {
        source_page: 'access-page-inline-form',
        demo_id: result.demoId,
      });
      setState('success');
      setTimeout(() => setShowSuccess(true), 50);
      return;
    }

    setErrors(result.fieldErrors);
    setFormError(c.errorFallback);
    setState('idle');
  };

  return (
    <div className="relative mx-auto mt-12 max-w-xl">
      <div
        style={{
          opacity: submitted ? 0 : 1,
          transform: submitted ? 'translateY(-8px)' : 'translateY(0)',
          transition: 'opacity 300ms ease-out, transform 300ms ease-out',
          pointerEvents: submitted ? 'none' : 'auto',
        }}
      >
        <form
          onSubmit={handleSubmit}
          noValidate
          aria-hidden={submitted}
          className="rounded-xl border border-marketing-border bg-marketing-surface p-6 sm:p-8"
        >
      <div className="space-y-4">
        <Field
          id="inline-demo-name"
          label={c.fields.name.label}
          placeholder={c.fields.name.placeholder}
          value={form.name}
          onChange={update('name')}
          error={errors.name ?? errors.firstName}
          autoComplete="name"
          disabled={state === 'submitting'}
          required
        />
        <Field
          id="inline-demo-email"
          label={c.fields.email.label}
          placeholder={c.fields.email.placeholder}
          type="email"
          value={form.email}
          onChange={update('email')}
          error={errors.email}
          autoComplete="email"
          disabled={state === 'submitting'}
          required
        />
        <Field
          id="inline-demo-company"
          label={c.fields.company.label}
          placeholder={c.fields.company.placeholder}
          value={form.company}
          onChange={update('company')}
          error={errors.company}
          autoComplete="organization"
          disabled={state === 'submitting'}
          required
        />
        <Field
          id="inline-demo-corridor"
          label={c.fields.corridor.label}
          placeholder={c.fields.corridor.placeholder}
          value={form.corridor}
          onChange={update('corridor')}
          disabled={state === 'submitting'}
        />
      </div>

      <div className="mt-6">
        <button
          type="submit"
          disabled={state === 'submitting'}
          className="inline-flex w-full items-center justify-center rounded-lg bg-marketing-primary px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-marketing-primary-muted focus:outline-none focus:ring-2 focus:ring-marketing-accent focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {state === 'submitting' ? 'Sending…' : c.submitLabel}
        </button>

        {formError ? (
          <p className="mt-3 text-center text-sm text-[#7a2a2a]">
            Something went wrong. Email us at{' '}
            <a className="underline" href="mailto:contact@relopass.com">
              contact@relopass.com
            </a>
            .
          </p>
        ) : (
          <p className="mt-3 text-center text-[11px] text-marketing-text-muted">
            {c.submitMicrocopy}
          </p>
        )}
        </div>
      </form>
      </div>

      {state === 'success' && (
        <div
          className="absolute inset-0 flex flex-col items-center justify-center text-center rounded-xl border border-marketing-border bg-marketing-surface px-6 py-8 sm:px-8"
          role="status"
          aria-live="polite"
          style={{
            opacity: showSuccess ? 1 : 0,
            transform: showSuccess ? 'translateY(0)' : 'translateY(8px)',
            transition: 'opacity 300ms ease-out 150ms, transform 300ms ease-out 150ms',
          }}
        >
          <p className="text-lg font-semibold text-marketing-primary">{c.success.title}</p>
          <p className="mt-2 text-marketing-body text-marketing-text-muted">{c.success.body}</p>
        </div>
      )}
    </div>
  );
};

interface FieldProps {
  id: string;
  label: string;
  placeholder?: string;
  value: string;
  onChange: (v: string) => void;
  error?: string;
  type?: string;
  autoComplete?: string;
  disabled?: boolean;
  required?: boolean;
}

const Field: React.FC<FieldProps> = ({
  id,
  label,
  placeholder,
  value,
  onChange,
  error,
  type = 'text',
  autoComplete,
  disabled,
  required,
}) => (
  <div>
    <label htmlFor={id} className="block text-sm font-medium text-marketing-primary">
      {label}
      {required && <span aria-hidden="true" className="ml-0.5 text-[#dc2626]">*</span>}
    </label>
    <input
      id={id}
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      autoComplete={autoComplete}
      disabled={disabled}
      aria-invalid={error ? 'true' : 'false'}
      aria-describedby={error ? `${id}-error` : undefined}
      className={`mt-1 w-full rounded-lg border bg-white px-3 py-2 text-sm text-marketing-text transition-colors focus:outline-none focus:ring-2 ${
        error
          ? 'border-[#dc2626] focus:border-[#dc2626] focus:ring-[#dc2626]/40'
          : 'border-marketing-border focus:border-marketing-accent focus:ring-marketing-accent/40'
      } disabled:cursor-not-allowed disabled:bg-marketing-surface-muted`}
    />
    {error && (
      <p id={`${id}-error`} className="mt-1 text-xs text-[#dc2626]">
        {error}
      </p>
    )}
  </div>
);
