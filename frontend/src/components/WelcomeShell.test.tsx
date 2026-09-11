import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { WelcomeShell } from './WelcomeShell';

vi.mock('./AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

describe('WelcomeShell', () => {
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
