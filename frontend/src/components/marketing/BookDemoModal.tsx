import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useDemoBooking } from '../../hooks/useDemoBooking';
import { submitDemoBooking } from '../../api/demoBooking';
import { track } from '../../analytics';

const MAX_CHALLENGE = 500;
const MIN_CHALLENGE = 10;

interface FormState {
  firstName: string;
  email: string;
  company: string;
  challenge: string;
}

type SubmitState = 'idle' | 'submitting' | 'success';

const EMPTY_FORM: FormState = { firstName: '', email: '', company: '', challenge: '' };

function validateClient(form: FormState): Record<string, string> {
  const errors: Record<string, string> = {};
  if (form.firstName.trim().length < 2) errors.firstName = 'Please enter your first name.';
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim()))
    errors.email = 'Please enter a valid email address.';
  if (form.company.trim().length < 2) errors.company = 'Please enter your company name.';
  const ch = form.challenge.trim().length;
  if (ch < MIN_CHALLENGE) errors.challenge = `Tell us a bit more (min ${MIN_CHALLENGE} characters).`;
  else if (ch > MAX_CHALLENGE) errors.challenge = `Please keep this under ${MAX_CHALLENGE} characters.`;
  return errors;
}

export const BookDemoModal: React.FC = () => {
  const { isOpen, sourcePage, close } = useDemoBooking();
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [state, setState] = useState<SubmitState>('idle');
  const firstFieldRef = useRef<HTMLInputElement | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);

  const isDirty =
    form.firstName.length > 0 ||
    form.email.length > 0 ||
    form.company.length > 0 ||
    form.challenge.length > 0;

  const reset = useCallback(() => {
    setForm(EMPTY_FORM);
    setErrors({});
    setFormError(null);
    setState('idle');
  }, []);

  const requestClose = useCallback(() => {
    if (state === 'submitting') return;
    if (state === 'idle' && isDirty) {
      const ok = typeof window !== 'undefined'
        ? window.confirm('You have unsaved details. Close anyway?')
        : true;
      if (!ok) return;
    }
    close();
  }, [close, isDirty, state]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        requestClose();
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen, requestClose]);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => firstFieldRef.current?.focus(), 30);
    } else {
      // Reset state after the closing transition so it doesn't flash on reopen.
      const t = setTimeout(reset, 200);
      return () => clearTimeout(t);
    }
    return;
  }, [isOpen, reset]);

  if (!isOpen) return null;

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
    const result = await submitDemoBooking({
      firstName: form.firstName.trim(),
      email: form.email.trim(),
      company: form.company.trim(),
      challenge: form.challenge.trim(),
      sourcePage,
    });

    if (result.ok) {
      track('demo_request_submitted', { source_page: sourcePage, demo_id: result.demoId });
      setState('success');
      setTimeout(() => close(), 3500);
      return;
    }

    setErrors(result.fieldErrors);
    setFormError(result.formError);
    setState('idle');
  };

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 px-4 py-8"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) requestClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="book-demo-title"
        className="w-full max-w-lg rounded-xl border border-marketing-border bg-marketing-surface shadow-xl"
      >
        <div className="flex items-start justify-between px-6 pt-6 sm:px-8 sm:pt-8">
          <div>
            <h2
              id="book-demo-title"
              className="text-xl sm:text-2xl font-semibold text-marketing-primary"
            >
              Schedule a demo
            </h2>
            <p className="mt-1 text-sm text-marketing-text-muted">
              See how HR teams coordinate relocation end-to-end.
            </p>
          </div>
          <button
            type="button"
            onClick={requestClose}
            className="ml-4 rounded-md p-1 text-marketing-text-subtle hover:text-marketing-primary focus:outline-none focus:ring-2 focus:ring-marketing-accent"
            aria-label="Close"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {state === 'success' ? (
          <div className="px-6 py-8 sm:px-8 sm:py-10">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-marketing-accent/10 text-marketing-accent">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                  <path d="M3 7.5L6 10.5L11.5 4" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <div>
                <p className="text-base font-medium text-marketing-primary">Request received.</p>
                <p className="mt-1 text-sm text-marketing-text-muted">
                  We'll reply within the next few business days.
                </p>
              </div>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} noValidate className="px-6 pb-6 pt-5 sm:px-8 sm:pb-8">
            <div className="space-y-4">
              <Field
                id="book-demo-first-name"
                label="First name"
                value={form.firstName}
                onChange={update('firstName')}
                error={errors.firstName}
                autoComplete="given-name"
                disabled={state === 'submitting'}
                inputRef={firstFieldRef}
              />
              <Field
                id="book-demo-email"
                label="Work email"
                type="email"
                value={form.email}
                onChange={update('email')}
                error={errors.email}
                autoComplete="email"
                disabled={state === 'submitting'}
                help="We'll send next steps here."
              />
              <Field
                id="book-demo-company"
                label="Company"
                value={form.company}
                onChange={update('company')}
                error={errors.company}
                autoComplete="organization"
                disabled={state === 'submitting'}
              />
              <TextAreaField
                id="book-demo-challenge"
                label="What's your main challenge with relocation?"
                value={form.challenge}
                onChange={update('challenge')}
                error={errors.challenge}
                disabled={state === 'submitting'}
                maxLength={MAX_CHALLENGE}
                help={`${form.challenge.trim().length}/${MAX_CHALLENGE}`}
                placeholder="E.g. tracking vendor progress across multiple cases."
              />
            </div>

            {formError && (
              <div className="mt-4 rounded-md border border-[#f1c9cc] bg-[#fdf3f4] px-3 py-2 text-sm text-[#7a2a2a]">
                {formError}
              </div>
            )}

            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-end">
              <button
                type="button"
                onClick={requestClose}
                disabled={state === 'submitting'}
                className="inline-flex items-center justify-center rounded-lg px-4 py-2.5 text-sm font-medium text-marketing-text-muted hover:text-marketing-primary disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={state === 'submitting'}
                className="inline-flex items-center justify-center rounded-lg bg-marketing-primary px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-marketing-primary-muted focus:outline-none focus:ring-2 focus:ring-marketing-accent focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {state === 'submitting' ? 'Sending…' : 'Schedule the demo'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

interface FieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  error?: string;
  help?: string;
  type?: string;
  autoComplete?: string;
  disabled?: boolean;
  inputRef?: React.RefObject<HTMLInputElement>;
}

