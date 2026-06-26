import React, { useCallback, useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';

/**
 * A11Y-5: accessible Modal/Dialog primitive.
 *
 * Replaces the hand-rolled `fixed inset-0` overlays that lacked semantics +
 * keyboard support. Provides:
 *  - role="dialog" + aria-modal="true" + aria-labelledby (the title)
 *  - focus moved into the dialog on open, trapped within (Tab / Shift+Tab cycle)
 *  - Escape to close
 *  - focus restored to the triggering element on close
 *  - backdrop click to close (parity with the old modals)
 *
 * Rendered through a portal on document.body so it isn't clipped by an
 * overflow/transform ancestor.
 */

const FOCUSABLE =
  'a[href],area[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

export interface ModalProps {
  /** Whether the dialog is shown. When false nothing is rendered. */
  open: boolean;
  /** Called on Escape, backdrop click, or the close affordance. */
  onClose: () => void;
  /** Accessible name — rendered as the dialog heading and wired via aria-labelledby. */
  title: string;
  children: React.ReactNode;
  /** Extra classes for the dialog panel. */
  className?: string;
  /** Hide the visible heading but keep it for screen readers (still aria-labelledby). */
  hideTitle?: boolean;
}

export const Modal: React.FC<ModalProps> = ({
  open,
  onClose,
  title,
  children,
  className = '',
  hideTitle = false,
}) => {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  // Remember what had focus so we can restore it when the dialog closes.
  const triggerRef = useRef<Element | null>(null);

  // Capture the trigger + move focus into the dialog on open; restore on close.
  useEffect(() => {
    if (!open) return;
    triggerRef.current = document.activeElement;
    const panel = panelRef.current;
    const first = panel?.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? panel)?.focus();
    return () => {
      const trigger = triggerRef.current;
      if (trigger instanceof HTMLElement) trigger.focus();
    };
  }, [open]);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      const panel = panelRef.current;
      if (!panel) return;
      const focusables = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (el) => el.offsetParent !== null || el === document.activeElement,
      );
      if (focusables.length === 0) {
        // Nothing focusable — keep focus on the panel itself.
        e.preventDefault();
        panel.focus();
        return;
      }
      const firstEl = focusables[0];
      const lastEl = focusables[focusables.length - 1];
      if (!firstEl || !lastEl) return;
      const active = document.activeElement;
      if (e.shiftKey && (active === firstEl || active === panel)) {
        e.preventDefault();
        lastEl.focus();
      } else if (!e.shiftKey && active === lastEl) {
        e.preventDefault();
        firstEl.focus();
      }
    },
    [onClose],
  );

  if (!open) return null;

  return createPortal(
    // eslint-disable-next-line local/no-clickable-div -- presentational backdrop; click-to-dismiss is a convenience and keyboard users close via Escape (handled on the dialog). Not an interactive control.
    <div
      role="presentation"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
      // Close only when the backdrop itself is clicked, not a child — so the panel
      // needs no stopPropagation. Keyboard users dismiss via Escape (on the dialog).
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions -- role=dialog owns its keyboard handling (Escape + Tab focus-trap); this is the canonical accessible-dialog pattern, not a clickable element. */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={onKeyDown}
        className={`bg-white rounded-lg shadow-lg outline-none ${className}`}
      >
        <h2 id={titleId} className={hideTitle ? 'sr-only' : 'text-base font-semibold text-slate-900 mb-2'}>
          {title}
        </h2>
        {children}
      </div>
    </div>,
    document.body,
  );
};
