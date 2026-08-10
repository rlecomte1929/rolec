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

export interface PrerenderedRoute {
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
];
