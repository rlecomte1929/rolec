/**
 * Focused public-marketing a11y lock: heading outline, named controls, imaged alt.
 *
 * Representative pages only (homepage + one paid-ad landing). Does not claim
 * WCAG conformance for the whole app.
 */
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeAll, describe, expect, it } from 'vitest';
import { DemoBookingProvider } from '../../../hooks/useDemoBooking';
import { Landing } from '../../Landing';
import { MobilityTeamsPage } from '../MobilityTeamsPage';

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

function renderPage(ui: React.ReactElement) {
  return render(
    <MemoryRouter>
      <DemoBookingProvider>{ui}</DemoBookingProvider>
    </MemoryRouter>,
  );
}

function expectNoSkippedHeadingLevel(container: HTMLElement) {
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
}

function expectNamedControls() {
  for (const el of screen.getAllByRole('button')) {
    expect(el).toHaveAccessibleName();
  }
  for (const el of screen.getAllByRole('link')) {
    expect(el).toHaveAccessibleName();
  }
}

function expectImagesHaveAlt(container: HTMLElement) {
  for (const img of Array.from(container.querySelectorAll('img'))) {
    expect(img, `img src=${img.getAttribute('src') ?? '(none)'} is missing alt`).toHaveAttribute('alt');
    const alt = img.getAttribute('alt');
    if (alt === '') {
      expect(
        img.getAttribute('aria-hidden'),
        `decorative img src=${img.getAttribute('src') ?? '(none)'} needs aria-hidden`,
      ).toBe('true');
    }
  }
}

describe('Landing — public a11y', () => {
  it('heading outline does not skip a level', () => {
    const { container } = renderPage(<Landing />);
    expectNoSkippedHeadingLevel(container);
  });

  it('buttons and links have an accessible name', () => {
    renderPage(<Landing />);
    expectNamedControls();
  });

  it('images have alt (empty only when decorative and hidden)', () => {
    const { container } = renderPage(<Landing />);
    expectImagesHaveAlt(container);
  });
});

describe('/mobility-teams — public a11y', () => {
  it('heading outline does not skip a level', () => {
    const { container } = renderPage(<MobilityTeamsPage />);
    expectNoSkippedHeadingLevel(container);
  });

  it('buttons and links have an accessible name', () => {
    renderPage(<MobilityTeamsPage />);
    expectNamedControls();
  });

  it('images have alt (empty only when decorative and hidden)', () => {
    const { container } = renderPage(<MobilityTeamsPage />);
    expectImagesHaveAlt(container);
  });
});
