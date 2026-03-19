import React from 'react';
import { PublicLayout } from '../../components/public';
import {
  Section,
  SectionHeader,
  HeroSurface,
  TrustContentBlock,
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
      {/* 1. HERO — split layout, mock to the right / below */}
      <Section spacing="lg" background="transparent" fillViewport>
        <div className="flex flex-col lg:grid lg:grid-cols-[1.4fr,1fr] lg:items-center gap-10 lg:gap-12">
          <div className="min-w-0">
            <HeroSurface
              title={c.hero.headline}
              subtitle={c.hero.subheadline}
              actions={
                <>
                  <CTAButton to={buildRoute('access')} variant="primary" size="lg">
                    {c.hero.primaryCta}
                  </CTAButton>
                  <CTAButton to={buildRoute('trust')} variant="outline" size="lg">
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

      {/* 2. PRODUCT DEFINITION */}
      <Section spacing="lg" background="muted">
        <SectionHeader
          title={c.productDefinition.title}
          subtitle={c.productDefinition.body}
          align="center"
          narrow
        />
      </Section>

      {/* 3. INSIDE THE PRODUCT — 3 blocks */}
      <Section spacing="lg" background="transparent">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-4xl mx-auto">
          {c.insideProduct.blocks.map((block) => (
            <TrustContentBlock
              key={block.title}
              title={block.title}
              body={block.body}
            />
          ))}
        </div>
      </Section>

      {/* 4. CTA — no Why ReloPass on Platform */}
      <Section spacing="lg" background="muted">
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
