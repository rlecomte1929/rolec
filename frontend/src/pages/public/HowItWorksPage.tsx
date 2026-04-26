import React from 'react';
import { PublicLayout } from '../../components/public';
import {
  Section,
  HeroSurface,
  CTAPanel,
  CTAButton,
  FadeIn,
} from '../../components/marketing';
import { useDemoBooking } from '../../hooks/useDemoBooking';
import { howItWorksContent } from './howItWorksContent';

export const HowItWorksPage: React.FC = () => {
  const { open: openDemoBooking } = useDemoBooking();
  const c = howItWorksContent;

  return (
    <PublicLayout>
      <Section spacing="lg" background="transparent" fillViewport>
        <HeroSurface
          eyebrow={c.hero.eyebrow}
          title={c.hero.headline}
          subtitle={c.hero.subheadline}
          trustMicrocopy={c.hero.trustMicrocopy}
        />
      </Section>

      <Section spacing="lg" background="muted">
        <div className="relative max-w-5xl mx-auto px-4 sm:px-6 space-y-20 lg:space-y-28">
          <div
            className="hidden md:block absolute left-1/2 top-8 bottom-8 w-px bg-marketing-accent/30 -translate-x-1/2"
            aria-hidden="true"
          />
          {c.steps.map((step, idx) => {
            const imageRight = idx % 2 === 0;
            return (
              <FadeIn key={step.number} delay={idx * 100}>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12 items-center">
                  <div className={imageRight ? '' : 'lg:order-2'}>
                    <p className="text-[11px] font-bold uppercase tracking-wider text-[#0d9488]">
                      {step.number}
                    </p>
                    <h2 className="mt-3 text-[20px] font-bold text-marketing-primary leading-tight">
                      {step.title}
                    </h2>
                    <p className="mt-3 text-[14px] text-marketing-text-muted leading-relaxed">
                      {step.body}
                    </p>
                  </div>
                  <div className={imageRight ? '' : 'lg:order-1'}>
                    <img
                      src={step.image}
                      alt={step.imageAlt}
                      loading="lazy"
                      className="w-full rounded-[10px] shadow-[0_8px_32px_rgba(0,0,0,0.10)] transition-transform duration-300 ease-out hover:scale-[1.02]"
                    />
                  </div>
                </div>
              </FadeIn>
            );
          })}
        </div>
      </Section>

      <Section spacing="lg" background="transparent">
        <FadeIn>
          <CTAPanel
            title={c.cta.headline}
            variant="surface"
            actions={
              <div className="flex flex-col items-center gap-3">
                <CTAButton
                  onClick={() => openDemoBooking('how-it-works-final')}
                  variant="primary"
                  size="lg"
                >
                  {c.cta.primaryCta}
                </CTAButton>
                <p className="text-[11px] text-marketing-text-muted">
                  {c.cta.trustMicrocopy}
                </p>
              </div>
            }
          />
        </FadeIn>
      </Section>
    </PublicLayout>
  );
};
