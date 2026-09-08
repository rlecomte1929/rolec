import { ReactNode, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '../lib/utils';

interface SheetProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  /** Width class. Defaults to a 2-column-friendly width (3/5 of viewport). */
  widthClassName?: string;
  /**
   * Optional description rendered under the title in muted text. Useful
   * for context (e.g. "Document type: Passport").
   */
  description?: string;
}

/**
 * Right-side Sheet primitive. Plain React + Tailwind — keeps the app
 * scaffold free of the shadcn-dialog Radix dependency that the brief's
 * "shadcn Sheet" reference implies. The behaviour matches the same
 * defaults: portal to body, overlay click closes, Esc closes, focus
 * trapped inside while open, scroll lock on body, ARIA-correct.
 *
 * If we ever do adopt @radix-ui/react-dialog, we can swap the internals
 * without changing this component's props.
 */
export function Sheet({
  open,
  onClose,
  title,
  description,
  children,
  widthClassName,
}: SheetProps): JSX.Element | null {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const lastFocusedRef = useRef<HTMLElement | null>(null);

  // Lock body scroll + remember the previously focused element so we
  // can restore it on close.
  useEffect(() => {
    if (!open) return undefined;
    lastFocusedRef.current = (document.activeElement as HTMLElement | null) ?? null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
      lastFocusedRef.current?.focus?.();
    };
  }, [open]);

  // Esc closes; basic focus trap on Tab.
  useEffect(() => {
    if (!open) return undefined;
    const handler = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      const container = containerRef.current;
      if (!container) return;
      const focusables = container.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (!first || !last) return;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', handler, true);
    return () => window.removeEventListener('keydown', handler, true);
  }, [open, onClose]);

  // Initial focus when the sheet opens.
  useEffect(() => {
    if (!open) return;
    requestAnimationFrame(() => {
      const container = containerRef.current;
      const first = container?.querySelector<HTMLElement>('[data-sheet-initial-focus]')
        ?? container?.querySelector<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        );
      first?.focus();
    });
  }, [open]);

  if (!open) return null;
  if (typeof document === 'undefined') return null;

  return createPortal(
    <div
      className="fixed inset-0 z-dialog flex justify-end"
      role="dialog"
      aria-modal="true"
      aria-labelledby="sheet-title"
      aria-describedby={description ? 'sheet-description' : undefined}
    >
      <button
        type="button"
        aria-label="Close panel"
        onClick={onClose}
        className="absolute inset-0 bg-foreground/40 backdrop-blur-sm"
      />
      <div
        ref={containerRef}
        className={cn(
          'relative flex h-full max-w-full flex-col bg-card shadow-xl',
          widthClassName ?? 'w-full md:w-[60vw] lg:w-[55vw] xl:w-[50vw]',
        )}
      >
        <header className="flex items-start justify-between gap-4 border-b border-border px-6 py-4">
          <div className="flex flex-col gap-1">
            <h2 id="sheet-title" className="text-lg font-semibold text-foreground">
              {title}
            </h2>
            {description ? (
              <p id="sheet-description" className="text-sm text-muted-foreground">
                {description}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            aria-label="Close panel"
            onClick={onClose}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-border bg-card text-foreground hover:bg-muted focus-visible:shadow-focus"
            data-sheet-initial-focus
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-6 py-4">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
