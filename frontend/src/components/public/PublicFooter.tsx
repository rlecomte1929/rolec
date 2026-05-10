import React from 'react';
import { Link } from 'react-router-dom';
import { Container } from '../antigravity';
import { ROUTE_DEFS } from '../../navigation/routes';
import { useDemoBooking } from '../../hooks/useDemoBooking';

const CONTACT_EMAIL = 'mailto:contact@relopass.com?subject=ReloPass%20Inquiry';

const PRODUCT_LINKS = [
  { label: 'Platform', path: ROUTE_DEFS.platform.path },
  { label: 'Why ReloPass', path: ROUTE_DEFS.why.path },
  { label: 'How it works', path: ROUTE_DEFS.howItWorks.path },
  { label: 'Security', path: ROUTE_DEFS.security.path },
  { label: 'Privacy', path: ROUTE_DEFS.privacy.path },
  { label: 'Get started', path: ROUTE_DEFS.access.path },
] as const;

const COMPANY_LINKS = [
  { label: 'Sign in', path: `${ROUTE_DEFS.auth.path}?mode=login` },
  { label: 'Create account', path: `${ROUTE_DEFS.auth.path}?mode=register` },
] as const;

export const PublicFooter: React.FC = () => {
  const { open: openDemoBooking } = useDemoBooking();
  return (
    <footer className="border-t border-marketing-border bg-marketing-surface-muted">
      <Container maxWidth="xl" className="py-8 sm:py-10">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-10 lg:gap-12">
          <div className="lg:col-span-1">
            <h4 className="text-xs font-bold uppercase tracking-wider text-black mb-4">
              Contact
            </h4>
            <p className="text-sm text-marketing-text-muted leading-relaxed max-w-[260px]">
              Tell us how your relocations run today. We'll show you what changes.
            </p>
            <div className="mt-4">
              <a
                href={CONTACT_EMAIL}
                className="text-sm text-marketing-text-subtle hover:text-marketing-text-muted transition-colors"
              >
                contact@relopass.com
              </a>
            </div>
          </div>

          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-black mb-4">
              Product
            </h4>
            <ul className="space-y-3">
              {PRODUCT_LINKS.map((link) => (
                <li key={link.path}>
                  <Link
                    to={link.path}
                    className="text-sm text-marketing-text-muted hover:text-marketing-primary transition-colors"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-black mb-4">
              Company
            </h4>
            <ul className="space-y-3">
              <li>
                <Link
                  to={COMPANY_LINKS[0].path}
                  className="text-sm text-marketing-text-muted hover:text-marketing-primary transition-colors"
                >
                  {COMPANY_LINKS[0].label}
                </Link>
              </li>
              <li>
                <button
                  type="button"
                  onClick={() => openDemoBooking('public-footer')}
                  className="text-sm text-marketing-text-muted hover:text-marketing-primary transition-colors"
                >
                  Book a demo
                </button>
              </li>
              <li>
                <Link
                  to={COMPANY_LINKS[1].path}
                  className="text-sm text-marketing-text-muted hover:text-marketing-primary transition-colors"
                >
                  {COMPANY_LINKS[1].label}
                </Link>
              </li>
            </ul>
          </div>

          <div />
        </div>

        <div className="mt-8 pt-6 border-t border-marketing-border-subtle flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <p className="text-xs text-marketing-text-subtle">
            Informational guidance only. ReloPass does not provide legal advice.
          </p>
          <div className="flex items-center gap-4">
            <p className="text-xs text-marketing-text-subtle">
              © {new Date().getFullYear()} ReloPass. All rights reserved.
            </p>
            <img
              src="/relopass-full-logo.png?v=1"
              alt="ReloPass"
              className="h-20 w-auto sm:h-24"
            />
          </div>
        </div>
      </Container>
    </footer>
  );
};
