/**
 * [AIQ-1783] SSR entry used ONLY at build time to prerender the paid-ad landing pages.
 *
 * Why this exists: the app ships as a Vite SPA on a Render static site, so a normal
 * route returns index.html with an empty #root. OAI-AdsBot would see a blank page and
 * the ads would point at nothing. Rendering these two routes to real HTML at build time
 * is crawler-equivalent to SSR without migrating the app to an SSR framework.
 *
 * This is NOT part of the client bundle — it is compiled separately by
 * `vite build --ssr` and consumed by scripts/prerender.mjs.
 *
 * Note on <head>: usePageMeta sets title/description inside useEffect, which never runs
 * during SSR. So each route exports its meta here and the script injects it. Without
 * that, every prerendered page would inherit index.html's generic title — which for an
 * ad landing page is a real cost, not a cosmetic one.
 */
import React from 'react';
import { renderToString } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { DemoBookingProvider } from './hooks/useDemoBooking';
import { MobilityTeamsPage } from './pages/public/MobilityTeamsPage';
import { RelocationChecklistPage } from './pages/public/RelocationChecklistPage';
import { mobilityTeamsContent, relocationChecklistContent } from './pages/public/adLandingContent';
// [AIQ-1797] The 8 PUBLIC marketing routes.
import { Landing } from './pages/Landing';
import { PlatformPage } from './pages/public/PlatformPage';
import { WhyReloPassPage } from './pages/public/WhyReloPassPage';
import { HowItWorksPage } from './pages/public/HowItWorksPage';
import { GetStartedPage } from './pages/public/GetStartedPage';
import { SecurityPage } from './pages/public/SecurityPage';
import { PrivacyPage } from './pages/public/PrivacyPage';
import { AccessPage } from './pages/public/AccessPage';

export interface PrerenderedRoute {
  /**
   * [AIQ-1797] Emit to dist/<outFile> instead of dist/<path>/index.html.
   *
   * Needed only by `/`, whose default output path would collapse to dist/index.html
   * anyway — stating it explicitly is what keeps that from looking like an accident.
   * See the comment at the write site in scripts/prerender.mjs.
   */
  outFile?: string;
  /** URL path, also the output directory: dist/<dir>/index.html */
  path: string;
  title: string;
  description: string;
  render: () => string;
}

function renderAt(path: string, node: React.ReactElement): string {
  return renderToString(
    <MemoryRouter initialEntries={[path]}>
      <DemoBookingProvider>{node}</DemoBookingProvider>
    </MemoryRouter>,
  );
}

export const ROUTES: PrerenderedRoute[] = [
  {
    path: '/mobility-teams',
    title: mobilityTeamsContent.meta.title,
    description: mobilityTeamsContent.meta.description,
    render: () => renderAt('/mobility-teams', <MobilityTeamsPage />),
  },
  {
    path: '/relocation-checklist',
    title: relocationChecklistContent.meta.title,
    description: relocationChecklistContent.meta.description,
    render: () => renderAt('/relocation-checklist', <RelocationChecklistPage />),
  },

  // ── [AIQ-1797] The 8 PUBLIC marketing routes ───────────────────────────────
  //
  // Every one of these served the 1,677-byte SPA shell — ~82 readable characters —
  // to any client that does not run JavaScript. Measured 2026-08-11 across all 8,
  // in both bare and trailing-slash form. That is what a search crawler and an AI
  // answer engine read today, so none of this copy can be ranked or cited.
  //
  // WHY THESE 8 AND NOT "EVERY PUBLIC ROUTE". ROUTE_DEFS marks more paths PUBLIC
  // than belong here, and prerendering some of them would be wrong rather than
  // merely wasteful:
  //   /auth, /login                  — credential surfaces, no marketing content
  //   /provider/portal, /supplier/quote — render per-magic-link content; a static
  //                                    snapshot would be meaningless at best
  //   /test-drive, /test-drive/survey — interactive trial, not copy to index
  //   /compliance                    — deliberately out of scope: its copy is
  //                                    governed by the EU AI Act hard gate in
  //                                    CLAUDE.md, so baking it into static HTML is
  //                                    a content decision, not a build one
  //   /mobility-teams, /relocation-checklist — already prerendered above
  //
  // The meta below is duplicated from each page's usePageMeta call, because that
  // call passes inline literals rather than exporting them (unlike the ad pages,
  // which read adLandingContent.ts). scripts/verify-prerender.mjs asserts the two
  // agree, so drift fails the build instead of silently shipping a wrong <title>.
  {
    path: '/',
    // dist/index.html, deliberately. A rewrite cannot serve `/` — Render skips redirect and
    // rewrite rules whenever a resource already exists at the path, and index.html always
    // does. The shell moved to dist/app.html instead; `/*` points there.
    outFile: 'index.html',
    title: 'ReloPass — Global mobility infrastructure',
    description:
      'Run relocation cases, timelines, documents, providers, and policy controls through one operating layer.',
    render: () => renderAt('/', <Landing />),
  },
  {
    path: '/platform',
    title: 'The Platform · ReloPass',
    description:
      'Every relocation on one system of record. Cases, documents, providers, and progress in one place.',
    render: () => renderAt('/platform', <PlatformPage />),
  },
  {
    path: '/why',
    title: 'Why ReloPass',
    description:
      'Relocation fails in the handoffs. ReloPass puts every case, document, and provider update on one record.',
    render: () => renderAt('/why', <WhyReloPassPage />),
  },
  {
    path: '/how-it-works',
    title: 'How It Works · ReloPass',
    description:
      'From case open to case closed. Four steps, one record. See how a relocation runs inside ReloPass.',
    render: () => renderAt('/how-it-works', <HowItWorksPage />),
  },
  {
    path: '/get-started',
    title: 'Get started · ReloPass',
    description:
      "Three ways in. Book a demo, sign in, or create an account. Tell us how your relocations run today and we'll show you what changes.",
    render: () => renderAt('/get-started', <GetStartedPage />),
  },
  {
    path: '/security',
    title: 'Security · ReloPass',
    description:
      'Data hosted in the EU, encrypted in transit and at rest. Role-based access throughout.',
    render: () => renderAt('/security', <SecurityPage />),
  },
  {
    path: '/privacy',
    title: 'Privacy Policy · ReloPass',
    description: 'How ReloPass collects, stores, and protects your data. Hosted in the EU.',
    render: () => renderAt('/privacy', <PrivacyPage />),
  },
  {
    path: '/access',
    title: 'Get Started · ReloPass',
    description: 'Book a demo, sign in, or create an account. 30-minute walkthrough. No commitment.',
    render: () => renderAt('/access', <AccessPage />),
  },
];
