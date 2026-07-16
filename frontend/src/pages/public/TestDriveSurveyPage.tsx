import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PublicLayout } from '../../components/public';
import { Section, FadeIn } from '../../components/marketing';
import { Button, Alert } from '../../components/antigravity';
import { usePageMeta } from '../../hooks/usePageMeta';
import { submitSurvey, type SurveyInput } from '../../api/testDrive';
import { testDriveSurveyContent as c } from './testDriveSurveyContent';

// Q1 rating scale — a deliberate red→green semantic diverging palette (rough → smooth).
// Intentionally outside the navy/teal brand tokens; the colour IS the signal here.
const RATING_COLORS = ['#bf4a42', '#cf7d38', '#be8f2f', '#6f9e56', '#3f9b6a'];

type ProblemFit = '' | 'yes' | 'somewhat' | 'no';
type PilotInterest = '' | 'yes' | 'maybe' | 'no';
type TesterSegment = '' | 'prospect' | 'internal';

interface SurveyForm {
  tester_segment: TesterSegment;
  tester_name: string;
  tester_email: string;
  tester_company_role: string;
  tester_sector: string;
  q1_overall: number | null;
  q2_friction: string;
  q3_problem_fit: ProblemFit;
  q3_why: string;
  q4_change: string;
  trust_intent: PilotInterest;
  trust_intent_why: string;
  testimonial: string;
  testimonial_consent: boolean;
  pilot_interest: PilotInterest;
  pilot_note: string;
  referral_name: string;
  referral_company_role: string;
  referral_contact: string;
  referral_consent: boolean;
}

const EMPTY: SurveyForm = {
  tester_segment: '',
  tester_name: '',
  tester_email: '',
  tester_company_role: '',
  tester_sector: '',
  q1_overall: null,
  q2_friction: '',
  q3_problem_fit: '',
  q3_why: '',
  q4_change: '',
  trust_intent: '',
  trust_intent_why: '',
  testimonial: '',
  testimonial_consent: false,
  pilot_interest: '',
  pilot_note: '',
  referral_name: '',
  referral_company_role: '',
  referral_contact: '',
  referral_consent: false,
};

const clean = (s: string): string | undefined => (s.trim() ? s.trim() : undefined);

