/**
 * Public-chrome regressions found by the qa.replay.io sweep (2026-08-27).
 *
 * Two defects, both invisible to the existing gates:
 *
 *   1. The /platform hero button labelled "Sign in" navigated to /how-it-works.
 *      Filed as a WCAG 3.2.4 "inconsistent accessible name", but it is a wiring
 *      bug: anyone trying to log in from that page landed on a marketing page.
 *   2. No public route had a skip-to-content link. AppShell and AdminLayout have
 *      had one since AIQ-397; PublicLayout never did, so all six public routes
 *      forced keyboard users through the full nav. The axe gate scans only
 *      /, /auth and two employee routes, so it never asked.
 */
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeAll, describe, expect, it } from 'vitest';
import { DemoBookingProvider } from '../../../hooks/useDemoBooking';
import { PlatformPage } from '../../../pages/public/PlatformPage';
import { PublicLayout } from '../PublicLayout';

describe('PublicLayout — keyboard bypass', () => {
  const renderLayout = () =>
    render(
      <MemoryRouter>
        <DemoBookingProvider>
          <PublicLayout>
            <p>page body</p>
          </PublicLayout>
        </DemoBookingProvider>
      </MemoryRouter>,
    );

  it('offers a skip-to-content link', () => {
    renderLayout();
    const skip = screen.getByRole('link', { name: /skip to main content/i });
    expect(skip).toHaveAttribute('href', '#main-content');
  });

  it('points that link at a main landmark that actually exists', () => {
    // A skip link whose target id is missing is worse than none — focus goes nowhere.
    const { container } = renderLayout();
    const main = container.querySelector('main#main-content');
    expect(main).not.toBeNull();
  });

  it('keeps the skip link visually hidden until focused', () => {
    renderLayout();
    // sr-only until :focus — it must not intrude on the visual design.
    expect(screen.getByRole('link', { name: /skip to main content/i }).className)
      .toMatch(/\bsr-only\b/);
  });
});


describe('/platform hero — "Sign in" must go to the login screen', () => {
  beforeAll(() => {
    // jsdom ships no matchMedia; FadeIn reads prefers-reduced-motion on mount.
    if (!window.matchMedia) {
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: (query: string) => ({
          matches: false,
          media: query,
          onchange: null,
          addEventListener: () => {},
          removeEventListener: () => {},
          addListener: () => {},
          removeListener: () => {},
          dispatchEvent: () => false,
        }),
      });
    }
  });

  it('does not send the Sign in CTA to /how-it-works', () => {
    render(
      <MemoryRouter>
        <DemoBookingProvider>
          <PlatformPage />
        </DemoBookingProvider>
      </MemoryRouter>,
    );
    // There are two "Sign in" links on this page (hero + footer CTA block). BOTH must
    // land on the auth screen; the hero one used to point at /how-it-works.
    const signIns = screen.getAllByRole('link', { name: /^sign in$/i });
    expect(signIns.length).toBeGreaterThan(0);
    for (const link of signIns) {
      expect(link.getAttribute('href')).toMatch(/\/auth/);
      expect(link.getAttribute('href')).not.toMatch(/how-it-works/);
    }
  });
});
