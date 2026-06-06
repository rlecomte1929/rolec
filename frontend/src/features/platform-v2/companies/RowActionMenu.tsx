import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Button } from '../../../components/antigravity/Button';
import { createPortal } from 'react-dom';

interface RowActionMenuProps {
  onEdit: () => void;
  onArchive: () => void;
  onDelete: () => void;
  /** When true, hide the Archive action (e.g. company is already archived). */
  disableArchive?: boolean;
  /** Label for accessibility — defaults to "Open actions menu". */
  ariaLabel?: string;
}

const PANEL_WIDTH = 176; // tailwind w-44 (11rem * 16)
const PANEL_GAP = 4;
const PANEL_ESTIMATED_HEIGHT = 130; // edit + archive + divider + delete ≈ 130px
const VIEWPORT_PAD = 8;

/**
 * Row-level dropdown menu triggered by a ⋯ button.
 *
 * The menu panel is rendered via `createPortal` to `document.body` so it
 * escapes any parent `overflow-*` boundaries (the table card uses
 * overflow-x-auto for horizontal scrolling, which used to clip this).
 *
 * Position is computed at open-time from the trigger button's bounding rect,
 * with a vertical flip if there isn't enough room below.
 */
export function RowActionMenu({
  onEdit,
  onArchive,
  onDelete,
  disableArchive = false,
  ariaLabel = 'Open actions menu',
}: RowActionMenuProps) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [panelStyle, setPanelStyle] = useState<{ top: number; left: number } | null>(null);

  // Compute position before paint so the panel never flashes in the wrong spot.
  useLayoutEffect(() => {
    if (!open || !triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();

    // Default: align right edge of panel to right edge of trigger, drop down.
    let left = rect.right - PANEL_WIDTH;
    let top = rect.bottom + PANEL_GAP;

    // Clamp horizontal position into the viewport.
    if (left < VIEWPORT_PAD) left = VIEWPORT_PAD;
    if (left + PANEL_WIDTH > window.innerWidth - VIEWPORT_PAD) {
      left = window.innerWidth - PANEL_WIDTH - VIEWPORT_PAD;
    }

    // Flip upward if there isn't enough room below the trigger.
    const spaceBelow = window.innerHeight - rect.bottom;
    if (spaceBelow < PANEL_ESTIMATED_HEIGHT + VIEWPORT_PAD) {
      top = rect.top - PANEL_GAP - PANEL_ESTIMATED_HEIGHT;
      if (top < VIEWPORT_PAD) top = VIEWPORT_PAD;
    }

    setPanelStyle({ top, left });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onWindowClick(e: MouseEvent) {
      const target = e.target as Node;
      if (panelRef.current?.contains(target)) return;
      if (triggerRef.current?.contains(target)) return;
      setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    // Close on any scroll (including inside the table) so the panel doesn't
    // detach from its trigger.
    function onScroll() {
      setOpen(false);
    }
    window.addEventListener('click', onWindowClick);
    window.addEventListener('keydown', onKey);
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', onScroll);
    return () => {
      window.removeEventListener('click', onWindowClick);
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', onScroll);
    };
  }, [open]);

  function pick(handler: () => void) {
    return (e: React.MouseEvent) => {
      e.stopPropagation();
      setOpen(false);
      handler();
    };
  }

  const portalRoot = typeof document !== 'undefined' ? document.body : null;

  return (
    <>
      <Button unstyled
        ref={triggerRef}
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
      </Button>

      {open && panelStyle && portalRoot && createPortal(
        <div
          ref={panelRef}
          role="menu"
          style={{
            position: 'fixed',
            top: panelStyle.top,
            left: panelStyle.left,
            width: PANEL_WIDTH,
            zIndex: 60,
          }}
          className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg ring-1 ring-black/5"
          onClick={(e) => e.stopPropagation()}
        >
          <Button unstyled
            type="button"
            role="menuitem"
            onClick={pick(onEdit)}
            className="block w-full px-3 py-2 text-left text-[13px] text-slate-700 hover:bg-slate-50"
          >
            Edit
          </Button>
          {!disableArchive && (
            <Button unstyled
              type="button"
              role="menuitem"
              onClick={pick(onArchive)}
              className="block w-full px-3 py-2 text-left text-[13px] text-slate-700 hover:bg-slate-50"
            >
              Archive
            </Button>
          )}
          <div className="h-px bg-slate-100" />
          <Button unstyled
            type="button"
            role="menuitem"
            onClick={pick(onDelete)}
            className="block w-full px-3 py-2 text-left text-[13px] text-rose-700 hover:bg-rose-50"
          >
            Delete…
          </Button>
        </div>,
        portalRoot,
      )}
    </>
  );
}
