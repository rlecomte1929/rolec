import { Link } from 'react-router-dom';
import { Card } from './antigravity/Card';
import { Badge } from './antigravity/Badge';

interface WelcomeStepCardProps {
  step: number; // 1, 2, 3 …
  title: string;
  description: string; // one sentence max
  href: string; // internal route to navigate to
  badge?: string; // optional label, e.g. "Start here"
  note?: string; // optional footnote below the card
  /** When false, the card has no Get started link (later welcome steps). */
  showCta?: boolean;
  /** Visible + accessible CTA. Required when several cards share a page. */
  ctaLabel?: string;
}

/**
 * One numbered orientation step on a welcome page. The whole card is inert — only
 * the "Get started →" link navigates — so reading the card can't trigger an
 * accidental full-card navigation, and the link stays keyboard-accessible.
 */
export function WelcomeStepCard({
  step,
  title,
  description,
  href,
  badge,
  note,
  showCta = true,
  ctaLabel = 'Get started →',
}: WelcomeStepCardProps) {
  return (
    <div>
      <Card className="hover:border-accent-200 transition-colors duration-150">
        <div className="flex items-start gap-4">
          <div className="w-9 h-9 shrink-0 rounded-full bg-navy-800 text-white text-sm font-semibold flex items-center justify-center">
            {step}
          </div>
          <div className="flex-1 min-w-0">
            {badge && (
              <div className="mb-2">
                <Badge variant="info" size="sm">
                  {badge}
                </Badge>
              </div>
            )}
            <h3 className="text-base font-semibold text-navy-800">{title}</h3>
            <p className="text-sm text-slate-600 mt-1">{description}</p>
          </div>
          {showCta ? (
          <Link
            to={href}
            className="inline-flex min-h-6 shrink-0 items-center self-center text-sm font-medium text-accent-600 hover:text-accent-700 transition-colors"
          >
            {ctaLabel}
          </Link>
          ) : null}
        </div>
      </Card>
      {note && <p className="text-sm text-slate-500 mt-2 ml-[52px]">{note}</p>}
    </div>
  );
}
