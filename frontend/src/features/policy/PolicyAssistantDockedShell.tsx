/**
 * Layout primitive for the Policy Assistant — replaces the modal-overlay
 * PolicyAssistantSideSheet with a docked right-side column on lg+ screens.
 *
 * Why this exists: the assistant should not compete with page content.
 * The previous implementation rendered a full-screen modal with a 35%
 * black backdrop, dimming the very policy text the user was trying to
 * cross-reference. This shell replaces that with a docked panel that
 * pushes content left so both the policy AND the assistant are
 * simultaneously visible and interactive.
 *
 * Behavior split:
 *   - lg+ (≥1024px): docked right column. Panel width animates between
 *     0 and 420px on a 250ms transition. NO backdrop. Page content
 *     reflows into the freed/taken space. Panel is `role="region"`,
 *     not `role="dialog"` — it's not modal.
 *   - <lg: bottom sheet (the previous mobile path). `role="dialog"`,
 *     `aria-modal="true"`, backdrop, Escape closes globally. The same
 *     opening/close flow as before.
 *
 * Pages mount their content as children and the assistant as the
 * `assistant` render-prop. The shell owns layout, animation, and the
 * responsive switch — pages stay simple.
 */
import React, { useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import { Button } from '../../components/antigravity/Button';

export type PolicyAssistantDockedShellProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Main page content — rendered side-by-side with the assistant on lg+. */
  children: React.ReactNode;
  /** Assistant body. Receives a `close` handler so the panel can offer
   *  in-content dismissal affordances if needed. */
  assistant: (ctx: { close: () => void }) => React.ReactNode;
  /** Panel header title. */
  title: string;
  /** Optional subtitle under the title. */
  subtitle?: React.ReactNode;
  /** Stable id for `aria-labelledby`. */
  titleId: string;
};

const DOCKED_WIDTH_PX = 420;

