import React from 'react';
import { PublicLayout } from '../../components/public';
import {
  Section,
  SectionHeader,
  HeroSurface,
  FeatureCard,
  CTAPanel,
  CTAButton,
  TrustDifferentiation,
  Pill,
  FadeIn,
} from '../../components/marketing';
import { buildRoute } from '../../navigation/routes';
import { useDemoBooking } from '../../hooks/useDemoBooking';
import { usePageMeta } from '../../hooks/usePageMeta';
import {
  complianceContent,
  ENTERPRISE_CONTACT_EMAIL,
} from './complianceContent';

export const CompliancePage: React.FC = () => {
  // [AIQ-1513] Title/description previously read "EU AI Act Ready" and "controls for
  // high-risk HR AI" — a status claim we cannot support, and a misclassification (our
  // assessment found limited-risk, not high-risk). This is the most syndicated copy we
  // have (search results, link previews), so it must describe controls, not status.
  usePageMeta({
    title: 'Trust & AI oversight · ReloPass',
    description:
      'How AI works at ReloPass: a human reviews every recommendation, each decision is logged with the AI output behind it, answers are grounded in your policy, and personal details are masked before any AI sees them.',
    ogUrl: 'https://www.relopass.com/compliance',
  });

  const { open: openDemoBooking } = useDemoBooking();
  const c = complianceContent;

  return (
    <PublicLayout>
      {/* 1. HERO */}
      <Section spacing="lg" background="transparent" fillViewport>
        <HeroSurface
          eyebrow={c.hero.eyebrow}
          title={c.hero.headline}
          subtitle={c.hero.subheadline}
          trustMicrocopy={c.hero.trustMicrocopy}
          aside={
            <Pill variant="accent" size="md">
              {c.hero.badge}
            </Pill>
          }
          actions={
            <>
              {/* [AIQ-1513] The downloadable compliance one-pager is gone — that asset made a
                  regulatory-status claim we cannot support. Demo is now the primary action. */}
              <CTAButton onClick={() => openDemoBooking('compliance-hero')} variant="primary" size="lg">
                {c.finalCta.demoCtaLabel}
              </CTAButton>
            </>
          }
        />
      </Section>

      {/* 2. WHAT "READY" MEANS — sets honest expectations */}
      <Section spacing="lg" background="muted">
        <FadeIn>
          <p className="text-center text-xs font-semibold uppercase tracking-wider text-marketing-accent mb-10">
            {c.readiness.sectionHeader}
          </p>
          <div className="max-w-5xl mx-auto">
            <TrustDifferentiation
              title={c.readiness.title}
              body={c.readiness.body}
              checklist={c.readiness.checklist}
            />
          </div>
        </FadeIn>
      </Section>

      {/* 2b. AI SYSTEMS INVENTORY — EU AI Act transparency (Art. 13) */}
      <Section spacing="lg" background="transparent">
        <FadeIn>
          <SectionHeader
            eyebrow={c.aiSystems.sectionHeader}
            title={c.aiSystems.title}
            subtitle={c.aiSystems.body}
            align="center"
          />
        </FadeIn>
        <div className="mt-12 sm:mt-16 max-w-5xl mx-auto grid grid-cols-1 sm:grid-cols-2 gap-6 lg:gap-8">
          {c.aiSystems.cards.map((card, i) => (
            <FadeIn key={card.title} delay={i * 80}>
              <FeatureCard title={card.title} description={card.body} className="h-full" />
            </FadeIn>
          ))}
        </div>
      </Section>

      {/* 3. HUMAN OVERSIGHT — the real Art. 14 flow */}
      <Section spacing="lg" background="muted">
        <FadeIn>
          <SectionHeader
            eyebrow={c.oversight.sectionHeader}
            title={c.oversight.title}
            subtitle={c.oversight.body}
            align="center"
          />
        </FadeIn>
        <div className="mt-12 sm:mt-16 max-w-5xl mx-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 lg:gap-8">
          {c.oversight.steps.map((step, i) => (
            <FadeIn key={step.number} delay={i * 80}>
              <FeatureCard
                eyebrow={step.number}
                title={step.title}
                description={step.body}
                className="bg-marketing-surface h-full"
              />
            </FadeIn>
          ))}
        </div>
      </Section>

      {/* 4. TRANSPARENCY & DATA PROCESSING */}
      <Section spacing="lg" background="transparent">
        <FadeIn>
          <SectionHeader
            eyebrow={c.transparency.sectionHeader}
            title={c.transparency.title}
            align="center"
          />
        </FadeIn>
        <div className="mt-12 sm:mt-16 max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
          {c.transparency.cards.map((card, i) => (
            <FadeIn key={card.title} delay={i * 80}>
              <FeatureCard title={card.title} description={card.body} className="h-full" />
            </FadeIn>
          ))}
        </div>
      </Section>

      {/* 4b. DATA GOVERNANCE & GDPR */}
      <Section spacing="lg" background="muted">
        <FadeIn>
          <SectionHeader
            eyebrow={c.dataGovernance.sectionHeader}
            title={c.dataGovernance.title}
            align="center"
          />
        </FadeIn>
        <div className="mt-12 sm:mt-16 max-w-5xl mx-auto grid grid-cols-1 sm:grid-cols-2 gap-6 lg:gap-8">
          {c.dataGovernance.cards.map((card, i) => (
            <FadeIn key={card.title} delay={i * 80}>
              <FeatureCard title={card.title} description={card.body} className="h-full" />
            </FadeIn>
          ))}
        </div>
      </Section>

      {/* 5. AUDIT TRAIL */}
      <Section spacing="lg" background="transparent">
        <FadeIn>
          <SectionHeader
            eyebrow={c.audit.sectionHeader}
            title={c.audit.title}
            subtitle={c.audit.body}
            align="center"
            narrow
          />
        </FadeIn>
      </Section>

      {/* 6. FINAL CTA + enterprise contact + disclaimer */}
      <Section spacing="lg" background="muted">
        <FadeIn>
          <CTAPanel
            title={c.finalCta.headline}
            subtitle={c.finalCta.microCopy}
            variant="surface"
            primaryAction={
              <CTAButton onClick={() => openDemoBooking('compliance-final')} variant="primary" size="lg">
                {c.finalCta.demoCtaLabel}
              </CTAButton>
            }
            secondaryAction={
              <CTAButton href={`mailto:${ENTERPRISE_CONTACT_EMAIL}`} variant="outline" size="lg">
                {c.finalCta.enterpriseLine}
              </CTAButton>
            }
            tertiaryAction={
              <CTAButton to={buildRoute('security')} variant="ghost" size="lg">
                Security &amp; data
              </CTAButton>
            }
          />
        </FadeIn>
        <FadeIn>
          <div className="mt-8 max-w-3xl mx-auto text-center space-y-4">
            <p className="text-marketing-body text-marketing-text-muted">
              {c.finalCta.enterpriseLine}{' '}
              <a
                href={`mailto:${ENTERPRISE_CONTACT_EMAIL}`}
                className="font-semibold text-marketing-accent underline underline-offset-2"
              >
                {ENTERPRISE_CONTACT_EMAIL}
              </a>
            </p>
            <p className="text-xs leading-relaxed text-marketing-text-subtle">
              {c.disclaimer}
            </p>
          </div>
        </FadeIn>
      </Section>
    </PublicLayout>
  );
};
