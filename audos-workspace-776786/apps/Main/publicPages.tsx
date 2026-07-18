import { assetUrl } from '../../components/landingContent';

export interface PublicPageContent {
  title: string;
  eyebrow?: string;
  body: string[];
  bullets?: string[];
  image?: string;
  imageAlt?: string;
}

export const PUBLIC_PAGES: Record<string, PublicPageContent> = {
  platform: {
    eyebrow: 'The platform',
    title: 'Every relocation on one system of record',
    body: [
      'ReloPass is the coordination layer for cross-border relocation. Cases, documents, providers, and progress live on one structured record instead of email threads and spreadsheets.',
      'HR and mobility operators see live status, compliance checkpoints, and vendor activity without chasing updates.',
    ],
    bullets: [
      'Structured relocation roadmaps applied at case creation',
      'Live case tracking across corridors and providers',
      'Compliance checkpoints built into every move',
    ],
    image: assetUrl('screenshot-employee-plan.png'),
    imageAlt: 'ReloPass employee relocation plan view',
  },
  why: {
    eyebrow: 'Why ReloPass',
    title: 'Built for mobility operators, not relocation agencies',
    body: [
      'ReloPass is workflow-first infrastructure: policy-aware guidance and execution in one system. It is not a vendor marketplace or a generic HR add-on.',
      'Every cross-border move runs through the same operating model — cases, timelines, documents, providers, and approvals.',
    ],
    bullets: [
      'One system of record for every relocation',
      'Policy becomes the operating rules',
      'Visibility for HR without inbox archaeology',
    ],
  },
  howItWorks: {
    eyebrow: 'How it works',
    title: 'From intake to arrival on one timeline',
    body: [
      'Enter the employee, corridor, and policy — ReloPass assembles a step-by-step roadmap with deadlines, documents, vendor touchpoints, and required approvals.',
      'Coordinators monitor progress in a command center while employees follow their own structured journey.',
    ],
    image: assetUrl('screenshot-destination-intelligence.png'),
    imageAlt: 'Destination intelligence in ReloPass',
  },
  getStarted: {
    eyebrow: 'Get started',
    title: 'Structure how you run relocation',
    body: [
      'Book a 30-minute walkthrough or sign in with your work email to explore the live demo workspace.',
      'Tell us how your relocations run today — we will show you what changes when cases live in one system.',
    ],
  },
  security: {
    eyebrow: 'Security',
    title: 'Enterprise-grade protection for mobility data',
    body: [
      'ReloPass is designed for HR and mobility teams handling sensitive employee and immigration data. Access is role-based; audit trails support compliance reviews.',
      'Production deployments add SSO, data residency options, and customer-managed encryption — contact us for the current security pack.',
    ],
  },
  privacy: {
    eyebrow: 'Privacy',
    title: 'Your data stays yours',
    body: [
      'Employee and case data is processed only to deliver relocation services to your organization. Marketing consent is optional and separate from product access.',
      'See our full privacy policy on relopass.com for subprocessors and retention schedules.',
    ],
  },
  compliance: {
    eyebrow: 'Compliance',
    title: 'Compliance checkpoints on every corridor',
    body: [
      'Immigration, tax, and policy requirements are modeled as checkpoints on each case — surfacing risks early and preserving an audit-ready trail.',
      'EU AI Act controls: AI-assisted extractions are logged, shadow-run, and require human confirmation before values ship to forms.',
    ],
  },
  access: {
    eyebrow: 'Access',
    title: 'Role-based access for HR, employees, and providers',
    body: [
      'HR and mobility managers operate the program. Employees follow assigned cases. Providers receive scoped tasks via magic links in production.',
      'This Audos preview uses email OTP sign-in instead of Google OAuth, passkeys, or Supabase invite flows from the original app.',
    ],
  },
  auth: {
    eyebrow: 'Sign in',
    title: 'Access your ReloPass workspace',
    body: [
      'In this Audos recreation, authentication uses the platform email + OTP flow at the space entry gate — not password login, Google SSO, or WebAuthn passkeys from the imported Supabase stack.',
      'Sign out and return to the public site to enter with a different email.',
    ],
  },
};

export function PublicPageView({ pageKey }: { pageKey: string }) {
  const page = PUBLIC_PAGES[pageKey];
  if (!page) return null;
  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      {page.eyebrow && (
        <p className="text-xs font-semibold uppercase tracking-[0.25em] mb-3 text-[var(--space-text-accent)]">{page.eyebrow}</p>
      )}
      <h1 className="text-3xl font-bold mb-6 text-[var(--space-text-primary)]">{page.title}</h1>
      <div className="space-y-4 text-sm leading-relaxed text-[var(--space-text-secondary)]">
        {page.body.map((p) => (
          <p key={p.slice(0, 40)}>{p}</p>
        ))}
      </div>
      {page.bullets && (
        <ul className="mt-6 space-y-2">
          {page.bullets.map((b) => (
            <li key={b} className="flex gap-2 text-sm text-[var(--space-text-secondary)]">
              <span className="text-[var(--space-brand-primary)]">•</span>
              {b}
            </li>
          ))}
        </ul>
      )}
      {page.image && (
        <img
          src={page.image}
          alt={page.imageAlt || ''}
          className="mt-8 w-full rounded-xl border"
          style={{ borderColor: 'var(--space-border-default)' }}
        />
      )}
    </div>
  );
}
