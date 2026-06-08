import React from 'react';
import { Button } from '../antigravity/Button';
import { Link } from 'react-router-dom';
import { Container } from '../antigravity';
import { ROUTE_DEFS } from '../../navigation/routes';
import { useDemoBooking } from '../../hooks/useDemoBooking';

const CONTACT_EMAIL = 'mailto:contact@relopass.com?subject=ReloPass%20Inquiry';

const PRODUCT_LINKS = [
  { label: 'Platform', path: ROUTE_DEFS.platform.path },
  { label: 'How it works', path: ROUTE_DEFS.howItWorks.path },
  { label: 'Why ReloPass', path: ROUTE_DEFS.why.path },
  { label: 'Get started', path: ROUTE_DEFS.access.path },
] as const;

const LEGAL_LINKS = [
  { label: 'Privacy policy', path: ROUTE_DEFS.privacy.path },
  { label: 'Security', path: ROUTE_DEFS.security.path },
] as const;

export const PublicFooter: React.FC = () => {
  const { open: openDemoBooking } = useDemoBooking();
  return (
    <footer className="border-t border-marketing-border bg-marketing-surface-muted">
      <Container maxWidth="xl" className="py-8 sm:py-10">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-10 lg:gap-12">
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
                  to={`${ROUTE_DEFS.auth.path}?mode=login`}
                  className="text-sm text-marketing-text-muted hover:text-marketing-primary transition-colors"
                >
                  Sign in
                </Link>
              </li>
              <li>
                <Button unstyled
                  type="button"
                  onClick={() => openDemoBooking('public-footer')}
                  className="text-sm text-marketing-text-muted hover:text-marketing-primary transition-colors"
                >
                  Book a demo
                </Button>
              </li>
              <li className="pt-2">
                <a
                  href={CONTACT_EMAIL}
                  className="text-sm text-marketing-text-subtle hover:text-marketing-text-muted transition-colors"
                >
                  contact@relopass.com
                </a>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-black mb-4">
              Legal
            </h4>
            <ul className="space-y-3">
              {LEGAL_LINKS.map((link) => (
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
        </div>

        <div className="mt-8 pt-6 border-t border-marketing-border-subtle flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <p className="text-sm font-medium text-marketing-text-muted">
            ReloPass — Global mobility infrastructure.
          </p>
          <div className="flex items-center gap-4">
            <p className="text-xs text-marketing-text-subtle">
              © {new Date().getFullYear()} ReloPass. All rights reserved.
            </p>
            <img
              src="/relopass-full-logo.png?v=2"
              alt="ReloPass"
              className="h-20 w-auto sm:h-24"
            />
          </div>
        </div>
      </Container>
    </footer>
  );
};
