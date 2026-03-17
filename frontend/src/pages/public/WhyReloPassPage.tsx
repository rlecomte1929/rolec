import React from 'react';
import { PublicLayout } from '../../components/public';
import {
  Section,
  SectionHeader,
  HeroSurface,
  TrustContentBlock,
  BulletBlock,
  CTAPanel,
  CTAButton,
} from '../../components/marketing';
import { buildRoute } from '../../navigation/routes';
import { whyReloPassContent } from './whyReloPassContent';

export const WhyReloPassPage: React.FC = () => {
  const c = whyReloPassContent;

  return (
    <PublicLayout>
      {/* 1. HERO — Names the mess, offers a cleaner path */}
      <Section spacing="lg" background="transparent" fillViewport>
        <HeroSurface
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
        />
      </Section>

      {/* 2. CURRENT REALITY — What teams recognise */}
      <Section spacing="lg" background="muted">
        <SectionHeader title={c.currentReality.title} align="center" />
        <div className="mt-10 max-w-2xl mx-auto">
          <BulletBlock items={c.currentReality.items} />
          {c.currentReality.supportingLine && (
            <p className="mt-6 text-sm text-marketing-text-subtle leading-relaxed text-center">
              {c.currentReality.supportingLine}
            </p>
          )}
        </div>
      </Section>

      {/* 3. WHY RELOPASS IS DIFFERENT — Differentiation blocks */}
      <Section spacing="lg" background="transparent">
        <SectionHeader title={c.differentiation.title} align="center" />
        <div className="mt-10 grid grid-cols-1 md:grid-cols-2 gap-8 lg:gap-12 max-w-4xl mx-auto">
          {c.differentiation.blocks.map((block, i) => (
            <TrustContentBlock
              key={i}
              title={block.title}
              body={block.body}
            />
          ))}
        </div>
      </Section>

      {/* 4. WHAT CHANGES FOR YOUR TEAM — Outcome bullets */}
      <Section spacing="lg" background="muted">
        <SectionHeader title={c.outcomes.title} align="center" />
        <div className="mt-10 max-w-2xl mx-auto">
          <BulletBlock items={c.outcomes.items} />
          {c.outcomes.supportingLine && (
            <p className="mt-6 text-sm text-marketing-text-subtle leading-relaxed text-center">
              {c.outcomes.supportingLine}
            </p>
          )}
        </div>
      </Section>

      {/* 5. CTA — See why teams make the switch */}
      <Section spacing="lg" background="transparent">
        <CTAPanel
          title={c.cta.headline}
          variant="surface"
          primaryAction={
            <CTAButton to={buildRoute('access')} variant="primary" size="lg">
              {c.cta.options.demo}
            </CTAButton>
          }
          secondaryAction={
            <CTAButton to={buildRoute('trust')} variant="outline" size="lg">
              {c.cta.options.howItWorks}
            </CTAButton>
          }
          tertiaryAction={
            <CTAButton to={`${buildRoute('auth')}?mode=login`} variant="ghost" size="lg">
              {c.cta.options.signIn}
            </CTAButton>
          }
        />
      </Section>
    </PublicLayout>
  );
};
