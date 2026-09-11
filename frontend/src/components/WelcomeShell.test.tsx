import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { WelcomeShell } from './WelcomeShell';

vi.mock('./AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

describe('WelcomeShell', () => {
  it('uses the skip label that names the real destination', () => {
    render(
      <MemoryRouter>
        <WelcomeShell onSkip={() => undefined} skipLabel="Open Cases →">
          <p>welcome</p>
        </WelcomeShell>
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: 'Open Cases →' })).toBeInTheDocument();
  });

  it('can hide the top skip so the page owns a single bottom exit', () => {
    render(
      <MemoryRouter>
        <WelcomeShell onSkip={() => undefined} hideSkip>
          <p>welcome</p>
        </WelcomeShell>
      </MemoryRouter>,
    );
    expect(screen.queryByRole('button', { name: /open cases|skip/i })).not.toBeInTheDocument();
  });

  it('reserves bottom space for the analytics consent banner', () => {
    render(
      <MemoryRouter>
        <WelcomeShell onSkip={() => undefined}>
          <button type="button">Go to the Command Center</button>
        </WelcomeShell>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('welcome-shell').className).toContain('--consent-banner-offset');
  });
});
