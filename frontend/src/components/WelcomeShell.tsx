import React from 'react';
import { AppShell } from './AppShell';

interface WelcomeShellProps {
  onSkip: () => void; // called when the user clicks the "skip" link
  skipLabel?: string;
  children: React.ReactNode;
}

/**
 * Thin scaffold shared by the HR and employee welcome pages. Renders inside the
 * authenticated AppShell (sidebar + topbar stay visible — this is not a modal or a
 * full-screen takeover). AppShell already owns the page background, scroll region,
 * and horizontal padding, so this only centres a max-w-2xl content column and adds
 * the low-weight skip link. No AppShell title is passed — each welcome page supplies
 * its own eyebrow + headline as the heading.
 */
export function WelcomeShell({
  onSkip,
  skipLabel = 'Skip, go to dashboard →',
  children,
}: WelcomeShellProps) {
  return (
    <AppShell>
      <div
        className="flex flex-col items-center pt-4 px-2 pb-[max(3rem,var(--consent-banner-offset,0px))]"
        data-testid="welcome-shell"
      >
        {/* Skip link — top right, low visual weight */}
        <div className="w-full max-w-2xl flex justify-end mb-8">
          <button
            onClick={onSkip}
            className="text-sm text-slate-500 hover:text-slate-700 hover:underline transition-colors"
          >
            {skipLabel}
          </button>
        </div>

        {/* Content slot */}
        <div className="w-full max-w-2xl animate-fade-in">{children}</div>
      </div>
    </AppShell>
  );
}
