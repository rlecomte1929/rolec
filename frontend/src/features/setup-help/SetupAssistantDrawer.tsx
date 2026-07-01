/**
 * Fixed-overlay drawer for the Setup & Help Assistant.
 *
 * Replaces the PolicyAssistantDockedShell usage in AppShell: that shell's
 * docked-column behavior requires a flex sibling to push against. AppShell's
 * main content lives in an unrelated subtree, so the column had no sibling
 * and rendered below the footer in the document flow.
 *
 * This drawer is always `position:fixed` — right-side panel on desktop,
 * bottom-sheet on mobile — so it renders above content on all breakpoints.
 */
import React, { useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import { Button } from '../../components/antigravity/Button';
import { SetupAssistantPanel } from './SetupAssistantPanel';

export type SetupAssistantDrawerProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

const TITLE_ID = 'setup-assistant-drawer-title';

export const SetupAssistantDrawer: React.FC<SetupAssistantDrawerProps> = ({
  open,
  onOpenChange,
}) => {
  const close = React.useCallback(() => onOpenChange(false), [onOpenChange]);
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);
  const prevFocusRef = useRef<HTMLElement | null>(null);

  // Save/restore focus on open/close.
  useEffect(() => {
    if (open) {
      const active = document.activeElement;
      if (active instanceof HTMLElement) prevFocusRef.current = active;
      const id = window.setTimeout(() => closeBtnRef.current?.focus(), 50);
      return () => window.clearTimeout(id);
    }
    const prev = prevFocusRef.current;
    if (prev && document.contains(prev)) prev.focus();
    prevFocusRef.current = null;
    return undefined;
  }, [open]);

  // Lock body scroll on mobile only (panel is non-overlapping on desktop).
  useEffect(() => {
    if (!open) return undefined;
    if (typeof window === 'undefined') return undefined;
    const isLg =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(min-width: 1024px)').matches;
    if (isLg) return undefined;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  if (!open) return null;

  return (
    <>
      {/* Mobile-only backdrop — not shown on desktop where the panel is a
          non-modal sidebar overlay. */}
      <Button
        unstyled
        type="button"
        className="fixed inset-0 z-40 bg-slate-900/35 backdrop-blur-[1px] lg:hidden"
        aria-label="Close panel"
        onClick={close}
      />

      {/* Panel — bottom-sheet on mobile, right fixed column on desktop. */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={TITLE_ID}
        data-testid="setup-assistant-drawer"
        className={[
          // Base — fixed, above everything, flex column
          'fixed z-50 flex flex-col bg-white',
          // Mobile: full-width bottom sheet anchored to bottom
          'left-0 right-0 bottom-0 max-h-[90dvh] rounded-t-2xl',
          'shadow-[0_-4px_30px_rgba(15,23,42,0.12)]',
          // Desktop lg+: right column, full viewport height, no rounded top
          'lg:left-auto lg:top-0 lg:w-[420px] lg:max-h-none',
          'lg:rounded-none lg:border-l lg:border-slate-200',
          'lg:shadow-[-4px_0_20px_rgba(15,23,42,0.08)]',
        ].join(' ')}
      >
        {/* Sticky header */}
        <div className="sticky top-0 z-10 flex shrink-0 items-start justify-between gap-3 border-b border-slate-200 px-4 py-3 bg-white">
          <div className="min-w-0 flex-1">
            <div
              id={TITLE_ID}
              className="text-base font-semibold tracking-tight text-[#0b2b43]"
            >
              Setup &amp; Help
            </div>
            <div className="text-xs text-slate-500 mt-1 leading-snug">
              Guided help for your ReloPass workspace
            </div>
          </div>
          <Button
            unstyled
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
          <SetupAssistantPanel variant="embedded" />
        </div>
      </div>
    </>
  );
};
