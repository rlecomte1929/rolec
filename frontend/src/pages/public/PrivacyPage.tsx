import React from 'react';
import { PublicLayout } from '../../components/public';
import { Section, SectionHeader, FadeIn } from '../../components/marketing';
import { usePageMeta } from '../../hooks/usePageMeta';
import { privacyContent } from './privacyContent';

const CONTACT_EMAIL = 'contact@relopass.com';

function renderBody(text: string): React.ReactNode {
  if (!text.includes(CONTACT_EMAIL)) return text;
  const parts = text.split(CONTACT_EMAIL);
  return (
    <>
      {parts.map((part, i) => (
        <React.Fragment key={i}>
          {part}
          {i < parts.length - 1 && (
            <a
              className="text-marketing-primary underline underline-offset-2 hover:text-marketing-accent"
              href={`mailto:${CONTACT_EMAIL}`}
            >
              {CONTACT_EMAIL}
            </a>
          )}
        </React.Fragment>
      ))}
    </>
  );
}

export const PrivacyPage: React.FC = () => {
  usePageMeta({
    title: 'Privacy Policy — ReloPass',
    description: 'How ReloPass collects, stores, and protects your data. Hosted in the EU.',
    ogUrl: 'https://www.relopass.com/privacy',
  });

  const c = privacyContent;

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
            <p className="text-marketing-body text-marketing-text-muted leading-relaxed">
              {c.intro}
            </p>
            <dl className="mt-10 space-y-8 sm:space-y-10">
              {c.sections.map((section) => (
                <div key={section.title}>
                  <dt className="text-marketing-body-lg font-semibold text-marketing-primary">
                    {section.title}
                  </dt>
                  <dd className="mt-2 text-marketing-body text-marketing-text-muted leading-relaxed">
                    {renderBody(section.body)}
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
