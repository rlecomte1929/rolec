import React from 'react';
import { Link } from 'react-router-dom';
import { Container } from '../antigravity';
import { ROUTE_DEFS } from '../../navigation/routes';

const CONTACT_EMAIL = 'mailto:hello@relopass.com?subject=ReloPass%20Inquiry';

const FOOTER_LINKS = {
  product: [
    { label: 'Platform', path: ROUTE_DEFS.platform.path },
    { label: 'Why ReloPass', path: ROUTE_DEFS.why.path },
    { label: 'How it works', path: ROUTE_DEFS.trust.path },
    { label: 'Get started', path: ROUTE_DEFS.access.path },
  ],
  company: [
    { label: 'Sign in', path: `${ROUTE_DEFS.auth.path}?mode=login` },
    { label: 'Book a demo', path: ROUTE_DEFS.access.path },
    { label: 'Create account', path: `${ROUTE_DEFS.auth.path}?mode=register` },
  ],
} as const;

export const PublicFooter: React.FC = () => {
  return (
    <footer className="border-t border-marketing-border bg-marketing-surface-muted">
      <Container maxWidth="xl" className="py-12 sm:py-16">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-10 lg:gap-12">
          <div className="lg:col-span-1">
            <h4 className="text-xs font-bold uppercase tracking-wider text-black mb-4">
              Contact
            </h4>
            <p className="text-sm text-marketing-text-muted leading-relaxed max-w-[260px]">
              Talk to us about your relocation process, current challenges, or how ReloPass could fit your team.
            </p>
            <div className="mt-4 flex flex-col gap-2">
              <a
                href={CONTACT_EMAIL}
                className="text-sm font-bold text-black hover:opacity-80 transition-opacity"
              >
                Contact us
              </a>
              <a
                href={CONTACT_EMAIL}
                className="text-sm text-marketing-text-subtle hover:text-marketing-text-muted transition-colors"
              >
                hello@relopass.com
              </a>
            </div>
          </div>

          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-black mb-4">
              Product
            </h4>
            <ul className="space-y-3">
              {FOOTER_LINKS.product.map((link) => (
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
              {FOOTER_LINKS.company.map((link) => (
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

          <div />
        </div>

        <div className="mt-12 pt-8 border-t border-marketing-border-subtle flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <p className="text-xs text-marketing-text-subtle">
            Informational guidance only. ReloPass does not provide legal advice.
          </p>
          <p className="text-xs text-marketing-text-subtle">
            © {new Date().getFullYear()} ReloPass. All rights reserved.
          </p>
        </div>
      </Container>
    </footer>
  );
};
