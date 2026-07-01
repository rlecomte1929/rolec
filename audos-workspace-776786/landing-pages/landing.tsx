import React, { useState, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
// === SECTION 1: IMPORTS AND TYPES ===
// All imports and TypeScript interfaces/types.

interface NavLink {
  label: string;
  href: string;
}

interface ProblemCard {
  title: string;
  description: string;
  tag: string;
}

interface Capability {
  title: string;
  description: string;
  badge: string;
}

interface CaseRow {
  id: string;
  corridor: string;
  stage: string;
  status: 'On track' | 'Action needed' | 'Blocked';
  due: string;
}

interface TimelineStep {
  label: string;
  state: 'done' | 'active' | 'upcoming';
}

interface AudienceMention {
  title: string;
  description: string;
}

interface FooterLink {
  label: string;
  href: string;
}

interface Stat {
  value: string;
  label: string;
}

// === SECTION 2: CONSTANTS AND CONFIGURATION ===
const WORKSPACE_BRAND_NAME = 'ReloPass';
const WORKSPACE_TAGLINE = 'Global mobility. Structured.';
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

const CONTACT_EMAIL = 'contact@relopass.com';
const DEMO_HREF = 'mailto:contact@relopass.com?subject=Book%20a%20demo';
const BRAND_PROMISE = 'Every relocation case is visible, compliant, on-time.';

const VISUAL_CONFIG = {
  radius: 'rounded-xl',
  cardShadow: 'shadow-md',
  headingFont: WORKSPACE_FONT_FAMILY,
  typographyName: WORKSPACE_TYPOGRAPHY,
};

// === SECTION 3: STRUCTURED CONTENT DATA ===
const NAV_LINKS: NavLink[] = [
  { label: 'Problem', href: '#problem' },
  { label: 'System', href: '#system' },
  { label: 'Product', href: '#product' },
  { label: 'Audience', href: '#audience' },
];

const HERO_CONTENT = {
  eyebrow: 'Global mobility infrastructure',
  title: 'Global mobility. Structured.',
  subtitle:
    'ReloPass is the coordination layer for cross-border employee relocation — one system where HR, employees, and providers work from the same source of truth.',
  promise: BRAND_PROMISE,
  primaryCta: 'Book a demo',
  secondaryCta: 'See the platform',
};

const HERO_STATS: Stat[] = [
  { value: 'Visible', label: 'every case, in real time' },
  { value: 'Compliant', label: 'policy-driven workflows' },
  { value: 'On-time', label: 'coordinated timelines' },
];

const PROBLEM_CONTENT = {
  eyebrow: 'The problem',
  title: 'Relocation still runs on emails and spreadsheets.',
  description:
    'Global workforce mobility is a coordination problem, not a service problem. Immigration, housing, schooling, and logistics run in parallel and uncoordinated — with no shared record and no real-time visibility. HR absorbs the follow-up, and employees are left uncertain.',
};

const PROBLEM_CARDS: ProblemCard[] = [
  {
    title: 'Fragmented processes',
    description: 'Every case is assembled by hand across inboxes, documents, and vendor portals. Nothing shares a single record.',
    tag: 'No source of truth',
  },
  {
    title: 'No real-time visibility',
    description: 'HR cannot see where a case stands without asking. Status lives in threads, not in a system.',
    tag: 'Status by email',
  },
  {
    title: 'Parallel, uncoordinated work',
    description: 'Immigration, housing, schooling, and logistics move on separate timelines that never reconcile.',
    tag: 'Uncoordinated workflows',
  },
];

const COST_OF_FAILURE: string[] = [
  'Delayed start dates',
  'Failed assignments',
  'Budget leakage',
  'Compliance exposure',
  'Overloaded HR teams',
];

const SYSTEM_CONTENT = {
  eyebrow: 'The system',
  title: 'One system coordinating every relocation.',
  description:
    'ReloPass translates policy into workflow, gives every stakeholder the same live record, and keeps a complete evidence trail behind each case.',
};

const SYSTEM_CAPABILITIES: Capability[] = [
  {
    title: 'Policy applied at case creation',
    description: 'Company policy is translated into the workflow the moment a case opens — the right steps, approvals, and entitlements, every time.',
    badge: 'Policy-to-workflow',
  },
  {
    title: 'Real-time visibility',
    description: 'One live view across every case. See status, owners, and next actions without chasing an update.',
    badge: 'Live case status',
  },
  {
    title: 'Corridor-specific execution',
    description: 'Workflows, timelines, and document requirements tuned to each origin-to-destination corridor.',
    badge: 'Region-aware',
  },
  {
    title: 'Structured case data',
    description: 'The same clean operational record for every relocation — comparable, reportable, and repeatable.',
    badge: 'Consistent records',
  },
  {
    title: 'Compliance evidence',
    description: 'A complete trail of who did what, when, and against which policy. Audit-ready by default.',
    badge: 'Audit trail',
  },
];

const PRODUCT_CONTENT = {
  eyebrow: 'The product',
  title: 'Structure every relocation.',
  description:
    'A data-forward surface for mobility operators: cases, timelines, and workflows in one structured operational record.',
  tableTitle: 'Active cases',
  tableSubtitle: 'One live record across every corridor.',
  timelineTitle: 'Case timeline',
  timelineSubtitle: 'Case #2041 · DE → US',
};

const PRODUCT_CASES: CaseRow[] = [
  { id: 'Case #2041', corridor: 'DE → US', stage: 'Immigration', status: 'On track', due: 'Aug 12' },
  { id: 'Case #2042', corridor: 'UK → SG', stage: 'Housing', status: 'Action needed', due: 'Aug 09' },
  { id: 'Case #2043', corridor: 'FR → CA', stage: 'Schooling', status: 'On track', due: 'Aug 20' },
  { id: 'Case #2044', corridor: 'IN → DE', stage: 'Logistics', status: 'Blocked', due: 'Aug 05' },
];

const PRODUCT_TIMELINE: TimelineStep[] = [
  { label: 'Case created', state: 'done' },
  { label: 'Policy applied', state: 'done' },
  { label: 'Documents collected', state: 'done' },
  { label: 'Immigration filed', state: 'active' },
  { label: 'Housing secured', state: 'upcoming' },
  { label: 'Arrival confirmed', state: 'upcoming' },
];

const AUDIENCE_CONTENT = {
  eyebrow: 'Built for mobility operators',
  title: 'For the people who own the move.',
  description:
    'ReloPass is built for HR and Global Mobility managers at growing companies of 50 to 250 employees running 10 or more cross-border relocations a year.',
  promise: 'Every relocation runs through a visible, policy-driven workflow.',
};

const AUDIENCE_SECONDARY: AudienceMention[] = [
  {
    title: 'Employees',
    description: 'A clear view of what happens next, so the move feels predictable instead of uncertain.',
  },
  {
    title: 'Providers',
    description: 'Structured handoffs and shared timelines, so vendor work stays coordinated with the case.',
  },
];

const NOT_CONTENT = {
  eyebrow: 'What ReloPass is',
  title: 'Coordination infrastructure — not a service.',
  description: 'ReloPass sells control over complexity. It is the layer that keeps every relocation structured.',
};

const NOT_ITEMS: { not: string; is: string }[] = [
  { not: 'Not a relocation agency', is: 'The system your agencies and providers plug into.' },
  { not: 'Not a marketplace', is: 'A single operational record, not a vendor directory.' },
  { not: 'Not an HR add-on', is: 'Coordination infrastructure for the entire relocation.' },
];

const CTA_CONTENT = {
  eyebrow: 'Structure every relocation',
  title: 'Tell us how your relocations run today.',
  description:
    'Book a 30-minute walkthrough and see how ReloPass brings every cross-border case into one visible, policy-driven workflow.',
  primaryCta: 'Book a demo',
  secondaryCta: 'See the platform',
};

const FOOTER_LINKS: FooterLink[] = [
  { label: 'Problem', href: '#problem' },
  { label: 'System', href: '#system' },
  { label: 'Product', href: '#product' },
  { label: 'Audience', href: '#audience' },
  { label: 'Book a demo', href: DEMO_HREF },
  { label: CONTACT_EMAIL, href: `mailto:${CONTACT_EMAIL}` },
];

const FOOTER_CONTENT = {
  tagline: 'Global mobility infrastructure. Structure every relocation.',
  copyright: `© ${new Date().getFullYear()} ${WORKSPACE_BRAND_NAME}. All rights reserved.`,
};

function statusStyles(status: CaseRow['status']): { bg: string; color: string } {
  if (status === 'On track') return { bg: 'rgba(22,163,74,0.16)', color: '#5fd694' };
  if (status === 'Action needed') return { bg: 'rgba(217,119,6,0.16)', color: '#f0b24a' };
  return { bg: 'rgba(220,38,38,0.16)', color: '#f08a8a' };
}

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
              href={`mailto:${CONTACT_EMAIL}`}
              className="text-[14px] font-semibold text-white/80 transition hover:text-white"
              data-section="nav-contact"
            >
              {CONTACT_EMAIL}
            </a>
            <a
              href={DEMO_HREF}
              className="rounded-full px-5 py-2.5 text-[14px] font-bold shadow-md transition duration-300 hover:scale-105"
              style={{ backgroundColor: WORKSPACE_HIGHLIGHT_COLOR, color: WORKSPACE_TEXT_ON_HIGHLIGHT, boxShadow: '0 0 0 2px rgba(56,198,222,0.22), 0 10px 30px rgba(56,198,222,0.35)' }}
              data-section="nav-cta"
            >
              Book a demo
            </a>
          </div>
        </nav>
      </header>
    </>
  );
}

