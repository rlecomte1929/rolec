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
import { AccessPage } from '../../../pages/public/AccessPage';
import { PlatformPage } from '../../../pages/public/PlatformPage';
import { PublicLayout } from '../PublicLayout';

// jsdom ships no matchMedia; FadeIn reads prefers-reduced-motion on mount. This lived
// inside the /platform describe, which made every OTHER describe in this file silently
// depend on /platform's beforeAll having run first — the /access outline test below passes
// in a full-file run and throws when run on its own with -t. File-level, so the order of
// describes cannot matter.
beforeAll(() => {
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


describe('/access — heading outline must not skip a level', () => {
  it('goes h1 -> h2 with no h3 in between', () => {
    // The three option cards ("Book a demo" / "Sign in" / "Create account") are the page's
    // top-level sections under its single h1, but were marked h3 — so the outline jumped
    // h1 -> h3 (WCAG 1.3.1). Worse, the page's one other body heading ("what the demo
    // covers") is an h2 that renders AFTER them, so the first h2 was preceded by three h3s.
    //
    // Asserting the SEQUENCE rather than "no h3 exists": the defect is the gap between
    // levels, and a sequence assertion still catches it if someone later adds a legitimate
    // h3 nested under one of these h2s.
    const { container } = render(
      <MemoryRouter>
        <DemoBookingProvider>
          <AccessPage />
        </DemoBookingProvider>
      </MemoryRouter>,
    );

    const levels = Array.from(container.querySelectorAll('h1,h2,h3,h4,h5,h6')).map((h) =>
      Number(h.tagName[1]),
    );

    expect(levels[0], 'page must open with its h1').toBe(1);
    for (let i = 1; i < levels.length; i += 1) {
      expect(
        levels[i]! - levels[i - 1]!,
        `heading ${i} (h${levels[i]}) skips a level after h${levels[i - 1]}: ${levels.join(' -> ')}`,
      ).toBeLessThanOrEqual(1);
    }
  });
});
