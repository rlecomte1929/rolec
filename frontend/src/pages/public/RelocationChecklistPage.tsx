import React from 'react';
import { PublicLayout } from '../../components/public';
import { Section, HeroSurface, FadeIn } from '../../components/marketing';
import { AdLeadForm } from '../../components/marketing/AdLeadForm';
import { usePageMeta } from '../../hooks/usePageMeta';
import { useAdEngagementTracking } from '../../hooks/useAdEngagementTracking';
import { relocationChecklistContent as c } from './adLandingContent';

/**
 * [AIQ-1783] `/relocation-checklist` — segment B, the employee.
 *
 * These visitors are not the buyer. The commercial point is the ONE gate: a work email
 * plus "Who do you work for?", which turns non-buyer traffic into a live target-account
 * list for outbound (the server derives the company domain from the email and matches
 * it against prospect_candidates).
 *
 * The disclaimer is verbatim and non-negotiable. Nothing on this page may claim a visa,
 * immigration or tax OUTCOME — ReloPass coordinates; it does not decide.
 */
export const RelocationChecklistPage: React.FC = () => {
  usePageMeta({ title: c.meta.title, description: c.meta.description, ogUrl: c.meta.ogUrl });
  useAdEngagementTracking('relocation-checklist');

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
        <div className="mx-auto grid max-w-5xl grid-cols-1 items-start gap-10 px-4 sm:px-6 lg:grid-cols-2">
          <FadeIn>
            <div>
              <h2 className="text-[22px] font-bold leading-tight text-marketing-primary">
                What the checklist covers
              </h2>
              <ul className="mt-5 space-y-4">
                {c.whatYouGet.map((item) => (
                  <li key={item} className="flex gap-3">
                    <span
                      aria-hidden="true"
                      className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-marketing-accent"
                    />
                    <span className="text-[14px] leading-relaxed text-marketing-text-muted">
                      {item}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-8 text-[14px] font-medium text-marketing-primary">
                {c.softBridge}
              </p>
            </div>
          </FadeIn>

          <AdLeadForm
            page="relocation-checklist"
            heading={c.form.heading}
            emailLabel={c.form.emailLabel}
            submitLabel={c.form.submitLabel}
            successMessage={c.form.successMessage}
            textQuestion={{ label: c.form.employerLabel, required: true }}
            footnote={c.disclaimer}
          />
        </div>
      </Section>
    </PublicLayout>
  );
};
