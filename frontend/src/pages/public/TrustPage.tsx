import React from 'react';
import { PublicLayout } from '../../components/public';
import {
  Section,
  SectionHeader,
  HeroSurface,
  TrustContentBlock,
  BulletBlock,
  SystemFlowDiagram,
  CTAPanel,
  CTAButton,
} from '../../components/marketing';
import { buildRoute } from '../../navigation/routes';
import { trustContent } from './trustContent';

export const TrustPage: React.FC = () => {
  const c = trustContent;

  return (
    <PublicLayout>
      {/* 1. HERO */}
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

      {/* 2. ONE CASE, CLEAR STEPS — Flow diagram lives here */}
      <Section spacing="lg" background="muted">
        <div className="max-w-2xl mx-auto">
          <TrustContentBlock
            title={c.process.title}
            body={c.process.body}
            closing={c.process.supportingLine}
          />
        </div>
        <div className="mt-10 max-w-4xl mx-auto">
          <SystemFlowDiagram nodes={c.process.flow} />
        </div>
      </Section>

      {/* 3. EVERYTHING STAYS IN CONTEXT — Merged visibility + requirements */}
      <Section spacing="lg" background="transparent">
        <div className="max-w-2xl mx-auto">
          <TrustContentBlock
            title={c.inContext.title}
            body={c.inContext.body}
          />
        </div>
        <div className="mt-10 max-w-2xl mx-auto">
          <BulletBlock items={c.inContext.items} />
        </div>
      </Section>

      {/* 4. THE PROCESS IS GUIDED — Short paragraph only */}
      <Section spacing="lg" background="muted">
        <div className="max-w-2xl mx-auto">
          <TrustContentBlock
            title={c.boundaries.title}
            body={c.boundaries.body}
          />
        </div>
      </Section>

      {/* 5. CTA — Walk through a real case only on this page */}
      <Section spacing="lg" background="transparent">
        <CTAPanel
          title={c.cta.headline}
          subtitle={c.cta.microCopy}
          variant="surface"
          primaryAction={
            <CTAButton to={buildRoute('access')} variant="primary" size="lg">
              {c.cta.options.demo}
            </CTAButton>
          }
          secondaryAction={
            <CTAButton to={buildRoute('platform')} variant="outline" size="lg">
              {c.cta.options.seePlatform}
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
