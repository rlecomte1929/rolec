/**
 * Shared floating "Policy Assistant" FAB used on every policy surface.
 *
 * Product direction (2026-04-22): the assistant should not compete with
 * page content. It lives as a fixed 💬 button bottom-right, visible on
 * every HR and employee policy page. When opened it slides in as a
 * right-anchored sheet (desktop) or a full-width sheet (mobile).
 *
 * This component is a pure shell — it does not know which role is using
 * it. Callers pass the assistant panel (HR or Employee) as children in
 * its `card` variant so we don't get the double-chrome that the panel's
 * own `sideSheet` mode ships with. The FAB owns:
 *
 *   - the fixed button + its accessible label
 *   - the overlay + right-anchored sheet
 *   - open/close state + Escape-to-close
 *   - focus trap on the close button when opening so keyboard users get
 *     predictable tab order
 *   - outside-click dismissal
 *
 * Non-goals for this component: conversation history, answer rendering,
 * question suggestions — those live in the assistant panels themselves.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';

type Props = {
  /**
   * Accessible label announced by screen readers when the FAB is focused.
   * Defaults to "Open Policy Assistant"; overridable if the surrounding
   * page prefers more specific wording ("Ask about your HR policy").
   */
  label?: string;
  /**
   * Sheet title rendered in the header when open. Defaults to "Policy
   * Assistant". Kept short so mobile sheet headers don't wrap.
   */
  sheetTitle?: string;
  /**
   * Render-prop for the sheet body. Called with the onClose handler so
   * the child can offer its own dismissal affordances (e.g. "Close"
   * buttons inside a long thread) without duplicating the state owner.
   */
  children: (ctx: { close: () => void }) => React.ReactNode;
  /**
   * Optional hook that fires when the sheet opens — useful for
   * analytics ("policy_assistant_opened") without pulling a provider
   * into the component.
   */
  onOpen?: () => void;
};

export const PolicyAssistantFab: React.FC<Props> = ({
  label = 'Open Policy Assistant',
  sheetTitle = 'Policy Assistant',
  children,
  onOpen,
}) => {
  const [open, setOpen] = useState(false);
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);
  const fabRef = useRef<HTMLButtonElement | null>(null);

  const openSheet = useCallback(() => {
    setOpen(true);
    onOpen?.();
  }, [onOpen]);

  const close = useCallback(() => {
    setOpen(false);
    // Restore focus to the FAB so keyboard users aren't dumped at the
    // top of the page after dismissal.
    fabRef.current?.focus();
  }, []);

  // Escape closes the sheet. Bound only while open to avoid leaking a
  // listener across every page that mounts the FAB.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, close]);

  // When the sheet opens, move focus to the close button so tab order
  // starts inside the sheet. Small setTimeout lets the sheet mount.
  useEffect(() => {
    if (!open) return;
    const id = window.setTimeout(() => closeBtnRef.current?.focus(), 50);
    return () => window.clearTimeout(id);
  }, [open]);

  return (
    <>
      <button
        ref={fabRef}
        type="button"
        onClick={openSheet}
        aria-label={label}
        aria-haspopup="dialog"
        aria-expanded={open}
        title={label}
        className="fixed bottom-6 right-6 z-40 h-14 w-14 rounded-full bg-[#0b2b43] text-white shadow-lg hover:bg-[#0f3a5a] focus:outline-none focus:ring-4 focus:ring-[#0b2b43]/30 flex items-center justify-center text-2xl"
        data-testid="policy-assistant-fab"
      >
        <span aria-hidden>💬</span>
      </button>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={sheetTitle}
          className="fixed inset-0 z-50 bg-black/30 flex justify-end"
          onClick={close}
        >
          <div
            className="h-full w-full max-w-md bg-white shadow-2xl overflow-y-auto flex flex-col"
            onClick={(e) => e.stopPropagation()}
            data-testid="policy-assistant-fab-sheet"
          >
            <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between sticky top-0 bg-white z-10">
              <div className="font-semibold text-[#0b2b43]">{sheetTitle}</div>
              <button
                ref={closeBtnRef}
                type="button"
                onClick={close}
                className="text-slate-500 hover:text-[#0b2b43] px-2 py-1 rounded focus:outline-none focus:ring-2 focus:ring-[#0b2b43]/30"
                aria-label="Close Policy Assistant"
              >
                Close
              </button>
            </div>
            <div className="p-4 flex-1">
              {children({ close })}
            </div>
          </div>
        </div>
      )}
    </>
  );
};
