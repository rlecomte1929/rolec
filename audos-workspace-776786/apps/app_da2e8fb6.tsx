import React, { useState, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
// === SECTION 1: IMPORTS AND TYPES ===
// All imports and TypeScript interfaces/types.

interface NavLink {
  label: string;
  href: string;
}

interface Benefit {
  title: string;
  description: string;
  metric: string;
  icon: string;
}

interface Feature {
  title: string;
  description: string;
  steps: string[];
  badge: string;
}

interface FAQ {
  question: string;
  answer: string;
}

interface FooterLink {
  label: string;
  href: string;
}

interface PricingTier {
  name: string;
  price: string;
  description: string;
  items: string[];
  cta: string;
  href: string;
  featured?: boolean;
}

interface Stat {
  value: string;
  label: string;
}

// === SECTION 2: CONSTANTS AND CONFIGURATION ===
const WORKSPACE_BRAND_NAME = 'ReloPass';
const WORKSPACE_TAGLINE = 'Global moves, intelligently managed.';
const WORKSPACE_PRIMARY_COLOR = '#2a93e0';
const WORKSPACE_HIGHLIGHT_COLOR = '#38c6de';
const WORKSPACE_CONTRAST_COLOR = '#2a93e0';
const WORKSPACE_TYPOGRAPHY = "'Inter', system-ui, sans-serif";
const WORKSPACE_FONT_FAMILY = '"Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
const WORKSPACE_SURFACE_PAGE = '#0b1620';
const WORKSPACE_SURFACE_PAGE_ALT = '#0e1f2c';
const WORKSPACE_SURFACE_PANEL = '#142430';
const WORKSPACE_SURFACE_PANEL_STRONG = '#1b3344';
const WORKSPACE_SURFACE_ACCENT_SOFT = 'rgba(56, 198, 222, 0.14)';
const WORKSPACE_BORDER_COLOR = '#203445';
const WORKSPACE_BORDER_STRONG_COLOR = '#2a465b';
const WORKSPACE_TEXT_PRIMARY = '#e6f1f5';
const WORKSPACE_TEXT_SECONDARY = '#b6c8d6';
const WORKSPACE_TEXT_MUTED = '#8aa2b3';
const WORKSPACE_TEXT_ON_PRIMARY = '#00131f';
const WORKSPACE_TEXT_ON_HIGHLIGHT = '#00131f';
const WORKSPACE_TEXT_ON_CONTRAST = '#00131f';
const WORKSPACE_HERO_GRADIENT = 'radial-gradient(900px circle at 50% 12%, rgba(42,147,224,0.25), transparent 60%), radial-gradient(1000px circle at 80% 0%, rgba(56,198,222,0.20), transparent 65%), linear-gradient(180deg, #0b1620 0%, #0b1620 100%)';
const WORKSPACE_LOGO_URL = 'https://storage.googleapis.com/audos-images/attachments/776786/5f4a4002-eb6e-44a9-8cbe-c49e65cbe809.png';
const WORKSPACE_LOGO_ON_DARK_URL = 'https://storage.googleapis.com/audos-images/attachments/776786/5f4a4002-eb6e-44a9-8cbe-c49e65cbe809.png';
const WORKSPACE_SPACE_URL = '/space/workspace-776786';
const WORKSPACE_HERO_VIDEO_URL = 'https://storage.googleapis.com/audos-images/generated-videos/openrouter-l90i9EtMD6gCM1CCicN7-1782744970847.mp4';

const VISUAL_CONFIG = {
  radius: 'rounded-xl',
  cardShadow: 'shadow-md',
  headingFont: WORKSPACE_FONT_FAMILY,
  typographyName: WORKSPACE_TYPOGRAPHY,
};

// === SECTION 3: STRUCTURED CONTENT DATA ===
const NAV_LINKS: NavLink[] = [
  { label: 'Platform', href: '#features' },
  { label: 'Why', href: '#faq' },
  { label: 'Trust', href: '#hero' },
  { label: 'Access', href: WORKSPACE_SPACE_URL },
];

const BENEFITS: Benefit[] = [
  {
    title: 'Replace scattered spreadsheets',
    description: 'Centralize every move, approval, vendor touchpoint, deadline, and document so HR teams stop chasing status updates across tools.',
    metric: '1 command center',
    icon: '◎',
  },
  {
    title: 'Lower compliance exposure',
    description: 'Keep immigration, tax, policy, and audit checkpoints visible throughout each employee relocation journey.',
    metric: 'Always audit-ready',
    icon: '✓',
  },
  {
    title: 'Move faster with confidence',
    description: 'Automated roadmaps turn days of manual specialist coordination into a guided workflow your team can trust.',
    metric: 'Days saved per case',
    icon: '↗',
  },
];

const FEATURES: Feature[] = [
  {
    title: 'Move Roadmaps',
    description:
      'Generate a personalized step-by-step relocation roadmap for each employee move, including policy decisions, deadlines, vendors, documents, immigration, tax, and compliance checkpoints.',
    steps: ['Policy fit confirmed', 'Documents requested', 'Tax and immigration checkpoints mapped', 'Vendor tasks sequenced'],
    badge: 'Personalized journey',
  },
  {
    title: 'Case Command',
    description:
      'Track every active relocation from one command center. Surface delays, missing documents, upcoming deadlines, and compliance risks across all cases — without chasing status updates by email.',
    steps: ['Live case status', 'Deadline monitoring', 'Vendor and approval visibility', 'Risk flags before they escalate'],
    badge: 'Operational control',
  },
  {
    title: 'Relocation Tasks',
    description:
      'Turn every roadmap into assigned, trackable work. ReloPass automates reminders, routes approvals, and triggers compliance checks so nothing slips between HR, vendors, and the employee on the move.',
    steps: ['Auto-assigned next actions', 'Automated reminders', 'Approval and document routing', 'Full audit trail per case'],
    badge: 'Automated follow-through',
  },
];

const FAQS: FAQ[] = [
  {
    question: 'Can we start using ReloPass without a complex implementation?',
    answer:
      'Yes. ReloPass is designed for SME mobility teams that need clarity quickly. You can start with a guided move roadmap, add employee details, and build a compliant relocation plan without rebuilding your HR stack.',
  },
  {
    question: 'What does the free plan include?',
    answer:
      'The free experience helps you explore structured relocation planning, create an initial move roadmap, and understand how ReloPass organizes policy decisions, documents, vendors, and compliance checkpoints.',
  },
  {
    question: 'When should we upgrade to a paid plan?',
    answer:
      'Upgrade when your team is managing multiple active moves, coordinating vendors, or needs stronger oversight across deadlines, approvals, documents, and compliance risks. Start free, upgrade when you are ready.',
  },
  {
    question: 'Does ReloPass replace immigration or tax advisors?',
    answer:
      'ReloPass does not replace licensed advisors. It helps HR and mobility teams coordinate the process, track requirements, and keep expert inputs organized inside a clear relocation workflow.',
  },
  {
    question: 'How does ReloPass reduce compliance risk?',
    answer:
      'ReloPass makes every relocation step visible, assigns checkpoints, tracks required documents, and highlights risk areas before small oversights become costly delays.',
  },
];

const FOOTER_LINKS: FooterLink[] = [
  { label: 'Platform', href: '#features' },
  { label: 'Why', href: '#faq' },
  { label: 'Trust', href: '#hero' },
  { label: 'Access', href: '#access' },
  { label: 'Login', href: '/login' },
  { label: 'Register', href: '/register' },
  { label: 'Contact', href: 'mailto:contact@relopass.com' },
  { label: 'Start free', href: WORKSPACE_SPACE_URL },
];

const HERO_CONTENT = {
  eyebrow: 'The relocation platform for global mobility teams',
  title: 'Your cross-border moves still run on spreadsheets and follow-up emails.',
  subtitle: WORKSPACE_TAGLINE,
  description:
    'ReloPass replaces scattered spreadsheets and manual chasing with a single, automated relocation platform that keeps every cross-border case compliant, on schedule, and fully auditable.',
  primaryCta: 'Get Started Free',
  secondaryCta: 'See how it works',
};

const PROOF_CONTENT = {
  eyebrow: 'Trusted by global mobility teams',
  title: 'One operating layer for every international move',
  description:
    'Replace the spreadsheets, email threads, vendor portals, and last-minute reminders with a single source of truth your whole team can trust.',
};

const TRUST_LOGOS: string[] = ['Logo', 'Logo', 'Logo', 'Logo', 'Logo'];

const TESTIMONIAL = {
  quote:
    'We replaced three spreadsheets and a constant stream of follow-up emails with one platform. Every relocation is now compliant, on schedule, and fully auditable — and our team finally feels in control.',
  name: 'Head of Global Mobility',
  role: 'Your customer story goes here',
};

const FEATURES_CONTENT = {
  eyebrow: 'How It Works',
  title: 'From relocation request to audit-ready completion',
  description:
    'ReloPass converts each employee move into a timeline-based journey with decisions, tasks, documents, vendors, and compliance checkpoints in the right order.',
  previewTitle: 'Live mobility command center',
  previewSubtitle: 'Every case, checkpoint, and vendor action stays visible.',
};

const PRICING_CONTENT = {
  eyebrow: 'Simple value framing',
  title: 'Start free, upgrade when you are ready.',
  description:
    'Explore the workflow immediately, then unlock deeper team oversight when active move volume and compliance complexity grow.',
};

const PRICING_TIERS: PricingTier[] = [
  {
    name: 'Free',
    price: '$0',
    description: 'For evaluating structured global mobility workflows before committing budget.',
    items: ['Create an initial move roadmap', 'Map key relocation milestones', 'Preview compliance checkpoints', 'Share a clear plan internally'],
    cta: 'Start free',
    href: WORKSPACE_SPACE_URL,
  },
  {
    name: 'Team',
    price: 'Paid plans',
    description: 'For mobility teams that need ongoing case control, vendor visibility, and stronger compliance oversight.',
    items: ['Manage multiple active relocation cases', 'Track vendors, approvals, and documents', 'Monitor deadlines and risk flags', 'Build a repeatable mobility operating model'],
    cta: 'Upgrade when ready',
    href: WORKSPACE_SPACE_URL,
    featured: true,
  },
];

const STATS: Stat[] = [
  { value: '24/7', label: 'case visibility' },
  { value: '0', label: 'spreadsheet chaos' },
  { value: '100%', label: 'journey clarity' },
];

const CTA_CONTENT = {
  eyebrow: 'Bring every cross-border move under control',
  title: 'Retire the spreadsheets. Run global mobility on one platform.',
  description:
    'Launch your first relocation roadmap today and see how ReloPass keeps every case compliant, on schedule, and fully auditable — without the manual follow-ups.',
  primaryCta: 'Get Started Free',
};

const FOOTER_CONTENT = {
  tagline: WORKSPACE_TAGLINE,
  copyright: `© ${new Date().getFullYear()} ${WORKSPACE_BRAND_NAME}. All rights reserved.`,
};

// === SECTION 4: NAVIGATION SECTION ===
function Navigation() {
  const [scrolled, setScrolled] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);

  useEffect(() => {
    const updateScrollState = () => {
      const scrollTop = window.scrollY || document.documentElement.scrollTop;
      const maxScroll = Math.max(document.documentElement.scrollHeight - window.innerHeight, 1);
      setScrolled(scrollTop > 40);
      setScrollProgress(Math.min(100, Math.max(0, (scrollTop / maxScroll) * 100)));
    };

    updateScrollState();
    window.addEventListener('scroll', updateScrollState, { passive: true });
    window.addEventListener('resize', updateScrollState);

    return () => {
      window.removeEventListener('scroll', updateScrollState);
      window.removeEventListener('resize', updateScrollState);
    };
  }, []);

  return (
    <>
      <div
        className="fixed left-0 top-0 z-[60] h-0.5 transition-all duration-150"
        style={{ width: `${scrollProgress}%`, backgroundColor: WORKSPACE_HIGHLIGHT_COLOR }}
      />
      <header className="fixed left-0 right-0 top-0 z-50 px-4 pt-4 md:px-6 md:pt-6">
        <nav
          className={`mx-auto flex max-w-6xl items-center justify-between rounded-full px-6 py-3 shadow-lg backdrop-blur-md transition-all duration-300 ${
            scrolled ? 'border bg-[#142430]/95 text-white shadow-xl' : 'border bg-[#0b1620]/70 text-white'
          }`}
          aria-label="Main navigation"
          style={{ borderColor: WORKSPACE_BORDER_COLOR, color: WORKSPACE_TEXT_PRIMARY }}
        >
          <a href="#hero" className="flex items-center gap-3">
            {WORKSPACE_LOGO_URL ? (
              <div className="rounded-lg p-0.5 border" style={{ backgroundColor: WORKSPACE_SURFACE_PANEL, borderColor: WORKSPACE_BORDER_COLOR }}>
                <img src={WORKSPACE_LOGO_URL} alt={WORKSPACE_BRAND_NAME} className="h-7 w-7 object-contain" />
              </div>
            ) : (
              <span className="font-bold text-2xl" style={{ color: WORKSPACE_CONTRAST_COLOR }}>
                {WORKSPACE_BRAND_NAME.charAt(0)}
              </span>
            )}
            <span
              className="font-bold tracking-tight"
              data-section="nav-brand-name"
              style={{ fontFamily: WORKSPACE_FONT_FAMILY }}
            >
              ReloPass
            </span>
          </a>

          <div className="hidden items-center gap-7 md:flex">
            {NAV_LINKS.map((link, index) => (
              <a
                key={link.href}
                href={link.href}
                className="text-[14px] font-semibold text-white/80 transition hover:text-white"
                data-section={`nav-${index + 1}-label`}
              >
                {link.label}
              </a>
            ))}
            <a
              href="/login"
              className="text-[14px] font-semibold text-white/80 transition hover:text-white"
              data-section="nav-login"
            >
              Login
            </a>
            <a
              href="/register"
              className="text-[14px] font-semibold text-white/80 transition hover:text-white"
              data-section="nav-register"
            >
              Register
            </a>
            <a
              href="mailto:contact@relopass.com"
              className="text-[14px] font-semibold text-white/80 transition hover:text-white"
              data-section="nav-contact"
            >
              contact@relopass.com
            </a>
            <a
              href={WORKSPACE_SPACE_URL}
              className="rounded-full px-5 py-2.5 text-[14px] font-bold shadow-md transition duration-300 hover:scale-105"
              style={{ backgroundColor: WORKSPACE_HIGHLIGHT_COLOR, color: WORKSPACE_TEXT_ON_HIGHLIGHT, boxShadow: '0 0 0 2px rgba(56,198,222,0.22), 0 10px 30px rgba(56,198,222,0.35)' }}
              data-section="nav-cta"
            >
              Start free
            </a>
          </div>
        </nav>
      </header>
    </>
  );
}

