/**
 * ScreenshotCapture — [AIQ-1480] capture the page as an image for the feedback widget.
 *
 * Two modes:
 *  - Full page: html2canvas over document.body.
 *  - Select region: a drag-to-select overlay, then html2canvas cropped to that rect.
 *
 * html2canvas is already a dependency and is lazy-imported (no new npm package). The
 * overlay and the feedback widget carry `data-html2canvas-ignore` so they never appear
 * in the capture. The overlay sits just below the widget (z-index 9998 < 9999) and only
 * intercepts pointer events while a region is being selected, so page scroll/stacking is
 * unaffected the rest of the time. On capture it emits a PNG data URL via `onCapture`.
 */
import { useCallback, useRef, useState } from 'react';

interface Props {
  onCapture: (dataUrl: string) => void;
  onCancel: () => void;
}

type Rect = { x: number; y: number; w: number; h: number };

export function ScreenshotCapture({ onCapture, onCancel }: Props) {
  const [selecting, setSelecting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [rect, setRect] = useState<Rect | null>(null);
  const start = useRef<{ x: number; y: number } | null>(null);

  const runCapture = useCallback(async (crop?: Rect) => {
    setBusy(true);
    try {
      const { default: html2canvas } = await import('html2canvas');
      const opts: Record<string, unknown> = {
        useCORS: true,
        logging: false,
        backgroundColor: '#ffffff',
        ignoreElements: (el: Element) => el.hasAttribute('data-html2canvas-ignore'),
      };
      if (crop) {
        opts.x = crop.x + window.scrollX;
        opts.y = crop.y + window.scrollY;
        opts.width = crop.w;
        opts.height = crop.h;
      }
      const canvas = await html2canvas(document.body, opts);
      onCapture(canvas.toDataURL('image/png'));
    } catch {
      onCancel(); // capture failed — bail cleanly, user can still submit without a shot
    } finally {
      setBusy(false);
      setSelecting(false);
      setRect(null);
    }
  }, [onCapture, onCancel]);

  // ── region-select drag handlers ──
  const onDown = (e: React.PointerEvent) => {
    start.current = { x: e.clientX, y: e.clientY };
    setRect({ x: e.clientX, y: e.clientY, w: 0, h: 0 });
  };
  const onMove = (e: React.PointerEvent) => {
    if (!start.current) return;
    const s = start.current;
    setRect({
      x: Math.min(s.x, e.clientX), y: Math.min(s.y, e.clientY),
      w: Math.abs(e.clientX - s.x), h: Math.abs(e.clientY - s.y),
    });
  };
  const onUp = () => {
    const r = rect;
    start.current = null;
    if (r && r.w > 4 && r.h > 4) void runCapture(r);
    else { setSelecting(false); setRect(null); }
  };

  if (selecting) {
    return (
      <div
        data-html2canvas-ignore
        data-testid="region-overlay"
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        className="fixed inset-0 z-[9998] cursor-crosshair bg-black/20 touch-none"
      >
        <div className="fixed top-3 left-1/2 -translate-x-1/2 bg-[#0b2b43] text-white text-xs px-3 py-1.5 rounded shadow">
          Drag to select an area · <button type="button" className="underline" onClick={(e) => { e.stopPropagation(); setSelecting(false); setRect(null); onCancel(); }}>cancel</button>
        </div>
        {rect && (
          <div
            className="absolute border-2 border-[#e5484d] bg-[#e5484d]/10"
            style={{ left: rect.x, top: rect.y, width: rect.w, height: rect.h }}
          />
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <button
        type="button" disabled={busy} onClick={() => void runCapture()}
        className="px-3 py-1.5 text-xs rounded border border-[#0b2b43] text-[#0b2b43] hover:bg-[#0b2b43] hover:text-white disabled:opacity-40"
      >{busy ? 'Capturing…' : 'Full page'}</button>
      <button
        type="button" disabled={busy} onClick={() => setSelecting(true)}
        className="px-3 py-1.5 text-xs rounded border border-[#0b2b43] text-[#0b2b43] hover:bg-[#0b2b43] hover:text-white disabled:opacity-40"
      >Select region</button>
      <button type="button" onClick={onCancel} className="px-2 py-1.5 text-xs text-gray-500 hover:text-gray-700">Skip</button>
    </div>
  );
}
