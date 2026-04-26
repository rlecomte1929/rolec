import React from 'react';
import { PublicLayout } from '../../components/public';
import {
  Section,
  SectionHeader,
  AccessOptionCard,
  BulletBlock,
  InlineDemoForm,
  FadeIn,
} from '../../components/marketing';
import { buildRoute } from '../../navigation/routes';
import { useDemoBooking } from '../../hooks/useDemoBooking';
import { accessContent } from './accessContent';

export const AccessPage: React.FC = () => {
  const { open: openDemoBooking } = useDemoBooking();
  const c = accessContent;

  return (
    <PublicLayout>
      {/* 1. HERO: Decision prompt */}
      <Section spacing="lg" background="transparent" fillViewport>
        <div className="max-w-2xl mx-auto text-center">
          <SectionHeader
            eyebrow={c.hero.eyebrow}
            title={c.hero.headline}
            subtitle={c.hero.subheadline}
            align="center"
            narrow
            as="h1"
          />
        </div>
      </Section>

      {/* 2. THREE OPTIONS: Book a demo primary for buyers */}
      <Section spacing="lg" background="muted" className="py-20 sm:py-24 md:py-28">
        <FadeIn>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto px-4 sm:px-6">
            <AccessOptionCard
              label={c.options.bookDemo.label}
              description={c.options.bookDemo.description}
              cta={c.options.bookDemo.cta}
              onClick={() => openDemoBooking('access-page')}
              variant="primary"
              trustMicrocopy={c.hero.trustMicrocopy}
            />
            <AccessOptionCard
              label={c.options.signIn.label}
              description={c.options.signIn.description}
              cta={c.options.signIn.cta}
              to={`${buildRoute('auth')}?mode=login`}
              variant="outline"
            />
            <AccessOptionCard
              label={c.options.createAccount.label}
              description={c.options.createAccount.description}
              cta={c.options.createAccount.cta}
              to={`${buildRoute('auth')}?mode=register`}
              variant="outline"
            />
          </div>
        </FadeIn>

        {/* 3. WHAT THE DEMO COVERS */}
        <FadeIn>
          <div className="mt-16 sm:mt-20 max-w-xl mx-auto">
            <h2 className="text-marketing-h3 font-semibold text-marketing-primary text-center">
              {c.demoCover.title}
            </h2>
            <BulletBlock items={c.demoCover.bullets} className="mt-6" />
          </div>
        </FadeIn>

        {/* 4. INLINE BOOKING FORM */}
        <FadeIn>
          <InlineDemoForm />
        </FadeIn>

        <FadeIn>
          {c.closingCta && (
            <p className="mt-16 sm:mt-20 text-marketing-body-lg font-semibold text-marketing-primary text-center max-w-2xl mx-auto leading-relaxed">
              {c.closingCta}
            </p>
          )}

          {/* 5. REASSURANCE */}
          <p className="mt-6 text-base text-marketing-text-muted text-center max-w-xl mx-auto leading-relaxed">
            {c.reassurance}
          </p>
        </FadeIn>
      </Section>
    </PublicLayout>
  );
};
