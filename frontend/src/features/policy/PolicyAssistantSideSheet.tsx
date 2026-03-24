import React, { useEffect } from 'react';
import { X } from 'lucide-react';

export type PolicyAssistantSideSheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  subtitle: React.ReactNode;
  titleId: string;
  /** Trigger row (e.g. top-right button); keep non-overlapping with body text. */
  trigger: React.ReactNode;
  children: React.ReactNode;
};

/**
 * Right-fixed overlay panel (desktop), bottom sheet on small screens.
 * Backdrop click, Escape, and header close button all close the panel.
 */
export function PolicyAssistantSideSheet({
  open,
  onOpenChange,
  title,
  subtitle,
  titleId,
  trigger,
  children,
}: PolicyAssistantSideSheetProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onOpenChange(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onOpenChange]);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  return (
    <>
      {trigger}
      {open ? (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center lg:items-stretch lg:justify-end"
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
        >
          <button
            type="button"
            className="absolute inset-0 bg-slate-900/35 backdrop-blur-[1px]"
            aria-label="Close panel"
            onClick={() => onOpenChange(false)}
          />
          <div
            className="relative z-10 flex h-[100dvh] max-h-[100dvh] w-full flex-col rounded-none border-0 border-slate-200 bg-white shadow-[0_-8px_30px_rgba(15,23,42,0.12)] sm:h-auto sm:max-h-[92vh] sm:rounded-t-2xl sm:border sm:border-b-0 lg:h-full lg:max-h-none lg:w-[min(440px,96vw)] lg:max-w-[min(440px,96vw)] lg:rounded-none lg:rounded-l-xl lg:border lg:border-b lg:border-r-0 lg:shadow-xl"
          >
            <div className="flex shrink-0 items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 bg-white">
              <div className="min-w-0">
                <div id={titleId} className="text-base font-semibold tracking-tight text-[#0b2b43]">
                  {title}
                </div>
                <div className="text-xs text-slate-500 mt-1 leading-snug">{subtitle}</div>
              </div>
              <button
                type="button"
                onClick={() => onOpenChange(false)}
                className="rounded-lg p-2 text-slate-500 hover:bg-slate-200/60 hover:text-slate-800 shrink-0"
                aria-label="Close"
              >
                <X className="h-5 w-5" aria-hidden />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4 pb-6">{children}</div>
          </div>
        </div>
      ) : null}
    </>
  );
}
