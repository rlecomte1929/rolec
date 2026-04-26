import React from 'react';
import { PublicLayout } from '../../components/public';
import { Section, SectionHeader, FadeIn } from '../../components/marketing';
import { securityContent } from './securityContent';

const CONTACT_EMAIL = 'contact@relopass.com';

function renderBody(text: string): React.ReactNode {
  if (!text.includes(CONTACT_EMAIL)) return text;
  const [before, after] = text.split(CONTACT_EMAIL);
  return (
    <>
      {before}
      <a
        className="text-marketing-primary underline underline-offset-2 hover:text-marketing-accent"
        href={`mailto:${CONTACT_EMAIL}`}
      >
        {CONTACT_EMAIL}
      </a>
      {after}
    </>
  );
}

export const SecurityPage: React.FC = () => {
  const c = securityContent;

  return (
    <PublicLayout>
      <Section spacing="lg" background="transparent">
        <div className="max-w-2xl mx-auto px-4 sm:px-6">
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

      <Section spacing="lg" background="muted">
        <FadeIn>
          <div className="max-w-2xl mx-auto px-4 sm:px-6">
            <dl className="space-y-8 sm:space-y-10">
              {c.points.map((point) => (
                <div key={point.title}>
                  <dt className="text-marketing-body-lg font-semibold text-marketing-primary">
                    {point.title}
                  </dt>
                  <dd className="mt-2 text-marketing-body text-marketing-text-muted leading-relaxed">
                    {renderBody(point.body)}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </FadeIn>
      </Section>
    </PublicLayout>
  );
};
