import React from 'react';
import { PublicHeader } from './PublicHeader';
import { PublicFooter } from './PublicFooter';
import { BackToTop } from './BackToTop';

interface PublicLayoutProps {
  children: React.ReactNode;
  /** Max width of main content: 'default' (72rem) | 'narrow' (48rem) | 'wide' (80rem) | 'full' */
  maxWidth?: 'default' | 'narrow' | 'wide' | 'full';
  /** Remove top/bottom padding for full-bleed sections */
  noPadding?: boolean;
  /** Additional class for main */
  mainClassName?: string;
}

export const PublicLayout: React.FC<PublicLayoutProps> = ({
  children,
  maxWidth = 'default',
  noPadding = false,
  mainClassName = '',
}) => {
  const containerWidth =
    maxWidth === 'narrow'
      ? 'max-w-marketing-narrow'
      : maxWidth === 'wide'
        ? 'max-w-marketing-wide'
        : maxWidth === 'full'
          ? 'max-w-full'
          : 'max-w-marketing';

  return (
    <div className="min-h-screen flex flex-col bg-marketing-surface-subtle text-marketing-text">
      {/* Skip-link for keyboard users — same pattern as AppShell/AdminLayout (AIQ-397),
          which the authenticated and admin shells have had all along. Every public route
          renders through this layout, so one link covers /platform, /why, /how-it-works,
          /privacy, /security and /access. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-[#0b2b43] focus:px-3 focus:py-2 focus:text-sm focus:font-semibold focus:text-white focus:shadow-lg"
      >
        Skip to main content
      </a>
      <PublicHeader />
      <main
        id="main-content"
        tabIndex={-1}
        className={`flex-1 w-full min-w-0 outline-none ${noPadding ? '' : 'pt-6 sm:pt-8 md:pt-10 pb-12 sm:pb-16 md:pb-20'} ${mainClassName}`}
      >
        <div
          className={`mx-auto w-full max-w-full px-4 sm:px-6 lg:px-8 ${containerWidth} ${
            noPadding ? '' : 'py-0'
          }`}
        >
          {children}
        </div>
      </main>
      <PublicFooter />
      <BackToTop />
    </div>
  );
};
