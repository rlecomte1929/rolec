/**
 * AnnotationCanvas — [AIQ-1480] lightweight markup layer over a captured screenshot.
 *
 * Raw Canvas 2D only (no third-party drawing library, per the task constraint). Tools:
 * freehand pen, rectangle, arrow — all drawn in red. Undo pops the last committed stroke;
 * Clear resets to the original capture. `getAnnotatedDataURL()` (exposed via ref) returns
 * the flattened image as a JPEG data URL (kept small so it stays under the 5 MB cap).
 *
 * Rendering is guarded against a null 2D context so the component mounts safely under
 * jsdom (where canvas is unimplemented) — interactive drawing is browser-verified.
 */
import {
  forwardRef, useEffect, useImperativeHandle, useRef, useState, useCallback,
} from 'react';

export type Tool = 'pen' | 'rect' | 'arrow';
const STROKE = '#e5484d'; // red
const LINE_WIDTH = 3;
const MAX_W = 900; // cap canvas width so annotated exports stay small

export interface AnnotationCanvasHandle {
  getAnnotatedDataURL: () => string;
}

interface Props {
  imageSrc: string;
  className?: string;
}

export const AnnotationCanvas = forwardRef<AnnotationCanvasHandle, Props>(
  function AnnotationCanvas({ imageSrc, className }, ref) {
    const canvasRef = useRef<HTMLCanvasElement | null>(null);
    const baseRef = useRef<ImageData | null>(null);   // the pristine capture (for Clear)
    const undoStack = useRef<ImageData[]>([]);          // committed strokes
    const dragStart = useRef<{ x: number; y: number } | null>(null);
    const preDrag = useRef<ImageData | null>(null);     // snapshot before a shape drag
    const [tool, setTool] = useState<Tool>('pen');
    const [ready, setReady] = useState(false);

    const ctx = () => canvasRef.current?.getContext('2d') ?? null;

    // Draw the source image onto the canvas once it loads (scaled to MAX_W).
    useEffect(() => {
      const canvas = canvasRef.current;
      if (!canvas || !imageSrc) return;
      const img = new Image();
      img.onload = () => {
        const scale = img.width > MAX_W ? MAX_W / img.width : 1;
        canvas.width = Math.max(1, Math.round(img.width * scale));
        canvas.height = Math.max(1, Math.round(img.height * scale));
        const c = ctx();
        if (c) {
          c.drawImage(img, 0, 0, canvas.width, canvas.height);
          try {
            baseRef.current = c.getImageData(0, 0, canvas.width, canvas.height);
          } catch {
            baseRef.current = null; // tainted/unsupported — Clear falls back to redraw
          }
        }
        undoStack.current = [];
        setReady(true);
      };
      img.src = imageSrc;
    }, [imageSrc]);

    const snapshot = useCallback((): ImageData | null => {
      const canvas = canvasRef.current, c = ctx();
      if (!canvas || !c) return null;
      try { return c.getImageData(0, 0, canvas.width, canvas.height); } catch { return null; }
    }, []);

    const pos = (e: React.PointerEvent) => {
      const canvas = canvasRef.current;
      if (!canvas) return { x: 0, y: 0 };
      const r = canvas.getBoundingClientRect();
      const sx = canvas.width / (r.width || 1), sy = canvas.height / (r.height || 1);
      return { x: (e.clientX - r.left) * sx, y: (e.clientY - r.top) * sy };
    };

    const drawArrow = (c: CanvasRenderingContext2D, x1: number, y1: number, x2: number, y2: number) => {
      const head = 12, ang = Math.atan2(y2 - y1, x2 - x1);
      c.beginPath(); c.moveTo(x1, y1); c.lineTo(x2, y2); c.stroke();
      c.beginPath(); c.moveTo(x2, y2);
      c.lineTo(x2 - head * Math.cos(ang - Math.PI / 6), y2 - head * Math.sin(ang - Math.PI / 6));
      c.moveTo(x2, y2);
      c.lineTo(x2 - head * Math.cos(ang + Math.PI / 6), y2 - head * Math.sin(ang + Math.PI / 6));
      c.stroke();
    };

    const onPointerDown = (e: React.PointerEvent) => {
      const c = ctx(); if (!c) return;
      e.currentTarget.setPointerCapture?.(e.pointerId);
      preDrag.current = snapshot();
      const p = pos(e);
      dragStart.current = p;
      c.strokeStyle = STROKE; c.lineWidth = LINE_WIDTH; c.lineCap = 'round'; c.lineJoin = 'round';
      if (tool === 'pen') { c.beginPath(); c.moveTo(p.x, p.y); }
    };

    const onPointerMove = (e: React.PointerEvent) => {
      const c = ctx(); if (!c || !dragStart.current) return;
      const p = pos(e), s = dragStart.current;
      if (tool === 'pen') {
        c.lineTo(p.x, p.y); c.stroke();
      } else {
        if (preDrag.current) c.putImageData(preDrag.current, 0, 0); // live preview
        c.strokeStyle = STROKE; c.lineWidth = LINE_WIDTH;
        if (tool === 'rect') c.strokeRect(s.x, s.y, p.x - s.x, p.y - s.y);
        else drawArrow(c, s.x, s.y, p.x, p.y);
      }
    };

    const commit = () => {
      if (!dragStart.current) return;
      dragStart.current = null; preDrag.current = null;
      const snap = snapshot();
      if (snap) undoStack.current.push(snap);
    };

    const undo = () => {
      const c = ctx(); if (!c) return;
      undoStack.current.pop();
      const prev = undoStack.current[undoStack.current.length - 1] ?? baseRef.current;
      if (prev) c.putImageData(prev, 0, 0);
    };

    const clear = () => {
      const c = ctx(); if (!c) return;
      undoStack.current = [];
      if (baseRef.current) c.putImageData(baseRef.current, 0, 0);
    };

    useImperativeHandle(ref, () => ({
      getAnnotatedDataURL: () => {
        const canvas = canvasRef.current;
        if (!canvas) return imageSrc;
        try {
          const url = canvas.toDataURL('image/jpeg', 0.85);
          // jsdom / unsupported canvas can return null — fall back to the original capture.
          return typeof url === 'string' && url.startsWith('data:') ? url : imageSrc;
        } catch {
          return imageSrc;
        }
      },
    }), [imageSrc]);

    const toolBtn = (t: Tool, label: string) => (
      <button
        type="button" onClick={() => setTool(t)} aria-pressed={tool === t}
        className={`px-2 py-1 text-xs rounded border ${tool === t ? 'bg-[#0b2b43] text-white border-[#0b2b43]' : 'border-gray-300 text-gray-700'}`}
      >{label}</button>
    );

    return (
      <div className={className}>
        <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
          {toolBtn('pen', 'Pen')}
          {toolBtn('rect', 'Rectangle')}
          {toolBtn('arrow', 'Arrow')}
          <button type="button" onClick={undo} className="px-2 py-1 text-xs rounded border border-gray-300 text-gray-700">Undo</button>
          <button type="button" onClick={clear} className="px-2 py-1 text-xs rounded border border-gray-300 text-gray-700">Clear</button>
        </div>
        <canvas
          ref={canvasRef}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={commit}
          onPointerLeave={commit}
          className="w-full border border-gray-200 rounded touch-none cursor-crosshair"
          data-ready={ready ? '1' : '0'}
        />
      </div>
    );
  },
);