// === SECTION 5: HERO SECTION (STATEMENT) ===
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
      <div className="absolute inset-0 z-[1]" style={{ backgroundColor: 'rgba(11,22,32,0.72)' }} />

      <div className="relative z-10 mx-auto max-w-4xl px-4" style={{ textAlign: 'center', color: WORKSPACE_TEXT_PRIMARY }}>
        <p
          className="reveal-on-scroll mx-auto mb-5 inline-flex rounded-full border px-4 py-2 font-semibold backdrop-blur-md text-[13px] md:text-[14px] uppercase tracking-[0.18em]"
          data-section="hero-eyebrow"
          style={{ backgroundColor: WORKSPACE_SURFACE_ACCENT_SOFT, borderColor: WORKSPACE_BORDER_COLOR, color: WORKSPACE_TEXT_PRIMARY }}
        >
          {HERO_CONTENT.eyebrow}
        </p>
        <h1
          className="reveal-on-scroll mb-6 font-bold leading-tight tracking-[-0.02em] text-[46px] md:text-[80px]"
          data-section="hero-title"
          style={{ fontFamily: WORKSPACE_FONT_FAMILY, color: WORKSPACE_TEXT_PRIMARY }}
        >
          {HERO_CONTENT.title}
        </h1>
        <p
          className="reveal-on-scroll mx-auto mb-6 max-w-2xl text-[18px] md:text-[22px] leading-8"
          data-section="hero-subtitle"
          style={{ fontFamily: WORKSPACE_FONT_FAMILY, color: WORKSPACE_TEXT_SECONDARY }}
        >
          {HERO_CONTENT.subtitle}
        </p>
        <div className="reveal-on-scroll flex flex-col items-center justify-center gap-4 sm:flex-row">
          <a
            href={DEMO_HREF}
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
            href="#product"
            className="inline-block rounded-lg border px-8 py-4 font-semibold backdrop-blur-md transition duration-300 hover:scale-105 hover:brightness-110"
            data-section="hero-secondary-cta"
            style={{ backgroundColor: WORKSPACE_SURFACE_PANEL, borderColor: WORKSPACE_BORDER_COLOR, color: WORKSPACE_TEXT_PRIMARY }}
          >
            {HERO_CONTENT.secondaryCta}
          </a>
        </div>

        <p
          className="reveal-on-scroll mx-auto mt-10 text-[14px] font-semibold uppercase tracking-[0.2em]"
          data-section="hero-promise"
          style={{ color: WORKSPACE_HIGHLIGHT_COLOR }}
        >
          {HERO_CONTENT.promise}
        </p>

        <div className="reveal-on-scroll mx-auto mt-8 grid max-w-2xl grid-cols-3 gap-3">
          {HERO_STATS.map((stat, index) => (
            <div
              key={stat.label}
              className="rounded-xl border p-4 backdrop-blur-md"
              style={{ borderColor: WORKSPACE_BORDER_COLOR, backgroundColor: WORKSPACE_SURFACE_PANEL }}
            >
              <p className="font-bold text-[20px]" data-section={`hero-stat-${index + 1}-value`} style={{ color: WORKSPACE_TEXT_PRIMARY }}>
                {stat.value}
              </p>
              <p
                className="font-semibold uppercase tracking-wide text-[11px] mt-1"
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

// === SECTION 6: PROBLEM SECTION ===
function ProblemSection() {
  return (
    <section id="problem" className="py-24" style={{ backgroundColor: WORKSPACE_SURFACE_PAGE }}>
      <div className="mx-auto max-w-7xl px-4">
        <div className="reveal-on-scroll mx-auto max-w-3xl text-center">
          <p
            className="mb-3 text-[13px] font-bold uppercase tracking-[0.22em]"
            data-section="problem-eyebrow"
            style={{ color: WORKSPACE_CONTRAST_COLOR }}
          >
            {PROBLEM_CONTENT.eyebrow}
          </p>
          <h2
            className="mb-5 text-[36px] font-bold tracking-tight md:text-[48px]"
            data-section="problem-title"
            style={{ color: WORKSPACE_TEXT_PRIMARY, fontFamily: WORKSPACE_FONT_FAMILY }}
          >
            {PROBLEM_CONTENT.title}
          </h2>
          <p className="text-[18px] leading-8" data-section="problem-description" style={{ color: WORKSPACE_TEXT_SECONDARY }}>
            {PROBLEM_CONTENT.description}
          </p>
        </div>

        <div className="mt-14 grid gap-6 md:grid-cols-3">
          {PROBLEM_CARDS.map((card, index) => (
            <article
              key={card.title}
              className="reveal-on-scroll rounded-xl border p-7 shadow-md transition duration-300 hover:-translate-y-1 hover:shadow-lg"
              style={{ backgroundColor: WORKSPACE_SURFACE_PANEL, borderColor: WORKSPACE_BORDER_COLOR }}
            >
              <span
                className="mb-6 inline-flex rounded-full px-3 py-1 text-[12px] font-bold"
                style={{ backgroundColor: WORKSPACE_SURFACE_PANEL_STRONG, color: WORKSPACE_TEXT_ON_CONTRAST }}
                data-section={`problem-${index + 1}-tag`}
              >
                {card.tag}
              </span>
              <h3
                className="mb-3 text-[20px] font-bold"
                data-section={`problem-${index + 1}-title`}
                style={{ color: WORKSPACE_TEXT_PRIMARY, fontFamily: WORKSPACE_FONT_FAMILY }}
              >
                {card.title}
              </h3>
              <p className="leading-7" data-section={`problem-${index + 1}-description`} style={{ color: WORKSPACE_TEXT_SECONDARY }}>
                {card.description}
              </p>
            </article>
          ))}
        </div>

        <div
          className="reveal-on-scroll mx-auto mt-12 max-w-5xl rounded-2xl border p-8 md:p-10"
          style={{ backgroundColor: WORKSPACE_SURFACE_PAGE_ALT, borderColor: WORKSPACE_BORDER_STRONG_COLOR }}
        >
          <p className="mb-5 text-[13px] font-bold uppercase tracking-[0.22em]" style={{ color: WORKSPACE_TEXT_MUTED }}>
            The cost of failure
          </p>
          <div className="flex flex-wrap gap-3">
            {COST_OF_FAILURE.map((item, index) => (
              <span
                key={item}
                className="rounded-lg border px-4 py-2 text-[14px] font-semibold"
                style={{ backgroundColor: WORKSPACE_SURFACE_PANEL, borderColor: WORKSPACE_BORDER_COLOR, color: WORKSPACE_TEXT_SECONDARY }}
                data-section={`problem-cost-${index + 1}`}
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

// === SECTION 7: SYSTEM SECTION ===
function SystemSection() {
  return (
    <section id="system" className="py-24" style={{ backgroundColor: WORKSPACE_SURFACE_PAGE_ALT }}>
      <div className="mx-auto max-w-7xl px-4">
        <div className="reveal-on-scroll mx-auto max-w-3xl text-center">
          <p
            className="mb-3 text-[13px] font-bold uppercase tracking-[0.22em]"
            data-section="system-eyebrow"
            style={{ color: WORKSPACE_CONTRAST_COLOR }}
          >
            {SYSTEM_CONTENT.eyebrow}
          </p>
          <h2
            className="mb-5 text-[36px] font-bold tracking-tight md:text-[48px]"
            data-section="system-title"
            style={{ color: WORKSPACE_TEXT_PRIMARY, fontFamily: WORKSPACE_FONT_FAMILY }}
          >
            {SYSTEM_CONTENT.title}
          </h2>
          <p className="text-[18px] leading-8" data-section="system-description" style={{ color: WORKSPACE_TEXT_SECONDARY }}>
            {SYSTEM_CONTENT.description}
          </p>
        </div>

        <div className="mt-14 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {SYSTEM_CAPABILITIES.map((cap, index) => (
            <article
              key={cap.title}
              className="reveal-on-scroll flex flex-col rounded-xl border p-7 shadow-md transition duration-300 hover:-translate-y-1 hover:shadow-lg"
              style={{ backgroundColor: WORKSPACE_SURFACE_PANEL, borderColor: WORKSPACE_BORDER_COLOR }}
            >
              <div className="mb-5 flex items-center justify-between">
                <span
                  className="text-[13px] font-bold"
                  style={{ color: WORKSPACE_PRIMARY_COLOR }}
                  data-section={`system-${index + 1}-index`}
                >
                  0{index + 1}
                </span>
                <span
                  className="rounded-full px-3 py-1 text-[12px] font-bold"
                  style={{ backgroundColor: WORKSPACE_SURFACE_ACCENT_SOFT, color: WORKSPACE_TEXT_PRIMARY }}
                  data-section={`system-${index + 1}-badge`}
                >
                  {cap.badge}
                </span>
              </div>
              <h3
                className="mb-3 text-[20px] font-bold"
                data-section={`system-${index + 1}-title`}
                style={{ color: WORKSPACE_TEXT_PRIMARY, fontFamily: WORKSPACE_FONT_FAMILY }}
              >
                {cap.title}
              </h3>
              <p className="leading-7" data-section={`system-${index + 1}-description`} style={{ color: WORKSPACE_TEXT_SECONDARY }}>
                {cap.description}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

// === SECTION 8: PRODUCT SECTION ===
function ProductSection() {
  return (
    <section id="product" className="py-24" style={{ backgroundColor: WORKSPACE_SURFACE_PAGE }}>
      <div className="mx-auto max-w-7xl px-4">
        <div className="reveal-on-scroll mx-auto max-w-3xl text-center">
          <p
            className="mb-3 text-[13px] font-bold uppercase tracking-[0.22em]"
            data-section="product-eyebrow"
            style={{ color: WORKSPACE_CONTRAST_COLOR }}
          >
            {PRODUCT_CONTENT.eyebrow}
          </p>
          <h2
            className="mb-5 text-[36px] font-bold tracking-tight md:text-[48px]"
            data-section="product-title"
            style={{ color: WORKSPACE_TEXT_PRIMARY, fontFamily: WORKSPACE_FONT_FAMILY }}
          >
            {PRODUCT_CONTENT.title}
          </h2>
          <p className="text-[18px] leading-8" data-section="product-description" style={{ color: WORKSPACE_TEXT_SECONDARY }}>
            {PRODUCT_CONTENT.description}
          </p>
        </div>

        <div className="mt-14 grid gap-6 lg:grid-cols-[1.35fr_0.65fr]">
          {/* Cases table */}
          <div
            className="reveal-on-scroll overflow-hidden rounded-2xl border shadow-md"
            style={{ backgroundColor: WORKSPACE_SURFACE_PANEL, borderColor: WORKSPACE_BORDER_STRONG_COLOR }}
          >
            <div className="flex items-center justify-between border-b px-6 py-5" style={{ borderColor: WORKSPACE_BORDER_COLOR }}>
              <div>
                <h3 className="text-[16px] font-bold" data-section="product-table-title" style={{ color: WORKSPACE_TEXT_PRIMARY }}>
                  {PRODUCT_CONTENT.tableTitle}
                </h3>
                <p className="text-[13px]" data-section="product-table-subtitle" style={{ color: WORKSPACE_TEXT_MUTED }}>
                  {PRODUCT_CONTENT.tableSubtitle}
                </p>
              </div>
              <span
                className="rounded-full px-3 py-1 text-[12px] font-bold"
                style={{ backgroundColor: WORKSPACE_SURFACE_ACCENT_SOFT, color: WORKSPACE_TEXT_PRIMARY }}
              >
                {PRODUCT_CASES.length} open
              </span>
            </div>

            <div
              className="grid grid-cols-[1.1fr_0.9fr_1fr_1fr_0.7fr] gap-2 px-6 py-3 text-[11px] font-bold uppercase tracking-wider"
              style={{ color: WORKSPACE_TEXT_MUTED, backgroundColor: WORKSPACE_SURFACE_PAGE_ALT }}
            >
              <span>Case</span>
              <span>Corridor</span>
              <span>Stage</span>
              <span>Status</span>
              <span className="text-right">Due</span>
            </div>

            <div>
              {PRODUCT_CASES.map((row, index) => {
                const pill = statusStyles(row.status);
                return (
                  <div
                    key={row.id}
                    className="grid grid-cols-[1.1fr_0.9fr_1fr_1fr_0.7fr] items-center gap-2 border-t px-6 py-4 text-[13px]"
                    style={{ borderColor: WORKSPACE_BORDER_COLOR }}
                    data-section={`product-case-${index + 1}`}
                  >
                    <span className="font-bold" style={{ color: WORKSPACE_TEXT_PRIMARY }}>
                      {row.id}
                    </span>
                    <span style={{ color: WORKSPACE_TEXT_SECONDARY }}>{row.corridor}</span>
                    <span style={{ color: WORKSPACE_TEXT_SECONDARY }}>{row.stage}</span>
                    <span>
                      <span
                        className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold"
                        style={{ backgroundColor: pill.bg, color: pill.color }}
                      >
                        <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: pill.color }} />
                        {row.status}
                      </span>
                    </span>
                    <span className="text-right font-semibold" style={{ color: WORKSPACE_TEXT_MUTED }}>
                      {row.due}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Timeline */}
          <div
            className="reveal-on-scroll rounded-2xl border p-6 shadow-md"
            style={{ backgroundColor: WORKSPACE_SURFACE_PANEL, borderColor: WORKSPACE_BORDER_STRONG_COLOR }}
          >
            <h3 className="text-[16px] font-bold" data-section="product-timeline-title" style={{ color: WORKSPACE_TEXT_PRIMARY }}>
              {PRODUCT_CONTENT.timelineTitle}
            </h3>
            <p className="mb-6 text-[13px]" data-section="product-timeline-subtitle" style={{ color: WORKSPACE_TEXT_MUTED }}>
              {PRODUCT_CONTENT.timelineSubtitle}
            </p>

            <ol className="relative space-y-5 pl-6">
              <span
                className="absolute left-[7px] top-1 bottom-1 w-px"
                style={{ backgroundColor: WORKSPACE_BORDER_STRONG_COLOR }}
                aria-hidden="true"
              />
              {PRODUCT_TIMELINE.map((step, index) => {
                const isDone = step.state === 'done';
                const isActive = step.state === 'active';
                const dot = isDone ? WORKSPACE_HIGHLIGHT_COLOR : isActive ? WORKSPACE_PRIMARY_COLOR : WORKSPACE_SURFACE_PANEL_STRONG;
                return (
                  <li key={step.label} className="relative" data-section={`product-timeline-step-${index + 1}`}>
                    <span
                      className="absolute -left-6 top-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full border-2"
                      style={{ backgroundColor: dot, borderColor: WORKSPACE_SURFACE_PANEL }}
                      aria-hidden="true"
                    />
                    <p
                      className="text-[14px] font-semibold"
                      style={{ color: step.state === 'upcoming' ? WORKSPACE_TEXT_MUTED : WORKSPACE_TEXT_PRIMARY }}
                    >
                      {step.label}
                    </p>
                    <p className="text-[12px]" style={{ color: WORKSPACE_TEXT_MUTED }}>
                      {isDone ? 'Complete' : isActive ? 'In progress' : 'Upcoming'}
                    </p>
                  </li>
                );
              })}
            </ol>
          </div>
        </div>
      </div>
    </section>
  );
}

// === SECTION 9: AUDIENCE SECTION ===
function AudienceSection() {
  return (
    <section id="audience" className="py-24" style={{ backgroundColor: WORKSPACE_SURFACE_PAGE_ALT }}>
      <div className="mx-auto max-w-7xl px-4">
        <div className="grid gap-12 lg:grid-cols-[1fr_1fr] lg:items-center">
          <div className="reveal-on-scroll">
            <p
              className="mb-3 text-[13px] font-bold uppercase tracking-[0.22em]"
              data-section="audience-eyebrow"
              style={{ color: WORKSPACE_CONTRAST_COLOR }}
            >
              {AUDIENCE_CONTENT.eyebrow}
            </p>
            <h2
              className="mb-5 text-[34px] font-bold tracking-tight md:text-[44px]"
              data-section="audience-title"
              style={{ color: WORKSPACE_TEXT_PRIMARY, fontFamily: WORKSPACE_FONT_FAMILY }}
            >
              {AUDIENCE_CONTENT.title}
            </h2>
            <p className="mb-6 text-[18px] leading-8" data-section="audience-description" style={{ color: WORKSPACE_TEXT_SECONDARY }}>
              {AUDIENCE_CONTENT.description}
            </p>
            <div
              className="rounded-xl border-l-4 px-5 py-4"
              style={{ borderColor: WORKSPACE_HIGHLIGHT_COLOR, backgroundColor: WORKSPACE_SURFACE_PANEL }}
            >
              <p className="text-[17px] font-bold" data-section="audience-promise" style={{ color: WORKSPACE_TEXT_PRIMARY }}>
                {AUDIENCE_CONTENT.promise}
              </p>
            </div>
          </div>

          <div className="reveal-on-scroll grid gap-4">
            {AUDIENCE_SECONDARY.map((mention, index) => (
              <article
                key={mention.title}
                className="rounded-xl border p-6 shadow-md"
                style={{ backgroundColor: WORKSPACE_SURFACE_PANEL, borderColor: WORKSPACE_BORDER_COLOR }}
              >
                <h3
                  className="mb-2 text-[16px] font-bold uppercase tracking-wide"
                  data-section={`audience-secondary-${index + 1}-title`}
                  style={{ color: WORKSPACE_PRIMARY_COLOR }}
                >
                  {mention.title}
                </h3>
                <p className="leading-7" data-section={`audience-secondary-${index + 1}-description`} style={{ color: WORKSPACE_TEXT_SECONDARY }}>
                  {mention.description}
                </p>
              </article>
            ))}
          </div>
        </div>

        {/* What ReloPass is / is not */}
        <div className="reveal-on-scroll mt-16">
          <p
            className="mb-3 text-[13px] font-bold uppercase tracking-[0.22em]"
            data-section="not-eyebrow"
            style={{ color: WORKSPACE_CONTRAST_COLOR }}
          >
            {NOT_CONTENT.eyebrow}
          </p>
          <h3
            className="mb-3 text-[26px] font-bold tracking-tight md:text-[32px]"
            data-section="not-title"
            style={{ color: WORKSPACE_TEXT_PRIMARY, fontFamily: WORKSPACE_FONT_FAMILY }}
          >
            {NOT_CONTENT.title}
          </h3>
          <p className="mb-8 max-w-2xl text-[16px] leading-8" data-section="not-description" style={{ color: WORKSPACE_TEXT_SECONDARY }}>
            {NOT_CONTENT.description}
          </p>
          <div className="grid gap-4 md:grid-cols-3">
            {NOT_ITEMS.map((item, index) => (
              <div
                key={item.not}
                className="rounded-xl border p-6"
                style={{ backgroundColor: WORKSPACE_SURFACE_PAGE, borderColor: WORKSPACE_BORDER_COLOR }}
                data-section={`not-item-${index + 1}`}
              >
                <p className="mb-2 text-[15px] font-bold" style={{ color: WORKSPACE_TEXT_MUTED }}>
                  {item.not}
                </p>
                <p className="text-[15px] leading-7" style={{ color: WORKSPACE_TEXT_PRIMARY }}>
                  {item.is}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

// === SECTION 10: CLOSING CTA ===
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
        <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
          <a
            href={DEMO_HREF}
            className="inline-flex rounded-lg px-8 py-4 text-lg font-bold shadow-md transition duration-300 hover:scale-105"
            style={{ backgroundColor: WORKSPACE_HIGHLIGHT_COLOR, color: WORKSPACE_TEXT_ON_HIGHLIGHT }}
            data-section="cta-primary"
          >
            {CTA_CONTENT.primaryCta}
          </a>
          <a
            href="#product"
            className="inline-flex rounded-lg border px-8 py-4 text-lg font-semibold transition duration-300 hover:scale-105"
            style={{ backgroundColor: WORKSPACE_SURFACE_PANEL, borderColor: WORKSPACE_BORDER_COLOR, color: WORKSPACE_TEXT_PRIMARY }}
            data-section="cta-secondary"
          >
            {CTA_CONTENT.secondaryCta}
          </a>
        </div>
        <p className="mt-6 text-sm" data-section="cta-contact" style={{ color: WORKSPACE_TEXT_MUTED }}>
          Or reach us directly at{' '}
          <a href={`mailto:${CONTACT_EMAIL}`} className="font-semibold underline" style={{ color: WORKSPACE_HIGHLIGHT_COLOR }}>
            {CONTACT_EMAIL}
          </a>
        </p>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t px-4 py-10" style={{ backgroundColor: WORKSPACE_SURFACE_PANEL, borderColor: WORKSPACE_BORDER_COLOR }}>
      <div className="mx-auto flex max-w-6xl flex-col gap-8 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="mb-3 flex items-center gap-3">
            {WORKSPACE_LOGO_URL ? (
              <div className="rounded-lg p-0.5 border" style={{ backgroundColor: WORKSPACE_SURFACE_PAGE, borderColor: WORKSPACE_BORDER_COLOR }}>
                <img src={WORKSPACE_LOGO_URL} alt={WORKSPACE_BRAND_NAME} className="h-7 w-7 object-contain" />
              </div>
            ) : (
              <span className="font-bold text-xl" style={{ color: WORKSPACE_PRIMARY_COLOR }}>{WORKSPACE_BRAND_NAME.charAt(0)}</span>
            )}
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

// === SECTION 11: MAIN COMPONENT AND ROOT RENDER ===
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

    upsertMeta('name', 'description', HERO_CONTENT?.subtitle || WORKSPACE_TAGLINE);
    upsertMeta('property', 'og:title', `${WORKSPACE_BRAND_NAME} — ${WORKSPACE_TAGLINE}`);
    upsertMeta('property', 'og:description', HERO_CONTENT?.subtitle || WORKSPACE_TAGLINE);
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
        <ProblemSection />
        <SystemSection />
        <ProductSection />
        <AudienceSection />
        <FinalCTA />
      </main>
      <Footer />
    </div>
  );
}

const container = document.getElementById('root')!;
const root = createRoot(container);
root.render(<LandingPage />);
