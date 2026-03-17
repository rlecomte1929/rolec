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
  LandingProductStrip,
} from '../components/marketing';
import { buildRoute } from '../navigation/routes';
import { useRegisterNav } from '../navigation/registry';
import { landingContent } from './landing/landingContent';

export const Landing: React.FC = () => {
  useRegisterNav('Landing', [
    { label: 'Book a demo', routeKey: 'access' },
    { label: 'See the platform', routeKey: 'platform' },
  ]);

  const c = landingContent;

  return (
    <PublicLayout>
      {/* 1. HERO — Two columns: text + CTAs left, visual right */}
      <Section spacing="lg" background="transparent" fillViewport>
        <HeroSurface
          eyebrow={c.hero.eyebrow}
          title={c.hero.headline}
          subtitle={c.hero.subheadline}
          actions={
            <>
              <CTAButton to={buildRoute('access')} variant="primary" size="lg">
                {c.hero.primaryCta}
              </CTAButton>
              <CTAButton to={buildRoute('platform')} variant="outline" size="lg">
                {c.hero.secondaryCta}
              </CTAButton>
            </>
          }
          visual={<LandingProductStrip blocks={c.productStrip.blocks} />}
        />
      </Section>

      {/* 2. PROBLEM — 3 cards */}
      <Section spacing="lg" background="muted">
        <SectionHeader
          title={c.problem.title}
          align="center"
        />
        <div className="mt-12 sm:mt-16 max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
          {c.problem.cards.map((card) => (
            <FeatureCard
              key={card.title}
              title={card.title}
              description={card.body}
            />
          ))}
        </div>
      </Section>

      {/* 3. SOLUTION — 4 blocks */}
      <Section spacing="lg" background="transparent">
        <SectionHeader
          title={c.solution.title}
          align="center"
        />
        <div className="mt-12 sm:mt-16 max-w-5xl mx-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 lg:gap-8">
          {c.solution.blocks.map((block) => (
            <FeatureCard
              key={block.title}
              title={block.title}
              description={block.body}
              className="bg-marketing-surface"
            />
          ))}
        </div>
      </Section>

      {/* 4. DIFFERENTIATION / TRUST — Left text, right checklist */}
      <Section spacing="lg" background="muted">
        <div className="max-w-5xl mx-auto">
        <TrustDifferentiation
          title={c.trust.title}
          body={c.trust.body}
          checklist={c.trust.checklist}
        />
        </div>
      </Section>

      {/* 5. FINAL CTA — Centered, compact, decisive */}
      <Section spacing="lg" background="transparent">
        <CTAPanel
          title={c.finalCta.headline}
          subtitle={c.finalCta.microCopy}
          variant="surface"
          primaryAction={
            <CTAButton to={buildRoute('access')} variant="primary" size="lg">
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
      </Section>
    </PublicLayout>
  );
};
