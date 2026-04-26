import React from 'react';
import { PublicLayout } from '../../components/public';
import {
  Section,
  SectionHeader,
  HeroSurface,
  TrustContentBlock,
  CTAPanel,
  CTAButton,
  FadeIn,
} from '../../components/marketing';
import { buildRoute } from '../../navigation/routes';
import { useDemoBooking } from '../../hooks/useDemoBooking';
import { whyReloPassContent } from './whyReloPassContent';

export const WhyReloPassPage: React.FC = () => {
  const { open: openDemoBooking } = useDemoBooking();
  const c = whyReloPassContent;

  return (
    <PublicLayout>
      {/* 1. HERO: Names the mess, offers a cleaner path */}
      <Section spacing="lg" background="transparent" fillViewport>
        <HeroSurface
          eyebrow={c.hero.eyebrow}
          title={c.hero.headline}
          subtitle={c.hero.subheadline}
          trustMicrocopy={c.hero.trustMicrocopy}
          actions={
            <>
              <CTAButton onClick={() => openDemoBooking('why-hero')} variant="primary" size="lg">
                {c.hero.primaryCta}
              </CTAButton>
              <CTAButton to={buildRoute('platform')} variant="outline" size="lg">
                {c.hero.secondaryCta}
              </CTAButton>
            </>
          }
        />
      </Section>

      {/* 2. CURRENT REALITY */}
      <Section spacing="lg" background="muted">
        <FadeIn>
          <SectionHeader title={c.currentReality.title} align="center" />
        </FadeIn>
        <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-2xl mx-auto">
          {c.currentReality.items.map((item, i) => (
            <FadeIn key={i} delay={i * 80}>
              <div className="rounded-xl border border-marketing-border bg-white px-6 py-5 transition-all duration-200 ease-out hover:-translate-y-1 hover:shadow-md hover:border-marketing-accent/40">
                <p className="text-marketing-body font-semibold text-marketing-primary leading-snug">
                  {item}
                </p>
              </div>
            </FadeIn>
          ))}
        </div>
        {c.currentReality.supportingLine && (
          <FadeIn>
            <p className="mt-8 text-sm text-marketing-text-subtle leading-relaxed text-center max-w-xl mx-auto">
              {c.currentReality.supportingLine}
            </p>
          </FadeIn>
        )}
      </Section>

      {/* 2b. THESIS */}
      <Section spacing="lg" background="transparent">
        <FadeIn>
          <div className="max-w-2xl mx-auto text-center">
            <div className="w-10 h-1 bg-marketing-accent rounded-full mx-auto mb-6" />
            <p className="text-2xl md:text-3xl font-bold text-marketing-primary leading-snug">
              {c.thesis}
            </p>
          </div>
        </FadeIn>
      </Section>

      {/* 3. WHY RELOPASS IS DIFFERENT: Differentiation blocks */}
      <Section spacing="lg" background="transparent">
        <FadeIn>
          <SectionHeader title={c.differentiation.title} align="center" />
          {c.differentiation.categoryBoundary && (
            <div className="mt-8 max-w-2xl mx-auto text-center">
              <p className="text-2xl md:text-3xl font-bold text-marketing-accent leading-snug">
                {c.differentiation.categoryBoundary.positive}
              </p>
              <div className="mt-4 flex flex-col items-center gap-1">
                {c.differentiation.categoryBoundary.negatives.map((line) => (
                  <p key={line} className="text-marketing-body text-marketing-text-muted font-medium">
                    {line}
                  </p>
                ))}
              </div>
              {c.differentiation.productAnchor && (
                <p className="mt-8 text-marketing-body text-marketing-text-subtle italic border-l-2 border-marketing-accent pl-4 text-left max-w-lg mx-auto">
                  {c.differentiation.productAnchor}
                </p>
              )}
            </div>
          )}
        </FadeIn>
        <div className="mt-10 grid grid-cols-1 md:grid-cols-2 gap-8 lg:gap-12 max-w-4xl mx-auto">
          {c.differentiation.blocks.map((block, i) => (
            <FadeIn key={i} delay={i * 80}>
              <TrustContentBlock
                title={block.title}
                body={block.body}
              />
            </FadeIn>
          ))}
        </div>
      </Section>

      {/* 4. OUTCOMES */}
      <Section spacing="lg" background="muted">
        <FadeIn>
          <SectionHeader title={c.outcomes.title} align="center" />
          <div className="mt-10 max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-10 items-center">
            <div>
              <ul className="space-y-4">
                {c.outcomes.items.map((item, i) => (
                  <FadeIn key={i} delay={i * 80}>
                    <li className="flex items-start gap-3">
                      <span className="mt-1 w-2 h-2 rounded-full bg-marketing-accent flex-shrink-0" />
                      <p className="text-marketing-body font-semibold text-marketing-primary leading-snug">
                        {item}
                      </p>
                    </li>
                  </FadeIn>
                ))}
              </ul>
              {c.outcomes.supportingLine && (
                <p className="mt-6 text-sm text-marketing-text-subtle leading-relaxed">
                  {c.outcomes.supportingLine}
                </p>
              )}
            </div>
            {c.outcomes.image && (
              <img
                src={c.outcomes.image}
                alt={c.outcomes.imageAlt}
                className="w-full rounded-[10px] shadow-[0_8px_32px_rgba(0,0,0,0.10)] transition-transform duration-300 ease-out hover:scale-[1.02]"
                loading="lazy"
              />
            )}
          </div>
        </FadeIn>
      </Section>

      {/* 4b. PEAK-CONVICTION CTA: Strike right after outcomes */}
      <Section spacing="sm" background="transparent">
        <FadeIn>
          <CTAPanel
            title={c.peakCta.headline}
            variant="accent"
            primaryAction={
              <CTAButton onClick={() => openDemoBooking('why-outcomes')} variant="secondary" size="lg">
                {c.peakCta.primaryCta}
              </CTAButton>
            }
          />
        </FadeIn>
      </Section>

      {/* 5. CTA: See why teams make the switch */}
      <Section spacing="lg" background="transparent">
        <FadeIn>
          <CTAPanel
            title={c.cta.headline}
            variant="surface"
            primaryAction={
              <CTAButton onClick={() => openDemoBooking('why-final')} variant="primary" size="lg">
                {c.cta.options.demo}
              </CTAButton>
            }
            secondaryAction={
              <CTAButton to={buildRoute('howItWorks')} variant="outline" size="lg">
                {c.cta.options.howItWorks}
              </CTAButton>
            }
            tertiaryAction={
              <CTAButton to={`${buildRoute('auth')}?mode=login`} variant="ghost" size="lg">
                {c.cta.options.signIn}
              </CTAButton>
            }
          />
        </FadeIn>
      </Section>
    </PublicLayout>
  );
};
