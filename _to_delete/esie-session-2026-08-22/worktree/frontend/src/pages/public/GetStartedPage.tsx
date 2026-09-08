import React, { useState } from 'react';
import { PublicLayout } from '../../components/public';
import {
  Section,
  HeroSurface,
  SectionHeader,
  CTAButton,
  FadeIn,
} from '../../components/marketing';
import { useDemoBooking } from '../../hooks/useDemoBooking';
import { usePageMeta } from '../../hooks/usePageMeta';
import { getStartedContent } from './getStartedContent';

interface FormState {
  firstName: string;
  lastName: string;
  email: string;
  company: string;
  volume: string;
  challenge: string;
}

const EMPTY_FORM: FormState = {
  firstName: '',
  lastName: '',
  email: '',
  company: '',
  volume: '',
  challenge: '',
};

export const GetStartedPage: React.FC = () => {
  usePageMeta({
    title: 'Get started · ReloPass',
    description:
      "Three ways in. Book a demo, sign in, or create an account. Tell us how your relocations run today and we'll show you what changes.",
    ogUrl: 'https://www.relopass.com/get-started',
  });

  const { open: openDemoBooking } = useDemoBooking();
  const c = getStartedContent;

  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  const update = (field: keyof FormState) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
    };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    openDemoBooking('get-started-form');
  };

  return (
    <PublicLayout>
      <Section spacing="lg" background="transparent">
        <HeroSurface
          eyebrow={c.hero.eyebrow}
          title={c.hero.headline}
          subtitle={c.hero.subheadline}
        />
      </Section>

      <Section spacing="lg" background="muted">
        <FadeIn>
          <div className="grid grid-cols-1 lg:grid-cols-[1.2fr,1fr] gap-10 lg:gap-14 items-start">
            <form
              onSubmit={handleSubmit}
              noValidate
              className="rounded-xl border border-marketing-border bg-marketing-surface p-6 sm:p-8"
            >
              <h2 className="text-marketing-h2 font-semibold text-marketing-primary">
                {c.form.title}
              </h2>

              <div className="mt-6 space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <TextField
                    id="gs-first-name"
                    label={c.form.fields.firstName.label}
                    placeholder={c.form.fields.firstName.placeholder}
                    value={form.firstName}
                    onChange={update('firstName')}
                    autoComplete="given-name"
                    required
                  />
                  <TextField
                    id="gs-last-name"
                    label={c.form.fields.lastName.label}
                    placeholder={c.form.fields.lastName.placeholder}
                    value={form.lastName}
                    onChange={update('lastName')}
                    autoComplete="family-name"
                    required
                  />
                </div>
                <TextField
                  id="gs-email"
                  label={c.form.fields.email.label}
                  placeholder={c.form.fields.email.placeholder}
                  type="email"
                  value={form.email}
                  onChange={update('email')}
                  autoComplete="email"
                  required
                />
                <TextField
                  id="gs-company"
                  label={c.form.fields.company.label}
                  placeholder={c.form.fields.company.placeholder}
                  value={form.company}
                  onChange={update('company')}
                  autoComplete="organization"
                  required
                />
                <div>
                  <label
                    htmlFor="gs-volume"
                    className="block text-sm font-medium text-marketing-primary"
                  >
                    {c.form.fields.volume.label}
                    <span aria-hidden="true" className="ml-0.5 text-[#dc2626]">*</span>
                  </label>
                  <select
                    id="gs-volume"
                    value={form.volume}
                    onChange={update('volume')}
                    required
                    className="mt-1 w-full rounded-lg border border-marketing-border bg-white px-3 py-2 text-sm text-marketing-text transition-colors focus:border-marketing-accent focus:outline-none focus:ring-2 focus:ring-marketing-accent/40"
                  >
                    <option value="" disabled>
                      {c.form.fields.volume.placeholder}
                    </option>
                    {c.form.fields.volume.options.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label
                    htmlFor="gs-challenge"
                    className="block text-sm font-medium text-marketing-primary"
                  >
                    {c.form.fields.challenge.label}
                  </label>
                  <textarea
                    id="gs-challenge"
                    value={form.challenge}
                    onChange={update('challenge')}
                    placeholder={c.form.fields.challenge.placeholder}
                    rows={3}
                    className="mt-1 w-full rounded-lg border border-marketing-border bg-white px-3 py-2 text-sm text-marketing-text transition-colors focus:border-marketing-accent focus:outline-none focus:ring-2 focus:ring-marketing-accent/40"
                  />
                </div>
              </div>

              <div className="mt-6">
                <CTAButton type="submit" variant="primary" size="lg" fullWidth>
                  {c.form.submitLabel}
                </CTAButton>
                <ul className="mt-4 space-y-1">
                  {c.form.trustMicrocopy.map((line) => (
                    <li
                      key={line}
                      className="text-[11px] text-marketing-text-muted text-center"
                    >
                      {line}
                    </li>
                  ))}
                </ul>
              </div>
            </form>

            <aside className="rounded-xl border border-marketing-border bg-marketing-surface p-6 sm:p-8">
              <h3 className="text-marketing-h3 font-semibold text-marketing-primary">
                {c.demoCovers.title}
              </h3>
              <ul className="mt-6 space-y-4">
                {c.demoCovers.items.map((item, idx) => (
                  <li key={item} className="flex gap-3 text-[14px] text-marketing-text">
                    <span
                      aria-hidden="true"
                      className="mt-0.5 inline-flex h-6 w-6 flex-none items-center justify-center rounded-full bg-marketing-accent/10 text-xs font-semibold text-marketing-accent"
                    >
                      {idx + 1}
                    </span>
                    <span className="leading-relaxed">{item}</span>
                  </li>
                ))}
              </ul>
            </aside>
          </div>
        </FadeIn>
      </Section>

      <Section spacing="lg" background="transparent">
        <FadeIn>
          <SectionHeader
            title="Other ways to start"
            align="center"
            narrow
          />
          <div className="mt-12 grid grid-cols-1 md:grid-cols-2 gap-6">
            <PathCard
              headline={c.secondaryPaths.signIn.headline}
              body={c.secondaryPaths.signIn.body}
              cta={c.secondaryPaths.signIn.cta}
              to={c.secondaryPaths.signIn.to}
            />
            <PathCard
              headline={c.secondaryPaths.seePlatform.headline}
              body={c.secondaryPaths.seePlatform.body}
              cta={c.secondaryPaths.seePlatform.cta}
              to={c.secondaryPaths.seePlatform.to}
            />
          </div>
        </FadeIn>
      </Section>

      <Section spacing="lg" background="muted">
        <FadeIn>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8 max-w-5xl mx-auto">
            {c.trustRow.map((statement) => (
              <p
                key={statement}
                className="text-[13px] text-marketing-text-muted leading-relaxed text-center md:text-left"
              >
                {statement}
              </p>
            ))}
          </div>
        </FadeIn>
      </Section>
    </PublicLayout>
  );
};