// === SECTION 5: HERO SECTION ===
function HeroSection() {
  return (
    <section id="hero" className="relative flex min-h-[100svh] items-center justify-center overflow-hidden min-h-screen">
      {WORKSPACE_HERO_VIDEO_URL ? (
        <video
          src={WORKSPACE_HERO_VIDEO_URL}
          autoPlay
          muted
          loop
          playsInline
          className="absolute inset-0 w-full h-full object-cover z-0"
        />
      ) : (
        <div className="absolute inset-0" style={{ backgroundImage: WORKSPACE_HERO_GRADIENT }} />
      )}
      <div className="absolute inset-0 z-[1]" style={{ backgroundImage: WORKSPACE_HERO_GRADIENT }} />

      <div className="relative z-10 mx-auto max-w-4xl px-4" style={{ textAlign: 'center', color: WORKSPACE_TEXT_PRIMARY }}>
        <p
          className="reveal-on-scroll mx-auto mb-5 inline-flex rounded-full border px-4 py-2 font-bold backdrop-blur-md text-[13px] md:text-[14px]"
          data-section="hero-eyebrow"
          style={{ backgroundColor: WORKSPACE_SURFACE_ACCENT_SOFT, borderColor: WORKSPACE_BORDER_COLOR, color: WORKSPACE_TEXT_PRIMARY }}
        >
          {HERO_CONTENT.eyebrow}
        </p>
        <h1
          className="reveal-on-scroll mb-6 font-bold leading-tight tracking-[-0.02em] text-[42px] md:text-[72px]"
          data-section="hero-title"
          style={{ fontFamily: WORKSPACE_FONT_FAMILY, color: WORKSPACE_TEXT_PRIMARY }}
        >
          {HERO_CONTENT.title}
        </h1>
        <p
          className="reveal-on-scroll mx-auto mb-5 max-w-2xl text-[20px] md:text-[24px]"
          data-section="hero-subtitle"
          style={{ fontFamily: WORKSPACE_FONT_FAMILY, color: WORKSPACE_TEXT_SECONDARY }}
        >
          {HERO_CONTENT.subtitle}
        </p>
        <p
          className="reveal-on-scroll mx-auto mb-8 max-w-2xl leading-8 text-[16px] md:text-[18px]"
          data-section="hero-description"
          style={{ color: WORKSPACE_TEXT_SECONDARY }}
        >
          ReloPass replaces scattered spreadsheets and manual chasing with a single, automated relocation platform that keeps every cross-border case compliant, on schedule, and fully auditable.
        </p>
        <div className="reveal-on-scroll flex flex-col items-center justify-center gap-4 sm:flex-row">
          <a
            href={WORKSPACE_SPACE_URL}
            className="inline-block rounded-lg px-8 py-4 font-semibold shadow-md transition duration-300 hover:scale-105"
            style={{
              backgroundColor: WORKSPACE_PRIMARY_COLOR,
              color: WORKSPACE_TEXT_ON_PRIMARY,
              boxShadow: '0 0 0 2px rgba(42,147,224,0.22), 0 12px 36px rgba(42,147,224,0.35)'
            }}
            data-section="hero-primary-cta"
          >
            {HERO_CONTENT.primaryCta}
          </a>
          <a
            href="#features"
            className="inline-block rounded-lg border px-8 py-4 font-semibold backdrop-blur-md transition duration-300 hover:scale-105 hover:brightness-110"
            data-section="hero-secondary-cta"
            style={{ backgroundColor: WORKSPACE_SURFACE_PANEL, borderColor: WORKSPACE_BORDER_COLOR, color: WORKSPACE_TEXT_PRIMARY }}
          >
            {HERO_CONTENT.secondaryCta}
          </a>
        </div>

        <div className="reveal-on-scroll mx-auto mt-12 grid max-w-2xl grid-cols-3 gap-3">
          {STATS.map((stat, index) => (
            <div
              key={stat.label}
              className="rounded-xl border p-4 backdrop-blur-md"
              style={{ borderColor: WORKSPACE_BORDER_COLOR, backgroundColor: WORKSPACE_SURFACE_PANEL }}
            >
              <p className="font-bold text-[22px]" data-section={`hero-stat-${index + 1}-value`} style={{ color: WORKSPACE_TEXT_PRIMARY }}>
                {stat.value}
              </p>
              <p
                className="font-semibold uppercase tracking-wide text-[11px]"
                data-section={`hero-stat-${index + 1}-label`}
                style={{ color: WORKSPACE_TEXT_MUTED }}
              >
                {stat.label}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// === SECTION 6: SOCIAL PROOF SECTION ===
function SocialProofSection() {
  return (
    <section className="py-24" style={{ backgroundColor: WORKSPACE_SURFACE_PAGE }}>
      <div className="mx-auto max-w-7xl px-4">
        <div className="reveal-on-scroll mx-auto max-w-3xl text-center md:text-center">
          <p
            className="mb-3 text-[13px] font-bold uppercase tracking-[0.22em]"
            data-section="benefits-eyebrow"
            style={{ color: WORKSPACE_CONTRAST_COLOR }}
          >
            {PROOF_CONTENT.eyebrow}
          </p>
          <h2
            className="mb-5 text-[36px] font-bold tracking-tight md:text-[48px]"
            data-section="benefits-title"
            style={{ color: WORKSPACE_TEXT_PRIMARY, fontFamily: WORKSPACE_FONT_FAMILY }}
          >
            {PROOF_CONTENT.title}
          </h2>
          <p className="text-[18px] leading-8" data-section="benefits-description" style={{ color: WORKSPACE_TEXT_SECONDARY }}>
            {PROOF_CONTENT.description}
          </p>
        </div>

        <div className="reveal-on-scroll mt-12 flex flex-wrap items-center justify-center gap-x-10 gap-y-4 opacity-80">
          {TRUST_LOGOS.map((logo, index) => (
            <div
              key={index}
              className="flex h-10 w-28 items-center justify-center rounded-lg border text-[12px] font-bold uppercase tracking-widest"
              style={{ borderColor: WORKSPACE_BORDER_COLOR, color: WORKSPACE_TEXT_MUTED, backgroundColor: WORKSPACE_SURFACE_PANEL }}
              data-section={`trust-logo-${index + 1}`}
              aria-hidden="true"
            >
              {logo}
            </div>
          ))}
        </div>

        <figure
          className="reveal-on-scroll mx-auto mt-14 max-w-4xl rounded-2xl border p-8 text-center md:text-center shadow-md md:p-12"
          style={{ backgroundColor: WORKSPACE_SURFACE_PANEL, borderColor: WORKSPACE_BORDER_STRONG_COLOR }}
        >
          <blockquote
            className="text-[20px] font-semibold leading-9 md:text-[24px]"
            data-section="testimonial-quote"
            style={{ color: WORKSPACE_TEXT_PRIMARY, fontFamily: WORKSPACE_FONT_FAMILY }}
          >
            “{TESTIMONIAL.quote}”
          </blockquote>
          <figcaption className="mt-6 flex flex-col items-center gap-1">
            <span
              className="flex h-12 w-12 items-center justify-center rounded-full text-[18px] font-bold"
              style={{ backgroundColor: WORKSPACE_SURFACE_ACCENT_SOFT, color: WORKSPACE_TEXT_PRIMARY }}
              aria-hidden="true"
            >
              {WORKSPACE_BRAND_NAME.charAt(0)}
            </span>
            <span className="mt-2 text-[14px] font-bold" data-section="testimonial-name" style={{ color: WORKSPACE_TEXT_PRIMARY }}>
              {TESTIMONIAL.name}
            </span>
            <span className="text-[14px]" data-section="testimonial-role" style={{ color: WORKSPACE_TEXT_MUTED }}>
              {TESTIMONIAL.role}
            </span>
          </figcaption>
        </figure>

        <div className="mt-14 grid gap-6 md:grid-cols-3">
          {BENEFITS.map((benefit, index) => (
            <article
              key={benefit.title}
              className="reveal-on-scroll rounded-xl border p-7 shadow-md transition duration-300 hover:-translate-y-1 hover:shadow-lg"
              style={{ backgroundColor: WORKSPACE_SURFACE_PANEL, borderColor: WORKSPACE_BORDER_COLOR }}
            >
              <div className="mb-6 flex items-center justify-between">
                <span
                  className="flex h-12 w-12 items-center justify-center rounded-xl text-[20px] font-bold"
                  style={{ backgroundColor: WORKSPACE_SURFACE_ACCENT_SOFT, color: WORKSPACE_TEXT_PRIMARY }}
                  aria-hidden="true"
                >
                  {benefit.icon}
                </span>
                <span
                  className="rounded-full px-3 py-1 text-[12px] font-bold"
                  style={{ backgroundColor: WORKSPACE_SURFACE_PANEL_STRONG, color: WORKSPACE_TEXT_ON_CONTRAST }}
                  data-section={`benefit-${index + 1}-metric`}
                >
                  {benefit.metric}
                </span>
              </div>
              <h3
                className="mb-3 text-[20px] font-bold"
                data-section={`benefit-${index + 1}-title`}
                style={{ color: WORKSPACE_TEXT_PRIMARY, fontFamily: WORKSPACE_FONT_FAMILY }}
              >
                {benefit.title}
              </h3>
              <p className="leading-7" data-section={`benefit-${index + 1}-description`} style={{ color: WORKSPACE_TEXT_SECONDARY }}>
                {benefit.description}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

// === SECTION 7: FEATURES SECTION ===
// Features or how-it-works component only.

function FeaturesSection() {
  return (
    <section id="features" className="py-24" style={{ backgroundColor: WORKSPACE_SURFACE_PANEL }}>
      <div className="mx-auto grid max-w-7xl items-start gap-16 px-4 lg:grid-cols-[0.95fr_1.05fr]">
        <div className="lg:sticky lg:top-24">
          <div
            className="reveal-on-scroll rounded-2xl border p-8 shadow-xl"
            style={{ backgroundColor: WORKSPACE_SURFACE_PANEL_STRONG, borderColor: WORKSPACE_BORDER_STRONG_COLOR }}
          >
            <p
              className="mb-3 text-sm font-bold uppercase tracking-[0.22em]"
              data-section="features-eyebrow"
              style={{ color: WORKSPACE_PRIMARY_COLOR }}
            >
              {FEATURES_CONTENT.eyebrow}
            </p>
            <h2
              className="mb-5 text-4xl font-bold tracking-tight md:text-5xl"
              data-section="features-title"
              style={{ color: WORKSPACE_TEXT_PRIMARY, fontFamily: WORKSPACE_FONT_FAMILY }}
            >
              {FEATURES_CONTENT.title}
            </h2>
            <p className="mb-8 text-lg leading-8" data-section="features-description" style={{ color: WORKSPACE_TEXT_SECONDARY }}>
              {FEATURES_CONTENT.description}
            </p>

            <div className="rounded-xl border p-5" style={{ backgroundColor: WORKSPACE_SURFACE_PAGE, borderColor: WORKSPACE_BORDER_COLOR }}>
              <div className="mb-5 flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-bold" data-section="features-preview-title" style={{ color: WORKSPACE_TEXT_PRIMARY }}>
                    {FEATURES_CONTENT.previewTitle}
                  </h3>
                  <p className="text-sm" data-section="features-preview-subtitle" style={{ color: WORKSPACE_TEXT_MUTED }}>
                    {FEATURES_CONTENT.previewSubtitle}
                  </p>
                </div>
                <span
                  className="rounded-full px-3 py-1 text-xs font-bold"
                  style={{ backgroundColor: WORKSPACE_HIGHLIGHT_COLOR, color: WORKSPACE_TEXT_ON_HIGHLIGHT }}
                  data-section="features-preview-badge"
                >
                  On track
                </span>
              </div>

              <div className="space-y-4">
                {FEATURES.map((feature, index) => (
                  <div key={feature.title} className="relative rounded-xl border p-4" style={{ borderColor: WORKSPACE_BORDER_COLOR, backgroundColor: WORKSPACE_SURFACE_PANEL_STRONG }}>
                    <div
                      className="absolute -left-2 top-5 h-4 w-4 rounded-full border-4"
                      style={{ backgroundColor: index === 0 ? WORKSPACE_HIGHLIGHT_COLOR : WORKSPACE_CONTRAST_COLOR, borderColor: WORKSPACE_SURFACE_PAGE }}
                      aria-hidden="true"
                    />
                    <p className="text-sm font-bold" data-section={`preview-${index + 1}-title`} style={{ color: WORKSPACE_TEXT_PRIMARY }}>
                      {feature.title}
                    </p>
                    <p className="mt-1 text-xs" data-section={`preview-${index + 1}-badge`} style={{ color: WORKSPACE_TEXT_MUTED }}>
                      {feature.badge}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-6">
          {FEATURES.map((feature, index) => (
            <article
              key={feature.title}
              className="reveal-on-scroll rounded-2xl border p-7 shadow-md transition duration-300 hover:-translate-y-1 hover:shadow-lg"
              style={{ backgroundColor: WORKSPACE_SURFACE_PANEL_STRONG, borderColor: WORKSPACE_BORDER_COLOR }}
            >
              <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                <span
                  className="rounded-full px-3 py-1 text-xs font-bold"
                  style={{ backgroundColor: WORKSPACE_SURFACE_ACCENT_SOFT, color: WORKSPACE_TEXT_PRIMARY }}
                  data-section={`feature-${index + 1}-badge`}
                >
                  {feature.badge}
                </span>
                <span className="text-sm font-bold" style={{ color: WORKSPACE_PRIMARY_COLOR }} data-section={`feature-${index + 1}-step-label`}>
                  Step 0{index + 1}
                </span>
              </div>
              <h3
                className="mb-3 text-3xl font-bold"
                data-section={`feature-${index + 1}-title`}
                style={{ color: WORKSPACE_TEXT_PRIMARY, fontFamily: WORKSPACE_FONT_FAMILY }}
              >
                {feature.title}
              </h3>
              <p className="mb-6 leading-8" data-section={`feature-${index + 1}-description`} style={{ color: WORKSPACE_TEXT_SECONDARY }}>
                {feature.description}
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                {feature.steps.map((step, stepIndex) => (
                  <div
                    key={step}
                    className="rounded-xl border px-4 py-3 text-sm font-semibold"
                    style={{ backgroundColor: WORKSPACE_SURFACE_PAGE, borderColor: WORKSPACE_BORDER_COLOR, color: WORKSPACE_TEXT_SECONDARY }}
                    data-section={`feature-${index + 1}-item-${stepIndex + 1}`}
                  >
                    {step}
                  </div>
                ))}
              </div>
            </article>
          ))}

          <div className="reveal-on-scroll pt-10">
            <p
              className="mb-3 text-sm font-bold uppercase tracking-[0.22em]"
              data-section="pricing-eyebrow"
              style={{ color: WORKSPACE_PRIMARY_COLOR }}
            >
              {PRICING_CONTENT.eyebrow}
            </p>
            <h3 className="mb-4 text-3xl font-bold" data-section="pricing-title" style={{ color: WORKSPACE_TEXT_PRIMARY, fontFamily: WORKSPACE_FONT_FAMILY }}>
              {PRICING_CONTENT.title}
            </h3>
            <p className="mb-6 leading-8" data-section="pricing-description" style={{ color: WORKSPACE_TEXT_SECONDARY }}>
              {PRICING_CONTENT.description}
            </p>
            <div className="grid gap-5 md:grid-cols-2">
              {PRICING_TIERS.map((tier, index) => (
                <article
                  key={tier.name}
                  className="rounded-xl border p-6 shadow-md"
                  style={{
                    backgroundColor: tier.featured ? WORKSPACE_SURFACE_ACCENT_SOFT : WORKSPACE_SURFACE_PAGE_ALT,
                    borderColor: tier.featured ? WORKSPACE_HIGHLIGHT_COLOR : WORKSPACE_BORDER_COLOR,
                  }}
                >
                  <h4 className="text-xl font-bold" data-section={`pricing-${index + 1}-name`} style={{ color: WORKSPACE_TEXT_PRIMARY }}>
                    {tier.name}
                  </h4>
                  <p className="mt-2 text-2xl font-bold" data-section={`pricing-${index + 1}-price`} style={{ color: WORKSPACE_PRIMARY_COLOR }}>
                    {tier.price}
                  </p>
                  <p className="mt-3 leading-7" data-section={`pricing-${index + 1}-description`} style={{ color: WORKSPACE_TEXT_SECONDARY }}>
                    {tier.description}
                  </p>
                  <ul className="mt-5 space-y-3">
                    {tier.items.map((item, itemIndex) => (
                      <li key={item} className="flex gap-3 text-sm font-semibold" style={{ color: WORKSPACE_TEXT_PRIMARY }}>
                        <span style={{ color: WORKSPACE_HIGHLIGHT_COLOR }} aria-hidden="true">
                          ✓
                        </span>
                        <span data-section={`pricing-${index + 1}-item-${itemIndex + 1}`}>{item}</span>
                      </li>
                    ))}
                  </ul>
                  <a
                    href={tier.href}
                    className="mt-6 inline-flex rounded-lg px-5 py-3 text-sm font-bold transition duration-300 hover:scale-105"
                    style={{
                      backgroundColor: tier.featured ? WORKSPACE_HIGHLIGHT_COLOR : WORKSPACE_PRIMARY_COLOR,
                      color: tier.featured ? WORKSPACE_TEXT_ON_HIGHLIGHT : WORKSPACE_TEXT_ON_PRIMARY,
                    }}
                    data-section={`pricing-${index + 1}-cta`}
                  >
                    {tier.cta}
                  </a>
                </article>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// === SECTION 8: FAQ SECTION ===
// FAQ component only.

function FAQSection() {
  const [openIndex, setOpenIndex] = useState<number>(0);

  return (
    <section id="faq" className="py-24" style={{ backgroundColor: WORKSPACE_SURFACE_PAGE }}>
      <div className="mx-auto max-w-3xl px-4">
        <div className="reveal-on-scroll text-center">
          <p
            className="mb-3 text-sm font-bold uppercase tracking-[0.22em]"
            data-section="faq-eyebrow"
            style={{ color: WORKSPACE_PRIMARY_COLOR }}
          >
            Questions, answered
          </p>
          <h2
            className="mb-5 text-4xl font-bold tracking-tight md:text-5xl"
            data-section="faq-title"
            style={{ color: WORKSPACE_TEXT_PRIMARY, fontFamily: WORKSPACE_FONT_FAMILY }}
          >
            What mobility teams ask first
          </h2>
          <p className="mb-10 text-lg leading-8" data-section="faq-description" style={{ color: WORKSPACE_TEXT_SECONDARY }}>
            Practical answers for HR leaders replacing manual relocation coordination with a dedicated operating system.
          </p>
        </div>

        <div className="space-y-4">
          {FAQS.map((faq, index) => {
            const isOpen = openIndex === index;
            return (
              <article
                key={faq.question}
                className="reveal-on-scroll overflow-hidden rounded-xl border shadow-md"
                style={{ backgroundColor: WORKSPACE_SURFACE_PANEL, borderColor: WORKSPACE_BORDER_COLOR }}
              >
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left"
                  onClick={() => setOpenIndex(isOpen ? -1 : index)}
                  aria-expanded={isOpen}
                  aria-controls={`faq-panel-${index}`}
                >
                  <span className="text-lg font-bold" data-section={`faq-${index + 1}-q`} style={{ color: WORKSPACE_TEXT_PRIMARY }}>
                    {faq.question}
                  </span>
                  <span
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-lg font-bold transition duration-300"
                    style={{ backgroundColor: isOpen ? WORKSPACE_HIGHLIGHT_COLOR : WORKSPACE_SURFACE_ACCENT_SOFT, color: WORKSPACE_TEXT_PRIMARY }}
                    aria-hidden="true"
                  >
                    {isOpen ? '−' : '+'}
                  </span>
                </button>
                <div
                  id={`faq-panel-${index}`}
                  className={`grid transition-all duration-300 ${isOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'}`}
                >
                  <div className="overflow-hidden">
                    <p className="px-6 pb-6 leading-8" data-section={`faq-${index + 1}-a`} style={{ color: WORKSPACE_TEXT_SECONDARY }}>
                      {faq.answer}
                    </p>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// === SECTION 9: FINAL CTA AND FOOTER ===
// Final CTA and footer components only.

function FinalCTA() {
  return (
    <section className="px-4 py-24" style={{ backgroundColor: WORKSPACE_SURFACE_PAGE }}>
      <div
        className="reveal-on-scroll mx-auto max-w-6xl overflow-hidden rounded-2xl border p-8 text-center shadow-xl md:p-14"
        style={{ backgroundImage: WORKSPACE_HERO_GRADIENT, borderColor: WORKSPACE_BORDER_STRONG_COLOR }}
      >
        <p
          className="mb-3 text-sm font-bold uppercase tracking-[0.22em]"
          data-section="final-cta-eyebrow"
          style={{ color: WORKSPACE_CONTRAST_COLOR }}
        >
          {CTA_CONTENT.eyebrow}
        </p>
        <h2
          className="mx-auto mb-5 max-w-3xl text-4xl font-bold tracking-tight md:text-6xl"
          data-section="final-cta-title"
          style={{ color: WORKSPACE_TEXT_PRIMARY, fontFamily: WORKSPACE_FONT_FAMILY }}
        >
          {CTA_CONTENT.title}
        </h2>
        <p className="mx-auto mb-8 max-w-2xl text-lg leading-8" data-section="final-cta-description" style={{ color: WORKSPACE_TEXT_SECONDARY }}>
          {CTA_CONTENT.description}
        </p>
        <a
          href={WORKSPACE_SPACE_URL}
          className="inline-flex rounded-lg px-8 py-4 text-lg font-bold shadow-md transition duration-300 hover:scale-105"
          style={{ backgroundColor: WORKSPACE_HIGHLIGHT_COLOR, color: WORKSPACE_TEXT_ON_HIGHLIGHT }}
          data-section="cta-primary"
        >
          {CTA_CONTENT.primaryCta}
        </a>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t px-4 py-10" style={{ backgroundColor: WORKSPACE_SURFACE_PAGE_ALT, borderColor: WORKSPACE_BORDER_COLOR }}>
      <div className="mx-auto flex max-w-6xl flex-col gap-8 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="mb-3 flex items-center gap-3">
            {WORKSPACE_LOGO_URL ? <div className="rounded-lg p-0.5 border" style={{ backgroundColor: WORKSPACE_SURFACE_PANEL, borderColor: WORKSPACE_BORDER_COLOR }}><img src={WORKSPACE_LOGO_URL} alt={WORKSPACE_BRAND_NAME} className="h-7 w-7 object-contain" /></div> : <span className="font-bold text-xl" style={{color: WORKSPACE_PRIMARY_COLOR}}>{WORKSPACE_BRAND_NAME.charAt(0)}</span>}
            <span className="text-lg font-bold" data-section="footer-brand-name" style={{ color: WORKSPACE_TEXT_PRIMARY, fontFamily: WORKSPACE_FONT_FAMILY }}>
              {WORKSPACE_BRAND_NAME}
            </span>
          </div>
          <p className="text-sm" data-section="footer-tagline" style={{ color: WORKSPACE_TEXT_SECONDARY }}>
            {FOOTER_CONTENT.tagline}
          </p>
        </div>

        <div className="flex flex-wrap gap-5">
          {FOOTER_LINKS.map((link, index) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm font-bold transition hover:opacity-75"
              data-section={`footer-link-${index + 1}-label`}
              style={{ color: WORKSPACE_TEXT_SECONDARY }}
            >
              {link.label}
            </a>
          ))}
        </div>

        <p className="text-sm" data-section="footer-copyright" style={{ color: WORKSPACE_TEXT_MUTED }}>
          {FOOTER_CONTENT.copyright}
        </p>
      </div>
    </footer>
  );
}

// === SECTION 10: MAIN COMPONENT AND ROOT RENDER ===
export default function LandingPage() {
  useEffect(() => {
    const fontLink = document.createElement('link');
    fontLink.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap';
    fontLink.rel = 'stylesheet';
    document.head.appendChild(fontLink);

    document.title = `${WORKSPACE_BRAND_NAME} — ${WORKSPACE_TAGLINE}`;

    const upsertMeta = (attrName: 'name' | 'property', attrValue: string, content: string) => {
      let el = document.querySelector(`meta[${attrName}="${attrValue}"]`) as HTMLMetaElement | null;
      if (!el) {
        el = document.createElement('meta');
        el.setAttribute(attrName, attrValue);
        document.head.appendChild(el);
      }
      el.setAttribute('content', content);
    };

    upsertMeta('name', 'description', HERO_CONTENT?.description || WORKSPACE_TAGLINE);
    upsertMeta('property', 'og:title', `${WORKSPACE_BRAND_NAME} — ${WORKSPACE_TAGLINE}`);
    upsertMeta('property', 'og:description', HERO_CONTENT?.description || WORKSPACE_TAGLINE);
    upsertMeta('property', 'og:image', WORKSPACE_LOGO_URL);
    upsertMeta('name', 'theme-color', WORKSPACE_SURFACE_PAGE);

    const revealElements = Array.from(document.querySelectorAll('.reveal-on-scroll'));
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            (entry.target as HTMLElement).classList.add('is-visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.14 }
    );

    revealElements.forEach((element) => observer.observe(element));

    return () => {
      observer.disconnect();
      if (document.head.contains(fontLink)) {
        document.head.removeChild(fontLink);
      }
    };
  }, []);

  return (
    <div
      className="min-h-full overflow-y-auto"
      data-logo-on-dark={WORKSPACE_LOGO_ON_DARK_URL}
      data-typography={VISUAL_CONFIG.typographyName}
      style={{ backgroundColor: 'var(--brand-surface-page, #0b1620)', color: 'var(--brand-text-primary, #e6f1f5)', fontFamily: WORKSPACE_FONT_FAMILY }}
    >
      <style>{`
        :root {
          --brand-font: ${WORKSPACE_FONT_FAMILY};
          --brand-surface-page: ${WORKSPACE_SURFACE_PAGE};
          --brand-surface-page-alt: ${WORKSPACE_SURFACE_PAGE_ALT};
          --brand-surface-card: ${WORKSPACE_SURFACE_PANEL};
          --brand-surface-panel: ${WORKSPACE_SURFACE_PANEL};
          --brand-text-primary: ${WORKSPACE_TEXT_PRIMARY};
          --brand-text-secondary: ${WORKSPACE_TEXT_SECONDARY};
          --brand-text-muted: ${WORKSPACE_TEXT_MUTED};
          --brand-primary: ${WORKSPACE_PRIMARY_COLOR};
          --brand-highlight: ${WORKSPACE_HIGHLIGHT_COLOR};
          --brand-contrast: ${WORKSPACE_CONTRAST_COLOR};
          --brand-border: ${WORKSPACE_BORDER_COLOR};
        }
        html {
          scroll-behavior: smooth;
        }
        body {
          margin: 0;
          font-family: var(--brand-font);
          background: ${WORKSPACE_SURFACE_PAGE};
          color: ${WORKSPACE_TEXT_PRIMARY};
        }
        .reveal-on-scroll {
          opacity: 0;
          transform: translateY(22px);
          transition: opacity 700ms ease, transform 700ms ease;
        }
        .reveal-on-scroll.is-visible {
          opacity: 1;
          transform: translateY(0);
        }
        @media (prefers-reduced-motion: reduce) {
          html {
            scroll-behavior: auto;
          }
          .reveal-on-scroll {
            opacity: 1;
            transform: none;
            transition: none;
          }
        }
      `}</style>
      <Navigation />
      <main>
        <HeroSection />
        <SocialProofSection />
        <FeaturesSection />
        <FAQSection />
        <FinalCTA />
      </main>
      <Footer />
    </div>
  );
}

const container = document.getElementById('root')!;
const root = createRoot(container);
root.render(<LandingPage />);