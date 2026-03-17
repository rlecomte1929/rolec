import React from 'react';
import { PublicLayout } from '../../components/public';
import {
  Section,
  SectionHeader,
  HeroSurface,
  CTAPanel,
  CTAButton,
} from '../../components/marketing';
import { CasePreviewMock } from '../../components/CasePreviewMock';
import { buildRoute } from '../../navigation/routes';
import { platformContent } from './platformContent';

export const PlatformPage: React.FC = () => {
  const c = platformContent;

  return (
    <PublicLayout>
      {/* 1. HERO — text left (desktop) / top (mobile); mock right (desktop) / below (mobile) */}
      <Section spacing="lg" background="transparent" fillViewport>
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-10 lg:gap-12">
          <div className="flex-1 min-w-0">
            <HeroSurface
              title={c.hero.headline}
              subtitle={c.hero.subheadline}
              actions={
                <>
                  <CTAButton to={buildRoute('access')} variant="primary" size="lg">
                    {c.hero.primaryCta}
                  </CTAButton>
                  <CTAButton to={buildRoute('why')} variant="outline" size="lg">
                    {c.hero.secondaryCta}
                  </CTAButton>
                </>
              }
            />
          </div>
          <div className="flex-shrink-0 flex justify-center lg:justify-end">
            <CasePreviewMock className="lg:max-w-sm" />
          </div>
        </div>
      </Section>

      {/* 2. SYSTEM — What the product is */}
      <Section spacing="lg" background="muted">
        <SectionHeader
          title={c.system.title}
          subtitle={c.system.body}
          align="center"
          narrow
        />
      </Section>

      {/* 3. CTA */}
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
            <CTAButton to={buildRoute('why')} variant="outline" size="lg">
              {c.cta.options.whyReloPass}
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