export const TestDriveSurveyPage: React.FC = () => {
  usePageMeta({
    title: 'Test drive — feedback · ReloPass',
    description: 'A few quick questions after running a test-drive case.',
    ogUrl: 'https://www.relopass.com/test-drive/survey',
  });

  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get('session') || '';
  const corridorId = (searchParams.get('corridor') || '').toUpperCase();

  // TD-M0 (AIQ-1556): pre-fill the tester's contact from what they entered at the
  // start (stashed under 'relopass_test_drive' by TestDrivePage) instead of re-asking.
  const [form, setForm] = useState<SurveyForm>(() => {
    try {
      const raw = localStorage.getItem('relopass_test_drive');
      if (raw) {
        const p = JSON.parse(raw) as { tester_name?: string; tester_email?: string };
        if (p.tester_name || p.tester_email) {
          return { ...EMPTY, tester_name: p.tester_name || '', tester_email: p.tester_email || '' };
        }
      }
    } catch {
      /* private-mode / storage disabled — fall through to empty */
    }
    return EMPTY;
  });
  const [state, setState] = useState<'idle' | 'submitting' | 'done'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [sectorOther, setSectorOther] = useState(false);

  const set = <K extends keyof SurveyForm>(key: K, value: SurveyForm[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (state !== 'idle') return;
    // TD-FIX-2 (AIQ-1503): the segment tap is required — never silently default to
    // 'prospect'. An unanswered survey stays honest (no segment written).
    if (!form.tester_segment) {
      setError(c.segment.required);
      return;
    }
    // AIQ-1543: validate the optional lead-in email client-side (a blank email is fine).
    // The server rejects a bad address too; this just surfaces it before the round-trip.
    const emailTrimmed = form.tester_email.trim();
    if (emailTrimmed && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(emailTrimmed)) {
      setError(c.aboutYou.email.invalid);
      return;
    }
    setState('submitting');
    setError(null);
    const payload: SurveyInput = {
      session_id: sessionId || undefined,
      corridor_id: corridorId || undefined,
      tester_segment: form.tester_segment,
      tester_name: clean(form.tester_name),
      tester_email: clean(form.tester_email),
      tester_company_role: clean(form.tester_company_role),
      tester_sector: clean(form.tester_sector),
      q1_overall: form.q1_overall ?? undefined,
      q2_friction: clean(form.q2_friction),
      q3_problem_fit: form.q3_problem_fit || undefined,
      q3_why: clean(form.q3_why),
      q4_change: clean(form.q4_change),
      trust_intent: form.trust_intent || undefined,
      trust_intent_why: clean(form.trust_intent_why),
      testimonial: clean(form.testimonial),
      testimonial_consent: form.testimonial_consent,
      pilot_interest: form.pilot_interest || undefined,
      pilot_note: clean(form.pilot_note),
      referral_name: clean(form.referral_name),
      referral_company_role: clean(form.referral_company_role),
      referral_contact: clean(form.referral_contact),
      referral_consent: form.referral_consent,
    };
    const res = await submitSurvey(payload);
    if (res.ok) {
      setState('done');
    } else {
      setError(res.error);
      setState('idle');
    }
  };

  if (state === 'done') {
    return (
      <PublicLayout>
        <Section spacing="lg" background="transparent">
          <div className="mx-auto max-w-xl text-center" role="status" aria-live="polite">
            <h1 className="text-marketing-h2 font-semibold text-marketing-primary">
              {c.thankYou.header}
            </h1>
            <p className="mt-4 text-marketing-body text-marketing-text-muted leading-relaxed">
              {c.thankYou.body}
            </p>
            <p className="mt-6 text-[15px] font-semibold italic text-marketing-primary">
              {c.signature}
            </p>
          </div>
        </Section>
      </PublicLayout>
    );
  }

  return (
    <PublicLayout>
      <Section spacing="lg" background="transparent">
        <div className="mx-auto max-w-xl text-center">
          <h1 className="text-marketing-h2 font-semibold text-marketing-primary">{c.intro.header}</h1>
          <p className="mt-4 text-marketing-body text-marketing-text-muted leading-relaxed">
            {c.intro.body}
          </p>
          <div className="mx-auto mt-5 max-w-lg rounded-lg border border-marketing-accent/30 bg-marketing-accent/10 px-4 py-3 text-left text-[13px] leading-relaxed text-marketing-primary">
            🔒 {c.privacy}
            <span className="mt-2 block font-semibold italic">{c.signature}</span>
          </div>
        </div>
      </Section>

      <Section spacing="lg" background="muted">
        <FadeIn>
          <form
            onSubmit={handleSubmit}
            noValidate
            className="mx-auto max-w-xl space-y-8 rounded-xl border border-marketing-border bg-marketing-surface p-6 sm:p-8"
          >
            {/* TD-FIX-2 (AIQ-1503): required one-tap segment self-ID — lead-in question. */}
            <div>
              <p className="text-sm font-medium text-marketing-primary">
                {c.segment.label}
                <span aria-hidden="true" className="ml-0.5 text-[#dc2626]">*</span>
              </p>
              <p className="mt-1 text-xs text-marketing-text-muted">{c.segment.helper}</p>
              <TapGroup
                options={c.segment.options}
                value={form.tester_segment}
                onSelect={(v) => set('tester_segment', v as TesterSegment)}
              />
            </div>

            {/* About you */}
            <fieldset className="space-y-4">
              <legend className="text-[15px] font-semibold text-marketing-primary">
                {c.aboutYou.header}
              </legend>
              <TextField
                id="s-name"
                label={c.aboutYou.name.label}
                value={form.tester_name}
                onChange={(v) => set('tester_name', v)}
                autoComplete="name"
              />
              <TextField
                id="s-email"
                label={c.aboutYou.email.label}
                helper={c.aboutYou.email.helper}
                type="email"
                value={form.tester_email}
                onChange={(v) => set('tester_email', v)}
                autoComplete="email"
              />
              <TextField
                id="s-company-role"
                label={c.aboutYou.companyRole.label}
                helper={c.aboutYou.companyRole.helper}
                value={form.tester_company_role}
                onChange={(v) => set('tester_company_role', v)}
              />
              <div>
                <label htmlFor="s-sector" className="block text-sm font-medium text-marketing-primary">
                  {c.aboutYou.sector.label}
                  <span className="ml-1 font-normal text-marketing-text-muted">
                    — {c.aboutYou.sector.helper}
                  </span>
                </label>
                <select
                  id="s-sector"
                  value={sectorOther ? '__other__' : form.tester_sector}
                  onChange={(e) => {
                    const v = e.target.value;
                    if (v === '__other__') {
                      setSectorOther(true);
                      set('tester_sector', '');
                    } else {
                      setSectorOther(false);
                      set('tester_sector', v);
                    }
                  }}
                  className={fieldInputClass}
                >
                  <option value="">{c.aboutYou.sector.placeholder}</option>
                  {c.aboutYou.sector.options.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                  <option value="__other__">{c.aboutYou.sector.otherLabel}</option>
                </select>
                {sectorOther && (
                  <input
                    type="text"
                    aria-label={c.aboutYou.sector.label}
                    placeholder={c.aboutYou.sector.otherPlaceholder}
                    value={form.tester_sector}
                    onChange={(e) => set('tester_sector', e.target.value)}
                    className={`${fieldInputClass} mt-2`}
                  />
                )}
              </div>
            </fieldset>

            {/* Q1 — overall (one tap) */}
            <div>
              <p className="text-sm font-medium text-marketing-primary">{c.q1.label}</p>
              <div className="mt-3 flex items-center gap-2">
                {[1, 2, 3, 4, 5].map((n) => {
                  const color = RATING_COLORS[n - 1];
                  const selected = form.q1_overall === n;
                  return (
                    <button
                      key={n}
                      type="button"
                      aria-pressed={selected}
                      onClick={() => set('q1_overall', n)}
                      className="h-11 w-11 rounded-lg text-sm font-bold text-white transition-transform hover:-translate-y-px focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-marketing-accent/50"
                      style={{
                        backgroundColor: color,
                        border: `1.5px solid ${color}`,
                        opacity: selected ? 1 : 0.72,
                        boxShadow: selected ? `0 5px 14px -4px ${color}80` : 'none',
                      }}
                    >
                      {n}
                    </button>
                  );
                })}
              </div>
              <div className="mt-1 flex justify-between text-[11px] text-marketing-text-muted">
                <span>{c.q1.low}</span>
                <span>{c.q1.high}</span>
              </div>
            </div>

            {/* Q2 — friction */}
            <TextArea
              id="s-friction"
              label={c.q2.label}
              helper={c.q2.helper}
              value={form.q2_friction}
              onChange={(v) => set('q2_friction', v)}
            />

            {/* Q3 — problem fit (tap + one line) */}
            <div>
              <p className="text-sm font-medium text-marketing-primary">{c.q3.label}</p>
              <TapGroup
                options={c.q3.options}
                value={form.q3_problem_fit}
                onSelect={(v) => set('q3_problem_fit', v as ProblemFit)}
              />
              <div className="mt-3">
                <TextField
                  id="s-why"
                  label={c.q3.whyLabel}
                  value={form.q3_why}
                  onChange={(v) => set('q3_why', v)}
                />
              </div>
            </div>

            {/* Q4 — one change */}
            <TextArea
              id="s-change"
              label={c.q4.label}
              value={form.q4_change}
              onChange={(v) => set('q4_change', v)}
            />

            {/* TD-M4 (AIQ-1559): trust / intent-to-use — one tap + optional why */}
            <div>
              <p className="text-sm font-medium text-marketing-primary">{c.trust.label}</p>
              <TapGroup
                options={c.trust.options}
                value={form.trust_intent}
                onSelect={(v) => set('trust_intent', v as PilotInterest)}
              />
              <div className="mt-3">
                <TextField
                  id="s-trust-why"
                  label={c.trust.whyLabel}
                  value={form.trust_intent_why}
                  onChange={(v) => set('trust_intent_why', v)}
                />
              </div>
            </div>

            <p className="text-[13px] italic text-marketing-text-muted">{c.highValueIntro}</p>

            {/* Q5 — testimonial + consent */}
            <div>
              <TextField
                id="s-testimonial"
                label={c.q5.label}
                helper={c.q5.helper}
                value={form.testimonial}
                onChange={(v) => set('testimonial', v)}
              />
              <Consent
                id="s-testimonial-consent"
                label={c.q5.consent}
                checked={form.testimonial_consent}
                onChange={(v) => set('testimonial_consent', v)}
              />
            </div>

            {/* Q6 — pilot interest */}
            <div>
              <p className="text-sm font-medium text-marketing-primary">{c.q6.label}</p>
              <TapGroup
                options={c.q6.options}
                value={form.pilot_interest}
                onSelect={(v) => set('pilot_interest', v as PilotInterest)}
              />
              <div className="mt-3">
                <TextField
                  id="s-pilot-note"
                  label={c.q6.noteLabel}
                  helper={c.q6.helper}
                  value={form.pilot_note}
                  onChange={(v) => set('pilot_note', v)}
                />
              </div>
            </div>

            {/* Q7 — intro + consent */}
            <fieldset className="space-y-3">
              <legend className="text-sm font-medium text-marketing-primary">{c.q7.label}</legend>
              <TextField
                id="s-ref-name"
                label={c.q7.name}
                value={form.referral_name}
                onChange={(v) => set('referral_name', v)}
              />
              <TextField
                id="s-ref-role"
                label={c.q7.companyRole}
                value={form.referral_company_role}
                onChange={(v) => set('referral_company_role', v)}
              />
              <TextField
                id="s-ref-contact"
                label={c.q7.contact}
                value={form.referral_contact}
                onChange={(v) => set('referral_contact', v)}
              />
              <Consent
                id="s-ref-consent"
                label={c.q7.consent}
                checked={form.referral_consent}
                onChange={(v) => set('referral_consent', v)}
              />
              <p className="text-[11px] text-marketing-text-muted">{c.q7.helper}</p>
            </fieldset>

            {error && <Alert variant="error">{error}</Alert>}

            <Button
              unstyled
              type="submit"
              disabled={state === 'submitting'}
              className="inline-flex w-full items-center justify-center rounded-lg bg-marketing-primary px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-marketing-primary-muted focus:outline-none focus:ring-2 focus:ring-marketing-accent focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {state === 'submitting' ? 'Sending…' : c.submit}
            </Button>
          </form>
        </FadeIn>
      </Section>
    </PublicLayout>
  );
};

interface FieldProps {
  id: string;
  label: string;
  helper?: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
}

const fieldInputClass =
  'mt-1 w-full rounded-lg border border-marketing-border bg-white px-3 py-2 text-sm text-marketing-text transition-colors focus:border-marketing-accent focus:outline-none focus:ring-2 focus:ring-marketing-accent/40';

const TextField: React.FC<FieldProps> = ({ id, label, helper, type = 'text', value, onChange, autoComplete }) => (
  <div>
    <label htmlFor={id} className="block text-sm font-medium text-marketing-primary">
      {label}
      {helper && <span className="ml-1 font-normal text-marketing-text-muted">— {helper}</span>}
    </label>
    <input
      id={id}
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      autoComplete={autoComplete}
      className={fieldInputClass}
    />
  </div>
);

const TextArea: React.FC<Omit<FieldProps, 'type' | 'autoComplete'>> = ({ id, label, helper, value, onChange }) => (
  <div>
    <label htmlFor={id} className="block text-sm font-medium text-marketing-primary">
      {label}
    </label>
    {helper && <p className="mt-1 text-xs text-marketing-text-muted">{helper}</p>}
    <textarea
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={3}
      className={fieldInputClass}
    />
  </div>
);

const TapGroup: React.FC<{
  options: ReadonlyArray<{ value: string; label: string }>;
  value: string;
  onSelect: (v: string) => void;
}> = ({ options, value, onSelect }) => (
  <div className="mt-3 flex flex-wrap gap-2">
    {options.map((opt) => (
      <button
        key={opt.value}
        type="button"
        aria-pressed={value === opt.value}
        onClick={() => onSelect(opt.value)}
        className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
          value === opt.value
            ? 'border-marketing-accent bg-marketing-accent/10 text-marketing-accent'
            : 'border-marketing-border text-marketing-text hover:bg-marketing-surface-muted'
        }`}
      >
        {opt.label}
      </button>
    ))}
  </div>
);

const Consent: React.FC<{ id: string; label: string; checked: boolean; onChange: (v: boolean) => void }> = ({
  id,
  label,
  checked,
  onChange,
}) => (
  <label htmlFor={id} className="mt-3 flex items-start gap-2 text-sm text-marketing-text">
    <input
      id={id}
      type="checkbox"
      checked={checked}
      onChange={(e) => onChange(e.target.checked)}
      className="mt-0.5 h-4 w-4 rounded border-marketing-border text-marketing-accent focus:ring-marketing-accent/40"
    />
    <span>{label}</span>
  </label>
);