interface TextFieldProps {
  id: string;
  label: string;
  placeholder?: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  type?: string;
  autoComplete?: string;
  required?: boolean;
}

const TextField: React.FC<TextFieldProps> = ({
  id,
  label,
  placeholder,
  value,
  onChange,
  type = 'text',
  autoComplete,
  required,
}) => (
  <div>
    <label
      htmlFor={id}
      className="block text-sm font-medium text-marketing-primary"
    >
      {label}
      {required && <span aria-hidden="true" className="ml-0.5 text-[#dc2626]">*</span>}
    </label>
    <input
      id={id}
      type={type}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      autoComplete={autoComplete}
      required={required}
      className="mt-1 w-full rounded-lg border border-marketing-border bg-white px-3 py-2 text-sm text-marketing-text transition-colors focus:border-marketing-accent focus:outline-none focus:ring-2 focus:ring-marketing-accent/40"
    />
  </div>
);

interface PathCardProps {
  headline: string;
  body: string;
  cta: string;
  to: string;
}

const PathCard: React.FC<PathCardProps> = ({ headline, body, cta, to }) => (
  <div className="rounded-xl border border-marketing-border bg-marketing-surface p-6 sm:p-8">
    <h3 className="text-[18px] font-semibold text-marketing-primary">{headline}</h3>
    <p className="mt-2 text-[14px] text-marketing-text-muted leading-relaxed">
      {body}
    </p>
    <div className="mt-6">
      <CTAButton to={to} variant="outline" size="md">
        {cta}
      </CTAButton>
    </div>
  </div>
);