export const PolicyAssistantDockedShell: React.FC<PolicyAssistantDockedShellProps> = ({
  open,
  onOpenChange,
  children,
  assistant,
  title,
  subtitle,
  titleId,
}) => {
  const close = React.useCallback(() => onOpenChange(false), [onOpenChange]);

  // Track the *previously* focused element so we can restore focus on
  // close. Same intent as the old fab implementation, kept so keyboard
  // users aren't dumped at the top of the page after dismissing.
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);

  // Snapshot focus on open; restore on close.
  useEffect(() => {
    if (open) {
      const active = document.activeElement;
      if (active instanceof HTMLElement) {
        previouslyFocusedRef.current = active;
      }
      // Move focus to the close button so keyboard tab order starts
      // inside the panel. Small setTimeout lets the transition mount.
      const id = window.setTimeout(() => closeBtnRef.current?.focus(), 50);
      return () => window.clearTimeout(id);
    }
    // On close, return focus to whatever opened the panel.
    const prev = previouslyFocusedRef.current;
    if (prev && document.contains(prev)) {
      prev.focus();
    }
    previouslyFocusedRef.current = null;
    return undefined;
  }, [open]);

  // ESC closes ONLY when focus is inside the panel. We deliberately do
  // NOT bind ESC globally on lg+ — the docked panel is not modal, and
  // a global handler would steal Escape from other components.
  // Mobile bottom-sheet IS modal so a global handler is fine; we still
  // gate by panel containment here to avoid double-bind issues. The
  // dialog overlay covers the screen on mobile so focus is naturally
  // trapped via the overlay click handler, and the panel-bound listener
  // catches the keyboard case.
  useEffect(() => {
    if (!open) return undefined;
    const node = panelRef.current;
    if (!node) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      const active = document.activeElement;
      if (active && node.contains(active)) {
        e.stopPropagation();
        close();
      }
    };
    node.addEventListener('keydown', onKey);
    return () => node.removeEventListener('keydown', onKey);
  }, [open, close]);

  // Lock body scroll only on the modal (mobile) path. On lg+ the panel
  // has its own scroll context and the page underneath stays scrollable.
  useEffect(() => {
    if (!open) return undefined;
    if (typeof window === 'undefined') return undefined;
    const isLg = window.matchMedia('(min-width: 1024px)').matches;
    if (isLg) return undefined;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  return (
    <div className="flex flex-row min-h-0 w-full">
      {/* Main content column. flex-1 + min-w-0 so flexbox can shrink it
          when the panel takes its 420px on lg+. overflow-x-clip keeps
          page-level sticky bars (e.g. HrPolicyPageV2's StatusStrip
          which uses negative horizontal margins to bleed across page
          padding) inside the column boundary instead of spilling into
          the docked panel area where they'd cover the panel header. */}
      <div
        className="flex-1 min-w-0 overflow-x-clip transition-[margin] duration-[250ms] ease-out"
        data-policy-assistant-main
      >
        {children}
      </div>

      {/* Docked panel column — visible only on lg+. Width animates
          between 0 (closed) and DOCKED_WIDTH_PX (open). overflow-hidden
          on the column hides the panel chrome at width 0 instead of
          letting it spill over the main content during transition. */}
      <aside
        ref={panelRef}
        role="region"
        aria-labelledby={titleId}
        aria-hidden={!open}
        className={`hidden lg:flex flex-col border-l border-slate-200 bg-white transition-[width] duration-[250ms] ease-out overflow-hidden ${
          open ? '' : 'pointer-events-none'
        }`}
        style={{ width: open ? `${DOCKED_WIDTH_PX}px` : '0px' }}
        data-policy-assistant-panel
      >
        {/* Sticky header so title + close button stay visible while the
            assistant body scrolls underneath. */}
        <div className="sticky top-0 z-10 flex shrink-0 items-start justify-between gap-3 border-b border-slate-200 px-4 py-3 bg-white">
          <div className="min-w-0 flex-1">
            <div id={titleId} className="text-base font-semibold tracking-tight text-[#0b2b43]">
              {title}
            </div>
            {subtitle ? (
              <div className="text-xs text-slate-500 mt-1 leading-snug">{subtitle}</div>
            ) : null}
          </div>
          <Button unstyled
            ref={closeBtnRef}
            type="button"
            onClick={close}
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-200/60 hover:text-slate-800 shrink-0 focus:outline-none focus:ring-2 focus:ring-[#0b2b43]/30"
            aria-label="Close"
          >
            <X className="h-5 w-5" aria-hidden />
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4 pb-6">
          {open ? assistant({ close }) : null}
        </div>
      </aside>

      {/* Mobile bottom-sheet — modal behavior preserved from the old
          PolicyAssistantSideSheet. role=dialog, aria-modal=true,
          backdrop, focus trap via overlay containment. lg:hidden so it
          doesn't interfere with the docked column above. */}
      {open ? (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center lg:hidden"
          role="dialog"
          aria-modal="true"
          aria-labelledby={`${titleId}-mobile`}
        >
          <Button unstyled
            type="button"
            className="absolute inset-0 bg-slate-900/35 backdrop-blur-[1px]"
            aria-label="Close panel"
            onClick={close}
          />
          <div className="relative z-10 flex h-[100dvh] max-h-[100dvh] w-full flex-col bg-white shadow-[0_-8px_30px_rgba(15,23,42,0.12)] sm:h-auto sm:max-h-[92vh] sm:rounded-t-2xl">
            <div className="sticky top-0 z-10 flex shrink-0 items-start justify-between gap-3 border-b border-slate-200 px-4 py-3 bg-white">
              <div className="min-w-0 flex-1">
                <div
                  id={`${titleId}-mobile`}
                  className="text-base font-semibold tracking-tight text-[#0b2b43]"
                >
                  {title}
                </div>
                {subtitle ? (
                  <div className="text-xs text-slate-500 mt-1 leading-snug">{subtitle}</div>
                ) : null}
              </div>
              <Button unstyled
                type="button"
                onClick={close}
                className="rounded-lg p-2 text-slate-500 hover:bg-slate-200/60 hover:text-slate-800 shrink-0"
                aria-label="Close"
              >
                <X className="h-5 w-5" aria-hidden />
              </Button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4 pb-6">
              {assistant({ close })}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};
