import { useEffect, useRef, useState } from 'react';

interface RowActionMenuProps {
  onEdit: () => void;
  onArchive: () => void;
  onDelete: () => void;
  /** When true, hide the Archive action (e.g. company is already archived). */
  disableArchive?: boolean;
  /** Label for accessibility — defaults to "Open actions menu". */
  ariaLabel?: string;
}

/**
 * Tiny row-level dropdown menu triggered by a ⋯ button.
 *
 * Lives entirely client-side; closes on outside click or Escape.
 * Stops click propagation so the row's onClick (which opens the
 * detail panel) doesn't also fire when the user interacts with the menu.
 */
export function RowActionMenu({
  onEdit,
  onArchive,
  onDelete,
  disableArchive = false,
  ariaLabel = 'Open actions menu',
}: RowActionMenuProps) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onWindowClick(e: MouseEvent) {
      if (!wrapperRef.current) return;
      if (!wrapperRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    window.addEventListener('click', onWindowClick);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('click', onWindowClick);
      window.removeEventListener('keydown', onKey);
    };
  }, [open]);

  function pick(handler: () => void) {
    return (e: React.MouseEvent) => {
      e.stopPropagation();
      setOpen(false);
      handler();
    };
  }

  return (
    <div
      ref={wrapperRef}
      className="relative inline-block"
      onClick={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        aria-label={ariaLabel}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
      >
        ⋯
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 w-44 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg ring-1 ring-black/5"
        >
          <button
            type="button"
            role="menuitem"
            onClick={pick(onEdit)}
            className="block w-full px-3 py-2 text-left text-[13px] text-slate-700 hover:bg-slate-50"
          >
            Edit
          </button>
          {!disableArchive && (
            <button
              type="button"
              role="menuitem"
              onClick={pick(onArchive)}
              className="block w-full px-3 py-2 text-left text-[13px] text-slate-700 hover:bg-slate-50"
            >
              Archive
            </button>
          )}
          <div className="h-px bg-slate-100" />
          <button
            type="button"
            role="menuitem"
            onClick={pick(onDelete)}
            className="block w-full px-3 py-2 text-left text-[13px] text-rose-700 hover:bg-rose-50"
          >
            Delete…
          </button>
        </div>
      )}
    </div>
  );
}
