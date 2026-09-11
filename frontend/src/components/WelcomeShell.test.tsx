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
    expect(screen.getByRole('button', { name: 'Open Cases →' }).className).toContain('min-h-6');
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

  it('can widen the content column for a two-pane HR layout', () => {
    render(
      <MemoryRouter>
        <WelcomeShell onSkip={() => undefined} hideSkip wide>
          <p>welcome</p>
        </WelcomeShell>
      </MemoryRouter>,
    );
    const column = screen.getByTestId('welcome-shell').querySelector('.animate-fade-in');
    expect(column?.className).toContain('max-w-5xl');
    expect(column?.className).not.toContain('max-w-2xl');
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
