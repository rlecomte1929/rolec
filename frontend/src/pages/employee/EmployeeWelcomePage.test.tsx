import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../utils/demo', () => ({ getAuthItem: () => 'u-1' }));
vi.mock('../../utils/welcomeSeen', () => ({ markWelcomeSeen: vi.fn() }));
vi.mock('../../api/welcome', () => ({ persistWelcomeSeen: vi.fn(() => Promise.resolve()) }));
vi.mock('../../components/WelcomeShell', () => ({
  WelcomeShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import { EmployeeWelcomePage } from './EmployeeWelcomePage';

afterEach(cleanup);

function renderPage() {
  return render(
    <MemoryRouter>
      <EmployeeWelcomePage />
    </MemoryRouter>,
  );
}

/** Consecutive heading levels must not jump by more than 1 (WCAG 1.3.1). */
function headingLevels(container: HTMLElement): number[] {
  return Array.from(container.querySelectorAll('h1,h2,h3,h4,h5,h6')).map((h) =>
    Number(h.tagName[1]),
  );
}

describe('EmployeeWelcomePage CTAs', () => {
  it('has a single Get started link plus the primary intake button', () => {
    renderPage();
    expect(screen.getAllByText('Get started →')).toHaveLength(1);
    expect(screen.getByRole('button', { name: /begin the intake form/i })).toBeInTheDocument();
  });
});

describe('EmployeeWelcomePage heading outline', () => {
  it('opens with h1, then a section h2, then step-card h3s — no skipped level', () => {
    const { container } = renderPage();

    expect(screen.getByRole('heading', { level: 1, name: /your relocation starts here/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: /how it works/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: /tell us about your move/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: /get your personalised roadmap/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: /find the services you need/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: /questions before you start/i })).toBeInTheDocument();

    const levels = headingLevels(container);
    expect(levels[0], 'page must open with its h1').toBe(1);
    for (let i = 1; i < levels.length; i += 1) {
      expect(
        levels[i]! - levels[i - 1]!,
        `heading ${i} (h${levels[i]}) skips a level after h${levels[i - 1]}: ${levels.join(' -> ')}`,
      ).toBeLessThanOrEqual(1);
    }
  });
});
