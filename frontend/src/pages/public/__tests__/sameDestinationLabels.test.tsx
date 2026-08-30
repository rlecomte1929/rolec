/**
 * WCAG 3.2.4 Consistent Identification — one destination, one name.
 *
 * Links that go to the same place must be named the same, or a screen-reader user listing
 * the links on a page sees three destinations where there is one.
 *
 * WHY THIS RENDERS THE PAGE INSTEAD OF ASSERTING ON THE CONTENT MODULE.
 * PR #2074 tried to fix exactly this and changed nothing a visitor could see: it edited
 * `src/pages/public/landingContent.ts`, which had ZERO importers. The live copy is
 * `src/pages/landing/landingContent.ts`. Both exported `landingContent`, both had a
 * `hero.primaryCta`, and the dead one even held the *corrected* string — so the diff looked
 * right, review looked right, and the landing hero still read "Structure how you run
 * relocation. Start with one case." next to a nav link reading "Get started".
 *
 * The dead file has since been deleted, but the lesson stands and this test is what enforces
 * it: assert against the RENDERED route, never against a content module by name.
 *
 * A content-module assertion would have passed against the dead file just as happily.
 * Rendering the route is the only form of this test that cannot be fooled by that.
 */
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeAll, describe, expect, it } from 'vitest';
import { DemoBookingProvider } from '../../../hooks/useDemoBooking';
import { Landing } from '../../Landing';
import { WhyReloPassPage } from '../WhyReloPassPage';

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

/** Accessible name of a link, as a screen reader would announce it. */
function nameOf(el: Element): string {
  return (el.getAttribute('aria-label') ?? el.textContent ?? '').replace(/\s+/g, ' ').trim();
}

function namesForHref(container: HTMLElement, href: string): string[] {
  return Array.from(container.querySelectorAll(`a[href="${href}"]`)).map(nameOf);
}

function renderPage(ui: React.ReactElement) {
  return render(
    <MemoryRouter>
      <DemoBookingProvider>{ui}</DemoBookingProvider>
    </MemoryRouter>,
  );
}

describe('WCAG 3.2.4 — same destination, same accessible name', () => {
  it('every /access link on the landing page shares one name', () => {
    const { container } = renderPage(<Landing />);
    const names = namesForHref(container, '/access');
    expect(names.length, 'expected the nav, footer and hero links to /access').toBeGreaterThan(1);
    expect(new Set(names), `/access links disagree: ${JSON.stringify(names)}`).toHaveProperty('size', 1);
  });

  it('every /platform link on the landing page shares one name', () => {
    const { container } = renderPage(<Landing />);
    const names = namesForHref(container, '/platform');
    expect(names.length).toBeGreaterThan(1);
    expect(new Set(names), `/platform links disagree: ${JSON.stringify(names)}`).toHaveProperty('size', 1);
  });

  it('every /platform link on /why shares one name', () => {
    const { container } = renderPage(<WhyReloPassPage />);
    const names = namesForHref(container, '/platform');
    expect(names.length, 'expected the nav, footer and hero CTA links to /platform').toBeGreaterThan(1);
    expect(new Set(names), `/platform links disagree: ${JSON.stringify(names)}`).toHaveProperty('size', 1);
  });
});
