import React from 'react';
import { PublicLayout } from '../../components/public';
import {
  Section,
  SectionHeader,
  AccessOptionCard,
} from '../../components/marketing';
import { buildRoute } from '../../navigation/routes';
import { accessContent } from './accessContent';

/** Placeholder for demo booking — wire to your flow when ready */
const DEMO_LINK = 'mailto:hello@relopass.com?subject=ReloPass%20Demo%20Request';

export const AccessPage: React.FC = () => {
  const c = accessContent;

  return (
    <PublicLayout>
      {/* 1. HERO — Decision prompt */}
      <Section spacing="lg" background="transparent" fillViewport>
        <div className="max-w-2xl mx-auto text-center">
          <SectionHeader
            title={c.hero.headline}
            subtitle={c.hero.subheadline}
            align="center"
            narrow
          />
        </div>
      </Section>

      {/* 2. THREE OPTIONS — Book a demo primary for buyers */}
      <Section spacing="lg" background="muted" className="py-20 sm:py-24 md:py-28">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto px-4 sm:px-6">
          <AccessOptionCard
            label={c.options.bookDemo.label}
            description={c.options.bookDemo.description}
            cta={c.options.bookDemo.cta}
            href={DEMO_LINK}
            variant="primary"
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

        {/* 3. REASSURANCE */}
        <p className="mt-12 sm:mt-14 text-base text-marketing-text-muted text-center max-w-xl mx-auto leading-relaxed">
          {c.reassurance}
        </p>
      </Section>
    </PublicLayout>
  );
};
