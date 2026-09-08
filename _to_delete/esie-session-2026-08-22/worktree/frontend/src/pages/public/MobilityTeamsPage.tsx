import React from 'react';
import { PublicLayout } from '../../components/public';
// Direct imports, NOT the components/marketing barrel. The barrel re-exports
// InlineDemoForm, which statically imports api/client -> supabaseAuth ->
// @supabase/supabase-js, whose realtime client throws on Node 20 (.nvmrc, what CI runs)
// and fails the prerender build. Importing one component through a barrel drags the
// whole barrel's graph in.
import { Section } from '../../components/marketing/Section';
import { HeroSurface } from '../../components/marketing/HeroSurface';
import { FadeIn } from '../../components/marketing/FadeIn';
import { CTAButton } from '../../components/marketing/CTAButton';
import { AdLeadForm } from '../../components/marketing/AdLeadForm';
import { useDemoBooking } from '../../hooks/useDemoBooking';
import { usePageMeta } from '../../hooks/usePageMeta';
import { useAdEngagementTracking } from '../../hooks/useAdEngagementTracking';
import { mobilityTeamsContent as c } from './adLandingContent';

/**
 * [AIQ-1783] `/mobility-teams` — segment A, the HR / mobility buyer.
 *
 * Paid-ad destination. Cold traffic at ~$3/click cannot go to the homepage; this page
 * answers one matched intent and nothing else.
 *
 * Deliberately omitted, per the task: pricing, long feature grids, and any visa or tax
 * outcome claim. Proof is three interface screenshots, not adjectives.
 */
export const MobilityTeamsPage: React.FC = () => {
  usePageMeta({ title: c.meta.title, description: c.meta.description, ogUrl: c.meta.ogUrl });
  useAdEngagementTracking('mobility-teams');
  const { open: openDemoBooking } = useDemoBooking();

  return (
    <PublicLayout>
      <Section spacing="lg" background="transparent">
        <HeroSurface
          eyebrow={c.hero.eyebrow}
          title={c.hero.headline}
          subtitle={c.hero.subheadline}
        />
      </Section>

      <Section spacing="lg" background="muted">
        <div className="mx-auto max-w-6xl space-y-16 px-4 sm:px-6 lg:space-y-24">
          {c.proof.map((anchor, idx) => {
            const imageRight = idx % 2 === 0;
            return (
              <FadeIn key={anchor.title} delay={idx * 100}>
                <div className="grid grid-cols-1 items-center gap-8 lg:grid-cols-2 lg:gap-12">
                  <div className={imageRight ? '' : 'lg:order-2'}>
                    <h2 className="text-[22px] font-bold leading-tight text-marketing-primary">
                      {anchor.title}
                    </h2>
                    <p className="mt-3 text-[14px] leading-relaxed text-marketing-text-muted">
                      {anchor.body}
                    </p>
                  </div>
                  <div className={imageRight ? '' : 'lg:order-1'}>
                    <img
                      src={anchor.image}
                      alt={anchor.imageAlt}
                      loading="lazy"
                      decoding="async"
                      className="w-full rounded-xl border border-black/10 shadow-sm"
                    />
                  </div>
                </div>
              </FadeIn>
            );
          })}
        </div>
      </Section>

      <Section spacing="lg" background="transparent">
        <div className="mx-auto grid max-w-5xl grid-cols-1 items-start gap-10 px-4 sm:px-6 lg:grid-cols-2">
          <div>
            <h2 className="text-[26px] font-bold leading-tight text-marketing-primary">
              {c.primaryCta}
            </h2>
            <div className="mt-6">
              <CTAButton variant="secondary" onClick={openDemoBooking}>
                {c.secondaryCta}
              </CTAButton>
            </div>
          </div>
          <AdLeadForm
            page="mobility-teams"
            heading={c.form.heading}
            submitLabel={c.form.submitLabel}
            successMessage={c.form.successMessage}
            selectQuestion={{
              label: c.form.qualifyingLabel,
              options: c.form.qualifyingOptions,
              required: true,
            }}
          />
        </div>
      </Section>
    </PublicLayout>
  );
};
