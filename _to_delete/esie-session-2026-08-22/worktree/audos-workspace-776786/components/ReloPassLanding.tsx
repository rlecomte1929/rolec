import { useEffect, useState } from 'react';
import {
  ArrowRight,
  FileSearch,
  ScanLine,
  UserCheck,
  Check,
} from 'lucide-react';
import { landingContent, assetUrl } from './landingContent';

const PROOF_ICONS = {
  FileSearch,
  ScanLine,
  UserCheck,
} as const;

export interface ReloPassLandingProps {
  onPrimaryCta?: () => void;
  onSecondaryCta?: () => void;
  onSignIn?: () => void;
  onPlatformTour?: () => void;
  logoUrl?: string;
  brandName?: string;
  scrollRootClass?: string;
}

export function ReloPassLanding({
  onPrimaryCta,
  onSecondaryCta,
  onSignIn,
  onPlatformTour,
  logoUrl = assetUrl('relopass-full-logo.png'),
  brandName = 'ReloPass',
  scrollRootClass = 'rp-root',
}: ReloPassLandingProps) {
  const c = landingContent;
  const [scrolled, setScrolled] = useState(false);

  // Legal disclaimer is scoped to the /test-drive page only (founder request):
  // it renders when the visitor arrived via the /test-drive URL path or the
  // #/test-drive hash route, and stays hidden on the plain homepage.
  const isTestDrivePage = (() => {
    try {
      const path = window.location.pathname.replace(/\/+$/, '');
      const hashPath = window.location.hash.replace(/^#\/?/, '').split('?')[0].replace(/\/+$/, '');
      return path.endsWith('/test-drive') || hashPath === 'test-drive';
    } catch {
      return false;
    }
  })();

  useEffect(() => {
    const root = document.querySelector(`.${scrollRootClass}`);
    if (!root) return;
    const onScroll = () => setScrolled(root.scrollTop > 24);
    root.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => root.removeEventListener('scroll', onScroll);
  }, [scrollRootClass]);

  const trackEvent = (name: string) => {
    try {
      if (typeof (window as any).trackFunnelEvent === 'function') {
        (window as any).trackFunnelEvent(name, {});
      }
    } catch {}
  };

  return (
    <>
      <style>{`
        .${scrollRootClass} {
          --rp-page: #0b1620;
          --rp-panel: #142430;
          --rp-muted: #0f1c26;
          --rp-border: #24384a;
          --rp-primary: #2a93e0;
          --rp-highlight: #38c6de;
          --rp-text: #eaf2f8;
          --rp-text-muted: #a7c2d3;
          --rp-text-subtle: #7f9bad;
          font-family: "Inter", system-ui, -apple-system, sans-serif;
          color: var(--rp-text);
          background: var(--rp-page);
        }
        .rp-section { padding: 4rem 1.5rem; }
        .rp-container { max-width: 72rem; margin: 0 auto; }
        .rp-btn-primary {
          display: inline-flex; align-items: center; gap: 0.5rem;
          background: var(--rp-primary); color: #111827;
          font-weight: 600; border-radius: 0.75rem;
          padding: 0.875rem 1.5rem; border: none; cursor: pointer;
          transition: transform 0.15s ease, box-shadow 0.15s ease;
          box-shadow: 0 10px 24px rgba(42,147,224,0.28);
        }
        .rp-btn-primary:hover { transform: translateY(-1px); }
        .rp-btn-outline {
          display: inline-flex; align-items: center; gap: 0.5rem;
          background: transparent; color: var(--rp-text);
          font-weight: 600; border-radius: 0.75rem;
          padding: 0.875rem 1.5rem; border: 1px solid var(--rp-border); cursor: pointer;
        }
        .rp-btn-ghost {
          background: transparent; border: none; color: var(--rp-highlight);
          font-weight: 600; cursor: pointer; text-decoration: underline;
          text-underline-offset: 3px;
        }
        .rp-card {
          background: var(--rp-panel); border: 1px solid var(--rp-border);
          border-radius: 1rem; padding: 1.5rem;
        }
        @media (min-width: 768px) {
          .rp-hero-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 3rem; align-items: center; }
          .rp-problem-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; }
          .rp-solution-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 3rem; align-items: center; }
        }
      `}</style>

      <nav
        className="fixed inset-x-0 top-0 z-30 transition-all duration-300"
        style={{
          backgroundColor: scrolled ? 'rgba(20,36,48,0.95)' : 'transparent',
          borderBottom: scrolled ? '1px solid #24384a' : '1px solid transparent',
          backdropFilter: scrolled ? 'blur(12px)' : undefined,
        }}
      >
        <div className="rp-container flex items-center justify-between gap-4 py-4 px-6">
          <a href="#hero" className="flex items-center gap-3 min-w-0">
            <img src={logoUrl} alt={brandName} style={{ height: 32, objectFit: 'contain' }} />
          </a>
          <div className="hidden md:flex items-center gap-6 text-sm font-medium" style={{ color: '#a7c2d3' }}>
            <a href="#problem" className="hover:text-white transition-colors">Problem</a>
            <a href="#solution" className="hover:text-white transition-colors">Solution</a>
            <a href="#trust" className="hover:text-white transition-colors">Why ReloPass</a>
          </div>
          <button
            type="button"
            className="rp-btn-primary text-sm py-2 px-4"
            onClick={() => { trackEvent('landing_cta_click'); onPrimaryCta?.(); }}
          >
            Get started
            <ArrowRight size={16} />
          </button>
        </div>
      </nav>

      <section id="hero" className="rp-section pt-28 pb-16" style={{ background: 'linear-gradient(180deg, #0b1620 0%, #0f1e2a 100%)' }}>
        <div className="rp-container rp-hero-grid">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.25em] mb-4" style={{ color: '#38c6de' }}>
              {c.hero.eyebrow}
            </p>
            <h1 className="text-4xl md:text-5xl font-bold leading-tight mb-4" style={{ color: '#eaf2f8' }}>
              {c.hero.headline}
            </h1>
            <p className="text-lg leading-relaxed mb-4" style={{ color: '#a7c2d3' }}>
              {c.hero.subheadline}
            </p>
            <p className="text-sm mb-6" style={{ color: '#7f9bad' }}>{c.hero.brandPromise}</p>
            <div className="flex flex-col sm:flex-row gap-3 mb-3">
              <button
                type="button"
                className="rp-btn-primary"
                onClick={() => { trackEvent('landing_cta_click'); onPrimaryCta?.(); }}
              >
                {c.hero.primaryCta}
                <ArrowRight size={18} />
              </button>
              <button
                type="button"
                className="rp-btn-outline"
                onClick={() => { trackEvent('landing_cta_click'); onSecondaryCta?.(); }}
              >
                {c.hero.secondaryCta}
              </button>
            </div>
            <p className="text-xs" style={{ color: '#7f9bad' }}>{c.hero.trustMicrocopy}</p>
            {isTestDrivePage && (
              <p className="text-xs text-center mt-4" style={{ color: '#7f9bad' }}>
                This is a research prototype — requirements shown are for validation purposes only, not legal advice.
              </p>
            )}
          </div>
          <div className="hidden md:block">
            <img
              src={assetUrl('screenshot-hero-case-card.png')}
              alt="ReloPass case view showing relocation status, milestones, documents, and provider activity on one record."
              className="w-full rounded-xl"
              style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.35)' }}
            />
          </div>
        </div>
      </section>

      <section className="rp-section py-8" style={{ background: '#0b1620' }}>
        <div className="rp-container grid gap-4 md:grid-cols-3">
          {c.proofBlock.items.map((item) => {
            const Icon = PROOF_ICONS[item.icon as keyof typeof PROOF_ICONS] || FileSearch;
            return (
              <div key={item.article} className="rp-card flex gap-3">
                <Icon size={20} style={{ color: '#38c6de', flexShrink: 0, marginTop: 2 }} />
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-wide mb-1" style={{ color: '#38c6de' }}>{item.article}</p>
                  <p className="text-sm leading-relaxed" style={{ color: '#a7c2d3' }}>{item.text}</p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section id="problem" className="rp-section" style={{ background: '#0f1c26' }}>
        <div className="rp-container">
          <h2 className="text-3xl font-bold text-center mb-12" style={{ color: '#eaf2f8' }}>{c.problem.title}</h2>
          <div className="rp-problem-grid">
            {c.problem.cards.map((card) => (
              <div key={card.title} className="rp-card">
                <h3 className="font-semibold mb-2 text-lg" style={{ color: '#eaf2f8' }}>{card.title}</h3>
                <p className="text-sm leading-relaxed" style={{ color: '#a7c2d3' }}>{card.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="solution" className="rp-section" style={{ background: '#0b1620' }}>
        <div className="rp-container">
          <p className="text-center text-sm font-semibold uppercase tracking-wider mb-2" style={{ color: '#38c6de' }}>{c.solution.sectionHeader}</p>
          <h2 className="text-3xl font-bold text-center mb-12" style={{ color: '#eaf2f8' }}>{c.solution.title}</h2>
          <div className="rp-solution-grid">
            <img
              src={assetUrl('screenshot-hr-assignments.png')}
              alt="ReloPass — every relocation case, its tasks, providers and status on one record"
              className="w-full rounded-xl border"
              style={{ borderColor: '#24384a' }}
            />
            <ul className="space-y-6">
              {c.solution.blocks.map((block) => (
                <li key={block.title} className="flex gap-3">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: '#38c6de' }} />
                  <div>
                    <h3 className="font-semibold mb-1" style={{ color: '#eaf2f8' }}>{block.title}</h3>
                    <p className="text-sm leading-relaxed" style={{ color: '#a7c2d3' }}>{block.body}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section id="trust" className="rp-section" style={{ background: '#0f1c26' }}>
        <div className="rp-container max-w-4xl">
          {c.trust.categoryBoundary && (
            <div className="text-center mb-10">
              <p className="text-lg font-bold mb-1" style={{ color: '#eaf2f8' }}>{c.trust.categoryBoundary.positive}</p>
              {c.trust.categoryBoundary.negatives.map((line) => (
                <p key={line} className="text-sm font-medium" style={{ color: '#7f9bad' }}>{line}</p>
              ))}
            </div>
          )}
          <h2 className="text-2xl font-bold mb-3 text-center" style={{ color: '#eaf2f8' }}>{c.trust.title}</h2>
          <p className="text-center mb-8" style={{ color: '#a7c2d3' }}>{c.trust.body}</p>
          <ul className="grid gap-3 sm:grid-cols-2">
            {c.trust.checklist.map((item) => (
              <li key={item} className="flex items-start gap-2 text-sm" style={{ color: '#a7c2d3' }}>
                <Check size={16} style={{ color: '#38c6de', flexShrink: 0, marginTop: 2 }} />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="rp-section" style={{ background: '#0b1620' }}>
        <div className="rp-container max-w-3xl text-center rp-card">
          <h2 className="text-3xl font-bold mb-3" style={{ color: '#eaf2f8' }}>{c.finalCta.headline}</h2>
          <p className="mb-8" style={{ color: '#a7c2d3' }}>{c.finalCta.microCopy}</p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <button type="button" className="rp-btn-primary" onClick={() => { trackEvent('landing_cta_click'); onSecondaryCta?.(); }}>
              {c.finalCta.options.demo}
            </button>
            <button type="button" className="rp-btn-outline" onClick={() => onPlatformTour?.()}>
              {c.finalCta.options.platform}
            </button>
            <button type="button" className="rp-btn-ghost" onClick={() => onSignIn?.()}>
              {c.finalCta.options.signIn}
            </button>
          </div>
        </div>
      </section>

      <footer className="rp-section py-10 border-t" style={{ borderColor: '#24384a', background: '#0f1c26' }}>
        <div className="rp-container flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <img src={assetUrl('relopass-logo.png')} alt={brandName} style={{ height: 24 }} />
            <span className="font-semibold" style={{ color: '#eaf2f8' }}>{brandName}</span>
          </div>
          <p className="text-xs" style={{ color: '#7f9bad' }}>
            © {new Date().getFullYear()} {brandName}. Global mobility infrastructure.
          </p>
        </div>
      </footer>
    </>
  );
}
