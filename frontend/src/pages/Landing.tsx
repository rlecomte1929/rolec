import React, { useEffect } from 'react';
import { PublicLayout } from '../components/public';
import {
  Section,
  SectionHeader,
  HeroSurface,
  ProofBlock,
  FeatureCard,
  CTAPanel,
  CTAButton,
  TrustDifferentiation,
  FadeIn,
} from '../components/marketing';
import { buildRoute } from '../navigation/routes';
import { useRegisterNav } from '../navigation/registry';
import { useDemoBooking } from '../hooks/useDemoBooking';
import { usePageMeta } from '../hooks/usePageMeta';
import { emitMarketingEvent, readUtm } from '../analytics';
import { landingContent } from './landing/landingContent';
import { imgDimensions } from '../lib/publicImageDimensions';

let landingViewEmitted = false;

export const Landing: React.FC = () => {
  useRegisterNav('Landing', [
    { label: 'Book a demo', routeKey: 'access' },
    { label: 'See the platform', routeKey: 'platform' },
  ]);

  // UIAUDIT-2026-06-13: keep the search + share metadata aligned with the
  // operating-layer category SITE-1 re-anchored the title/hero to. (The old
  // FRIDAY-004d "Mobility AI" strings still lingered in description/ogTitle/
  // ogDescription/ogImageAlt/schema below while the title already changed.)
  usePageMeta({
    title: 'ReloPass — Global mobility infrastructure', // SITE-1: re-anchored to the infrastructure category (was 'Mobility AI…')
    description:
      'Run relocation cases, timelines, documents, providers, and policy controls through one operating layer.',
    ogTitle: 'ReloPass — Global mobility infrastructure',
    ogDescription:
      'Every relocation case is visible, compliant, and on time.',
    ogUrl: 'https://relopass.com/',
    // TODO [FRIDAY-004e hand-off]: og:image asset is a designer commission and does
    // NOT exist yet (1200×630 spec in FRIDAY-004d §5). This path 404s until the asset
    // ships — confirm filename/path with the designer before relying on link previews.
    ogImage: 'https://relopass.com/og/og-default-1200x630.png',
    ogImageWidth: '1200',
    ogImageHeight: '630',
    ogImageAlt: 'ReloPass — Global mobility infrastructure',
    ogLocale: 'en_GB',
    // TODO [FRIDAY-004e hand-off]: confirm the @relopass X handle exists; if not,
    // drop twitterSite/twitterCreator (FRIDAY-004d §6).
    twitterSite: '@relopass',
    twitterCreator: '@relopass',
    // schema.org Organization (FRIDAY-004d §7). TODO [Romain to confirm before merge]:
    //   - foundingDate: 2024 or 2025?
    //   - sameAs[0] LinkedIn company slug
    //   - sameAs[1] X handle (remove if no account)
    //   - sameAs[2] whether to expose the personal GitHub or omit
    //   - contactPoint emails (sales@/support@) must exist + be monitored, else drop the array
    jsonLd: {
      '@context': 'https://schema.org',
      '@type': 'Organization',
      name: 'ReloPass',
      alternateName: 'ReloPass — Global mobility infrastructure',
      url: 'https://relopass.com/',
      logo: 'https://relopass.com/brand/logo-512.png',
      description:
        'The operating layer for relocation cases, timelines, documents, providers, and policy controls.',
      foundingDate: '2025', // TODO [Romain]: confirm 2024 vs 2025
      sameAs: [
        'https://www.linkedin.com/company/relopass/', // TODO [Romain]: confirm slug
        'https://x.com/relopass', // TODO [Romain]: confirm handle / remove if none
        'https://github.com/rlecomte1929', // TODO [Romain]: confirm whether to expose
      ],
      contactPoint: [
        // TODO [Romain]: confirm these inboxes exist + are monitored, else drop contactPoint
        {
          '@type': 'ContactPoint',
          contactType: 'sales',
          email: 'sales@relopass.com',
          availableLanguage: ['English', 'French'],
        },
        {
          '@type': 'ContactPoint',
          contactType: 'customer support',
          email: 'support@relopass.com',
          availableLanguage: ['English', 'French'],
        },
      ],
    },
  });

  const { open: openDemoBooking } = useDemoBooking();
  const c = landingContent;

  useEffect(() => {
    // Module-scoped, not a ref: Landing remounts on a NotFoundRedirect bounce and under
    // StrictMode's dev double-invoke, and each emit costs two POSTs (PostHog + our own
    // /api/public/track). One view per page load is what the metric means.
    if (landingViewEmitted) return;
    landingViewEmitted = true;
    emitMarketingEvent('landing_page_view', readUtm());
  }, []);

  // AIQ-757: `/` renders the marketing homepage for everyone — including
  // authenticated users — to match the other public pages (/platform,
  // /how-it-works, /get-started), which never redirect. The 404.html
  // `?__redirect=<path>` deep-link fallback is still honoured globally by
  // <QueryRedirect /> in App.tsx, so removing the role-home bounce here does
  // not break deep links.

  return (
    <PublicLayout>
      {/* 1. HERO: Two columns: text + CTAs left, visual right.
          AIQ-981: dropped `fillViewport` — it forced min-h-screen + vertical
          centering, which pushed the headline down and left blank space above
          the hero on tall viewports. The hero now starts directly below the nav. */}
      <Section spacing="lg" background="transparent">
        <HeroSurface
          eyebrow={c.hero.eyebrow}
          title={c.hero.headline}
          subtitle={c.hero.subheadline}
          brandPromise={c.hero.brandPromise}
          trustMicrocopy={c.hero.trustMicrocopy}
          actions={
            <>
              {/* SITE-1: primary CTA is now the approved get-started action;
                  'Book a demo' becomes the lower-friction secondary. */}
              {/* CTAButton's `to` (Link) variant type-forbids and ignores onClick.
                  This wrapper is intentionally non-interactive — the real control is
                  the inner <Link>. We use capture-phase onClickCapture purely to
                  observe the bubbling click for the fire-and-forget funnel emit; the
                  Link still navigates via `to` (and keeps cmd/middle-click-to-new-tab). */}
              <span onClickCapture={() => emitMarketingEvent('landing_cta_click', { cta: 'hero-primary', ...readUtm() })}>
                <CTAButton to={buildRoute('access')} variant="primary" size="lg">
                  {c.hero.primaryCta}
                </CTAButton>
              </span>
              <CTAButton
                onClick={() => { emitMarketingEvent('landing_cta_click', { cta: 'hero-demo', ...readUtm() }); openDemoBooking('landing-hero'); }}
                variant="outline"
                size="lg"
              >
                {c.hero.secondaryCta}
              </CTAButton>
            </>
          }
          visual={
            <img
              src="/screenshot-hero-case-card.png"
              alt="ReloPass case view showing Paul Doe's France to Singapore relocation — status, milestones, documents, and provider activity on one record."
              width={600}
              height={360}
              loading="eager"
              className="hidden md:block w-full max-w-[600px] h-auto rounded-[12px] shadow-[0_8px_32px_rgba(0,0,0,0.10)] transition-transform duration-300 ease-out hover:scale-[1.02]"
            />
          }
        />
      </Section>

      {/* 1b. PROOF BLOCK: 3 EU AI Act credibility lines, directly under the hero (FRIDAY-004c).
          AIQ-982: drop the proof block's top padding so it sits tight under the
          hero CTAs (the hero's bottom padding already provides the gap). */}
      <Section spacing="sm" background="transparent" className="pt-0">
        <FadeIn>
          <ProofBlock items={c.proofBlock.items} className="max-w-5xl mx-auto" />
        </FadeIn>
      </Section>

      {/* 2. PROBLEM: 3 cards */}
      <Section spacing="lg" background="muted">
        <FadeIn>
          <SectionHeader
            title={c.problem.title}
            align="center"
          />
        </FadeIn>
        <div className="mt-12 sm:mt-16 max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
          {c.problem.cards.map((card, i) => (
            <FadeIn key={card.title} delay={i * 80}>
              <FeatureCard
                title={card.title}
                description={card.body}
              />
            </FadeIn>
          ))}
        </div>
      </Section>

      {/* 3. SOLUTION: 4 blocks */}
      <Section spacing="lg" background="transparent">
        <FadeIn>
          <SectionHeader
            eyebrow={c.solution.sectionHeader}
            title={c.solution.title}
            align="center"
          />
        </FadeIn>
        {/* Anchored composition: one product visual + a scannable capabilities
            list, instead of six equal tiles (breaks the back-to-back card-grid
            rhythm; reuses the existing assignments screenshot). */}
        <div className="mt-12 sm:mt-16 max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16 items-center">
          <FadeIn>
            <img
              src="/screenshot-hr-assignments.png"
              {...imgDimensions("/screenshot-hr-assignments.png")}
              decoding="async"
              alt="ReloPass — every relocation case, its tasks, providers and status on one record"
              className="w-full rounded-xl border border-marketing-border shadow-sm"
              loading="lazy"
            />
          </FadeIn>
          <FadeIn delay={120}>
            <ul className="space-y-7">
              {c.solution.blocks.map((block) => (
                <li key={block.title} className="flex gap-4">
                  <span aria-hidden="true" className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-marketing-accent" />
                  <div>
                    <h3 className="text-marketing-h3 font-semibold text-marketing-primary">{block.title}</h3>
                    <p className="mt-1.5 text-sm text-marketing-text-muted leading-relaxed">{block.body}</p>
                  </div>
                </li>
              ))}
            </ul>
          </FadeIn>
        </div>
      </Section>

      {/* 4. DIFFERENTIATION / TRUST: Left text, right checklist */}
      <Section spacing="lg" background="muted">
        <FadeIn>
          <div className="max-w-5xl mx-auto">
          {c.trust.categoryBoundary && (
            <div className="mb-10 text-center">
              <p className="text-marketing-body-lg font-bold text-marketing-primary">
                {c.trust.categoryBoundary.positive}
              </p>
              {c.trust.categoryBoundary.negatives.map((line) => (
                <p key={line} className="text-marketing-body text-marketing-text-muted font-medium">
                  {line}
                </p>
              ))}
            </div>
          )}
          <TrustDifferentiation
            title={c.trust.title}
            body={c.trust.body}
            checklist={c.trust.checklist}
          />
          </div>
        </FadeIn>
      </Section>

      {/* 5. FINAL CTA: Centered, compact, decisive.
          AIQ-989: trim the bottom padding so the gap to the footer isn't oversized. */}
      <Section spacing="lg" background="transparent" className="pb-12 sm:pb-16">
        <FadeIn>
          <CTAPanel
            title={c.finalCta.headline}
            subtitle={c.finalCta.microCopy}
            variant="surface"
            primaryAction={
              <CTAButton
                onClick={() => { emitMarketingEvent('landing_cta_click', { cta: 'final-demo', ...readUtm() }); openDemoBooking('landing-final'); }}
                variant="primary"
                size="lg"
              >
                {c.finalCta.options.demo}
              </CTAButton>
            }
            secondaryAction={
              <CTAButton to={buildRoute('platform')} variant="outline" size="lg">
                {c.finalCta.options.platform}
              </CTAButton>
            }
            tertiaryAction={
              <CTAButton to={`${buildRoute('auth')}?mode=login`} variant="ghost" size="lg">
                {c.finalCta.options.signIn}
              </CTAButton>
            }
          />
        </FadeIn>
      </Section>
    </PublicLayout>
  );
};