const Field: React.FC<FieldProps> = ({
  id,
  label,
  value,
  onChange,
  error,
  help,
  type = 'text',
  autoComplete,
  disabled,
  inputRef,
}) => {
  const describedBy = error ? `${id}-error` : help ? `${id}-help` : undefined;
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-marketing-primary">
        {label}
      </label>
      <input
        ref={inputRef}
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        disabled={disabled}
        aria-invalid={error ? 'true' : 'false'}
        aria-describedby={describedBy}
        className={`mt-1 w-full rounded-lg border bg-white px-3 py-2 text-sm text-marketing-text transition-colors focus:outline-none focus:ring-2 ${
          error
            ? 'border-[#dc2626] focus:border-[#dc2626] focus:ring-[#dc2626]/40'
            : 'border-marketing-border focus:border-marketing-accent focus:ring-marketing-accent/40'
        } disabled:cursor-not-allowed disabled:bg-marketing-surface-muted`}
      />
      {error ? (
        <p id={`${id}-error`} className="mt-1 text-xs text-[#dc2626]">
          {error}
        </p>
      ) : help ? (
        <p id={`${id}-help`} className="mt-1 text-xs text-marketing-text-subtle">
          {help}
        </p>
      ) : null}
    </div>
  );
};

interface TextAreaFieldProps extends Omit<FieldProps, 'type' | 'inputRef'> {
  maxLength?: number;
  placeholder?: string;
}

const TextAreaField: React.FC<TextAreaFieldProps> = ({
  id,
  label,
  value,
  onChange,
  error,
  help,
  disabled,
  maxLength,
  placeholder,
}) => {
  const describedBy = error ? `${id}-error` : help ? `${id}-help` : undefined;
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-marketing-primary">
        {label}
      </label>
      <textarea
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        maxLength={maxLength}
        placeholder={placeholder}
        rows={4}
        aria-invalid={error ? 'true' : 'false'}
        aria-describedby={describedBy}
        className={`mt-1 w-full rounded-lg border bg-white px-3 py-2 text-sm text-marketing-text transition-colors focus:outline-none focus:ring-2 ${
          error
            ? 'border-[#dc2626] focus:border-[#dc2626] focus:ring-[#dc2626]/40'
            : 'border-marketing-border focus:border-marketing-accent focus:ring-marketing-accent/40'
        } disabled:cursor-not-allowed disabled:bg-marketing-surface-muted`}
      />
      {error ? (
        <p id={`${id}-error`} className="mt-1 text-xs text-[#dc2626]">
          {error}
        </p>
      ) : help ? (
        <p id={`${id}-help`} className="mt-1 text-xs text-marketing-text-subtle">
          {help}
        </p>
      ) : null}
    </div>
  );
};
