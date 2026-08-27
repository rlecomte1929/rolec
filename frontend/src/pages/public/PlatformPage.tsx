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
import { CasePreviewMock } from '../../components/CasePreviewMock';
import { buildRoute } from '../../navigation/routes';
import { useDemoBooking } from '../../hooks/useDemoBooking';
import { usePageMeta } from '../../hooks/usePageMeta';
import { platformContent } from './platformContent';

export const PlatformPage: React.FC = () => {
  usePageMeta({
    title: 'The Platform · ReloPass',
    description: 'Every relocation on one system of record. Cases, documents, providers, and progress in one place.',
    ogUrl: 'https://www.relopass.com/platform',
  });

  const { open: openDemoBooking } = useDemoBooking();
  const c = platformContent;

  return (
    <PublicLayout>
      {/* 1. HERO: split layout, mock to the right / below */}
      <Section spacing="lg" background="transparent" fillViewport>
        <div className="flex flex-col lg:grid lg:grid-cols-[1.4fr,1fr] lg:items-center gap-10 lg:gap-12">
          <div className="min-w-0">
            <HeroSurface
              eyebrow={c.hero.eyebrow}
              title={c.hero.headline}
              subtitle={c.hero.subheadline}
              trustMicrocopy={c.hero.trustMicrocopy}
              actions={
                <>
                  <CTAButton onClick={() => openDemoBooking('platform-hero')} variant="primary" size="lg">
                    {c.hero.primaryCta}
                  </CTAButton>
                  {/* The label is 'Sign in' (platformContent.ts hero.secondaryCta), so it must
                      go to the login screen. It pointed at /how-it-works, dropping anyone
                      trying to log in from this page onto a marketing page instead. Same
                      target as the footer CTA's sign-in below. */}
                  <CTAButton to={`${buildRoute('auth')}?mode=login`} variant="outline" size="lg">
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
        <FadeIn>
          <SectionHeader
            title={c.productDefinition.title}
            subtitle={c.productDefinition.body}
            align="center"
            narrow
          />
        </FadeIn>
      </Section>

      {/* 3. INSIDE THE PRODUCT: 3 blocks */}
      <Section spacing="lg" background="transparent">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10 lg:gap-12 max-w-6xl mx-auto">
          {c.insideProduct.blocks.map((block, i) => (
            <FadeIn key={block.title} delay={i * 80}>
              <div>
                {'image' in block && block.image && (
                  <img
                    src={block.image}
                    alt={'imageAlt' in block ? block.imageAlt : ''}
                    loading="lazy"
                    className="w-full rounded-[8px] shadow-[0_4px_16px_rgba(0,0,0,0.08)] mb-4 transition-transform duration-300 ease-out hover:scale-[1.02]"
                  />
                )}
                <TrustContentBlock title={block.title} body={block.body} />
              </div>
            </FadeIn>
          ))}
        </div>
      </Section>

      {/* 4. SPLIT: HR view vs Employee view */}
      <Section spacing="lg" background="muted" className="bg-[#f7f8fa]">
        <FadeIn>
          <SectionHeader
            title={c.splitSection.title}
            subtitle={c.splitSection.subtitle}
            align="center"
            narrow
          />
          <div className="mt-12 max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-8">
            {[c.splitSection.hrView, c.splitSection.employeeView].map((view) => (
              <div key={view.label}>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-[#0d9488] mb-3">
                  {view.label}
                </p>
                <img
                  src={view.image}
                  alt={view.caption}
                  loading="lazy"
                  className="w-full rounded-[10px] shadow-[0_8px_32px_rgba(0,0,0,0.10)] transition-transform duration-300 ease-out hover:scale-[1.02]"
                />
                <p className="mt-3 text-[13px] text-[#6b7280]">{view.caption}</p>
              </div>
            ))}
          </div>
        </FadeIn>
      </Section>

      {/* 5. CTA: no Why ReloPass on Platform */}
      <Section spacing="lg" background="muted">
        <FadeIn>
          <CTAPanel
            title={c.cta.headline}
            variant="surface"
            primaryAction={
              <CTAButton onClick={() => openDemoBooking('platform-final')} variant="primary" size="lg">
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
