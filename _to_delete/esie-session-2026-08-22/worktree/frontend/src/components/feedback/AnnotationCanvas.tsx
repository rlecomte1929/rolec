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

export type Tool = 'pen' | 'rect' | 'circle' | 'arrow' | 'text';
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
    const [pendingText, setPendingText] = useState<{ cx: number; cy: number } | null>(null);
    const [textValue, setTextValue]     = useState('');

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
      // Text tool: record click position and show input — no canvas drag needed.
      if (tool === 'text') {
        const p = pos(e);
        setPendingText({ cx: p.x, cy: p.y });
        return;
      }
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
        else if (tool === 'circle') {
          const cx = (s.x + p.x) / 2, cy = (s.y + p.y) / 2;
          const rx = Math.abs(p.x - s.x) / 2, ry = Math.abs(p.y - s.y) / 2;
          if (rx > 0 && ry > 0) { c.beginPath(); c.ellipse(cx, cy, rx, ry, 0, 0, 2 * Math.PI); c.stroke(); }
        } else drawArrow(c, s.x, s.y, p.x, p.y);
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

    const commitText = () => {
      const trimmed = textValue.trim();
      if (trimmed && pendingText) {
        const c = ctx(), canvas = canvasRef.current;
        if (c && canvas) {
          // Scale font size to canvas pixel density so text looks consistent
          const scale = canvas.width / Math.max(1, canvas.offsetWidth || canvas.width);
          const fontSize = Math.round(16 * scale);
          c.fillStyle = STROKE;
          c.font = `bold ${fontSize}px sans-serif`;
          c.fillText(trimmed, pendingText.cx, pendingText.cy);
          // Push AFTER drawing so undoStack's top matches the canvas — same invariant
          // as commit() (pushing before would make one undo remove text + the next shape).
          const snap = snapshot();
          if (snap) undoStack.current.push(snap);
        }
      }
      setPendingText(null);
      setTextValue('');
    };

    // Focus the text input once when it mounts (stable identity → fires only on
    // mount/unmount, not every render — the repo avoids the autoFocus prop).
    const focusTextInput = useCallback((el: HTMLInputElement | null) => { el?.focus(); }, []);

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
          {toolBtn('pen',    'Pen')}
          {toolBtn('rect',   'Rect')}
          {toolBtn('circle', 'Circle')}
          {toolBtn('arrow',  'Arrow')}
          {toolBtn('text',   'Text')}
          <button type="button" onClick={undo}  className="px-2 py-1 text-xs rounded border border-gray-300 text-gray-700">Undo</button>
          <button type="button" onClick={clear} className="px-2 py-1 text-xs rounded border border-gray-300 text-gray-700">Clear</button>
        </div>
        {/* Text-tool pending input — appears after user clicks on canvas with Text active */}
        {pendingText && (
          <div className="flex items-center gap-1.5 mb-1.5">
            <input
              ref={focusTextInput}
              type="text"
              value={textValue}
              onChange={(e) => setTextValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') { e.preventDefault(); commitText(); }
                if (e.key === 'Escape') { setPendingText(null); setTextValue(''); }
              }}
              placeholder="Type text, then Enter"
              className="flex-1 text-xs border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-[#0b2b43]"
            />
            <button type="button" onClick={commitText}
              className="text-xs px-2 py-1 bg-[#0b2b43] text-white rounded">Add</button>
            <button type="button" onClick={() => { setPendingText(null); setTextValue(''); }}
              className="text-xs px-2 py-1 text-gray-500">✕</button>
          </div>
        )}
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
