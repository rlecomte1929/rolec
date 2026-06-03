import React from 'react';
import { PublicLayout } from '../components/public';
import {
  Section,
  SectionHeader,
  HeroSurface,
  FeatureCard,
  CTAPanel,
  CTAButton,
  TrustDifferentiation,
  FadeIn,
} from '../components/marketing';
import { buildRoute } from '../navigation/routes';
import { useRegisterNav } from '../navigation/registry';
import { useDemoBooking } from '../hooks/useDemoBooking';
import { usePageMeta } from '../hooks/usePageMeta';
import { landingContent } from './landing/landingContent';

export const Landing: React.FC = () => {
  useRegisterNav('Landing', [
    { label: 'Book a demo', routeKey: 'access' },
    { label: 'See the platform', routeKey: 'platform' },
  ]);

  usePageMeta({
    title: 'ReloPass · The operating layer for cross-border relocation',
    description: 'Cases, documents, providers, and status on one record. Built for HR and mobility teams.',
    ogUrl: 'https://www.relopass.com',
  });

  const { open: openDemoBooking } = useDemoBooking();
  const c = landingContent;

  // AIQ-757: `/` renders the marketing homepage for everyone — including
  // authenticated users — to match the other public pages (/platform,
  // /how-it-works, /get-started), which never redirect. The 404.html
  // `?__redirect=<path>` deep-link fallback is still honoured globally by
  // <QueryRedirect /> in App.tsx, so removing the role-home bounce here does
  // not break deep links.

  return (
    <PublicLayout>
      {/* 1. HERO: Two columns: text + CTAs left, visual right */}
      <Section spacing="lg" background="transparent" fillViewport>
        <HeroSurface
          eyebrow={c.hero.eyebrow}
          title={c.hero.headline}
          subtitle={c.hero.subheadline}
          brandPromise={c.hero.brandPromise}
          trustMicrocopy={c.hero.trustMicrocopy}
          actions={
            <>
              <CTAButton onClick={() => openDemoBooking('landing-hero')} variant="primary" size="lg">
                {c.hero.primaryCta}
              </CTAButton>
              <CTAButton to={buildRoute('platform')} variant="outline" size="lg">
                {c.hero.secondaryCta}
              </CTAButton>
            </>
          }
          visual={
            <img
              src="/screenshot-hero-case-card.png"
              alt="ReloPass case view showing Paul Doe's France to Singapore relocation — status, milestones, documents, and provider activity on one record."
              width={600}
              height={360}
              loading="eager"
              className="hidden md:block w-full max-w-[600px] h-auto rounded-[12px] shadow-[0_8px_32px_rgba(0,0,0,0.10)] transition-transform duration-300 ease-out hover:scale-[1.02]"
            />
          }
        />
      </Section>

      {/* 2. PROBLEM: 3 cards */}
      <Section spacing="lg" background="muted">
        <FadeIn>
          <SectionHeader
            title={c.problem.title}
            align="center"
          />
        </FadeIn>
        <div className="mt-12 sm:mt-16 max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
          {c.problem.cards.map((card, i) => (
            <FadeIn key={card.title} delay={i * 80}>
              <FeatureCard
                title={card.title}
                description={card.body}
              />
            </FadeIn>
          ))}
        </div>
      </Section>

      {/* 3. SOLUTION: 4 blocks */}
      <Section spacing="lg" background="transparent">
        <FadeIn>
          <SectionHeader
            eyebrow={c.solution.sectionHeader}
            title={c.solution.title}
            align="center"
          />
        </FadeIn>
        <div className="mt-12 sm:mt-16 max-w-5xl mx-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 lg:gap-8">
          {c.solution.blocks.map((block, i) => (
            <FadeIn key={block.title} delay={i * 80}>
              <FeatureCard
                title={block.title}
                description={block.body}
                className="bg-marketing-surface"
              />
            </FadeIn>
          ))}
        </div>
      </Section>

      {/* 4. DIFFERENTIATION / TRUST: Left text, right checklist */}
      <Section spacing="lg" background="muted">
        <FadeIn>
          <div className="max-w-5xl mx-auto">
          {c.trust.categoryBoundary && (
            <div className="mb-10 text-center">
              <p className="text-marketing-body-lg font-bold text-marketing-primary">
                {c.trust.categoryBoundary.positive}
              </p>
              {c.trust.categoryBoundary.negatives.map((line) => (
                <p key={line} className="text-marketing-body text-marketing-text-muted font-medium">
                  {line}
                </p>
              ))}
            </div>
          )}
          <TrustDifferentiation
            title={c.trust.title}
            body={c.trust.body}
            checklist={c.trust.checklist}
          />
          </div>
        </FadeIn>
      </Section>

      {/* 5. FINAL CTA: Centered, compact, decisive */}
      <Section spacing="lg" background="transparent">
        <FadeIn>
          <CTAPanel
            title={c.finalCta.headline}
            subtitle={c.finalCta.microCopy}
            variant="surface"
            primaryAction={
              <CTAButton onClick={() => openDemoBooking('landing-final')} variant="primary" size="lg">
                {c.finalCta.options.demo}
              </CTAButton>
            }
            secondaryAction={
              <CTAButton to={buildRoute('platform')} variant="outline" size="lg">
                {c.finalCta.options.platform}
              </CTAButton>
            }
            tertiaryAction={
              <CTAButton to={`${buildRoute('auth')}?mode=login`} variant="ghost" size="lg">
                {c.finalCta.options.signIn}
              </CTAButton>
            }
          />
        </FadeIn>
      </Section>
    </PublicLayout>
  );
};
