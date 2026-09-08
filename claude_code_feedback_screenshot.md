# Claude Code Prompt — FeedbackWidget Screenshot Improvements

## Context

The FeedbackWidget (`frontend/src/components/FeedbackWidget.tsx`) is a floating
feedback button that lets users on relopass.com report bugs, ideas, and other
feedback. It has three sub-components:

- `ScreenshotCapture.tsx` — takes a page screenshot via html2canvas (full-page or
  drag-select region)
- `AnnotationCanvas.tsx` — draws annotations (pen, rect, arrow) over a captured image
- Both live in `frontend/src/components/feedback/`

**Three problems to fix:**

**Problem 1 — Dropdowns close when clicking the screenshot button.**
If a user has a page dropdown open and wants to screenshot it, clicking any button
in the widget triggers the dropdown's "click-outside" detection and closes it.
Fix: add a **delayed capture** option (5-second countdown). During the countdown
the widget hides itself, the user re-opens their dropdown, then the screenshot
fires automatically.

**Problem 2 — No way to upload an image from disk.**
Users want to attach an existing screenshot or image file instead of taking a live
capture. Fix: add an "Upload image" option that accepts any image file and feeds it
into the same annotation flow as a captured screenshot.

**Problem 3 — Annotation canvas is cramped inside the 320px widget popover.**
The annotation UI is squeezed into the small `w-80` widget panel. Users want a
large fullscreen annotation workspace with more tools. Fix: open a fullscreen
**annotation modal** (via React portal to `document.body`) after any capture or
upload. Add `circle` and `text` tools to the existing pen/rect/arrow set.

---

## Branch

```bash
git checkout -b feat/feedback-screenshot-ux origin/main
```

---

## Files to create / modify

```
frontend/src/components/feedback/AnnotationCanvas.tsx   MODIFY
frontend/src/components/feedback/AnnotationModal.tsx    CREATE
frontend/src/components/feedback/ScreenshotCapture.tsx  MODIFY
frontend/src/components/FeedbackWidget.tsx              MODIFY
```

Read all four files (three existing, one to create) before touching anything.

---

## Change 1 — `AnnotationCanvas.tsx`: add circle + text tools

### 1a. Extend the Tool type

Replace:
```typescript
export type Tool = 'pen' | 'rect' | 'arrow';
```
with:
```typescript
export type Tool = 'pen' | 'rect' | 'circle' | 'arrow' | 'text';
```

### 1b. Add text-pending state (after the existing `useState` declarations)

```typescript
const [pendingText, setPendingText] = useState<{ cx: number; cy: number } | null>(null);
const [textValue, setTextValue]     = useState('');
```

### 1c. Handle circle in `onPointerMove`

In the `else` branch of `onPointerMove` (where `tool !== 'pen'`), add `circle`
alongside `rect` and `arrow`:

```typescript
if (tool === 'rect')   c.strokeRect(s.x, s.y, p.x - s.x, p.y - s.y);
else if (tool === 'circle') {
  const cx = (s.x + p.x) / 2, cy = (s.y + p.y) / 2;
  const rx = Math.abs(p.x - s.x) / 2, ry = Math.abs(p.y - s.y) / 2;
  if (rx > 0 && ry > 0) { c.beginPath(); c.ellipse(cx, cy, rx, ry, 0, 0, 2 * Math.PI); c.stroke(); }
} else drawArrow(c, s.x, s.y, p.x, p.y);
```

### 1d. Handle text tool in `onPointerDown`

At the START of `onPointerDown`, before the pointer-capture line, add an early
return for the text tool:

```typescript
const onPointerDown = (e: React.PointerEvent) => {
  // Text tool: record click position and show input — no canvas drag needed.
  if (tool === 'text') {
    const p = pos(e);
    setPendingText({ cx: p.x, cy: p.y });
    return;
  }
  const c = ctx(); if (!c) return;
  // ... rest of existing handler unchanged
```

### 1e. Add `commitText` function (after the existing `clear` function)

```typescript
const commitText = () => {
  const trimmed = textValue.trim();
  if (trimmed && pendingText) {
    const c = ctx(), canvas = canvasRef.current;
    if (c && canvas) {
      // Scale font size to canvas pixel density so text looks consistent
      const scale = canvas.width / Math.max(1, canvas.offsetWidth || canvas.width);
      const fontSize = Math.round(16 * scale);
      const snap = snapshot();
      if (snap) undoStack.current.push(snap);
      c.fillStyle = STROKE;
      c.font = `bold ${fontSize}px sans-serif`;
      c.fillText(trimmed, pendingText.cx, pendingText.cy);
    }
  }
  setPendingText(null);
  setTextValue('');
};
```

### 1f. Update the toolbar JSX

Replace the existing toolbar `<div className="flex items-center gap-1.5 mb-1.5 flex-wrap">` block with:

```tsx
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
      autoFocus
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
```

The `<canvas>` element and the `useImperativeHandle` block are **unchanged**.

---

## Change 2 — Create `AnnotationModal.tsx`

Create `frontend/src/components/feedback/AnnotationModal.tsx`:

```typescript
/**
 * AnnotationModal — full-screen annotation workspace for the FeedbackWidget.
 *
 * Rendered via React portal directly onto document.body so it covers the
 * entire viewport regardless of the widget's stacking context (z-50). Tools
 * (pen, rect, circle, arrow, text, undo, clear) live in the AnnotationCanvas
 * child. The modal provides the Save / Cancel actions.
 *
 * z-index: 10000 — above the capture overlay (9998) and the widget (50).
 */
import { createPortal } from 'react-dom';
import { useRef } from 'react';
import { AnnotationCanvas, type AnnotationCanvasHandle } from './AnnotationCanvas';

interface Props {
  imageSrc: string;
  onSave:   (dataUrl: string) => void;
  onCancel: () => void;
}

export function AnnotationModal({ imageSrc, onSave, onCancel }: Props) {
  const annotRef = useRef<AnnotationCanvasHandle>(null);

  const handleSave = () => {
    const url = annotRef.current?.getAnnotatedDataURL() ?? imageSrc;
    onSave(url);
  };

  return createPortal(
    <div
      data-html2canvas-ignore
      className="fixed inset-0 z-[10000] flex flex-col bg-black/85"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-[#0b2b43] shrink-0">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
          </svg>
          <span className="text-white text-sm font-semibold">Annotate screenshot</span>
          <span className="text-white/50 text-xs hidden sm:inline">
            — draw on the image, then save to attach
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button" onClick={onCancel}
            className="text-xs px-3 py-1.5 rounded border border-white/30 text-white/80 hover:bg-white/10 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button" onClick={handleSave}
            className="text-xs font-semibold px-4 py-1.5 rounded bg-[#1f8e8b] text-white hover:bg-[#177a77] transition-colors"
          >
            Save &amp; attach
          </button>
        </div>
      </div>

      {/* Canvas area — scrollable, centered */}
      <div className="flex-1 overflow-auto p-4 sm:p-8 flex flex-col items-center">
        <div className="w-full max-w-5xl">
          <AnnotationCanvas
            ref={annotRef}
            imageSrc={imageSrc}
            className="bg-white rounded-lg shadow-2xl overflow-hidden"
          />
        </div>
      </div>
    </div>,
    document.body,
  );
}
```

---

## Change 3 — `ScreenshotCapture.tsx`: add delayed capture countdown

### 3a. Extend Props

```typescript
interface Props {
  onCapture:      (dataUrl: string) => void;
  onCancel:       () => void;
  onDelayStart?:  () => void;  // called when countdown begins — parent can hide itself
}
```

### 3b. Add countdown state

After the existing `useState` lines:

```typescript
const [countdown, setCountdown] = useState<number | null>(null);
```

### 3c. Add a `startDelayed` function and a countdown `useEffect`

Import `useEffect` if not already imported (it's not in the current file — add it
to the `react` import).

```typescript
// Countdown effect: ticks every second, fires capture at 0.
useEffect(() => {
  if (countdown === null) return;
  if (countdown === 0) {
    void runCapture();
    setCountdown(null);
    return;
  }
  const id = window.setTimeout(() => setCountdown((n) => (n !== null ? n - 1 : null)), 1000);
  return () => window.clearTimeout(id);
}, [countdown, runCapture]);

const startDelayed = () => {
  onDelayStart?.();
  setCountdown(5);
};
```

### 3d. Render the countdown overlay

When `countdown !== null`, render a fixed full-screen overlay instead of the
normal button row. Add this BEFORE the `if (selecting)` guard at the top of the
return:

```tsx
if (countdown !== null) {
  return (
    <div
      data-html2canvas-ignore
      className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-black/60"
    >
      <div className="text-white text-center space-y-2">
        <p className="text-6xl font-bold tabular-nums leading-none">{countdown}</p>
        <p className="text-sm text-white/70">
          {countdown > 0 ? 'Open your dropdown now — screenshot in…' : 'Capturing…'}
        </p>
        <button
          type="button"
          onClick={() => { setCountdown(null); onCancel(); }}
          className="mt-2 text-xs text-white/60 underline hover:text-white"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
```

### 3e. Add the "Delayed (5s)" button to the normal button row

In the existing `return (...)` (the non-selecting, non-busy state), add a third
button between "Select region" and "Skip":

```tsx
<button
  type="button" disabled={busy} onClick={startDelayed}
  className="px-3 py-1.5 text-xs rounded border border-[#0b2b43] text-[#0b2b43] hover:bg-[#0b2b43] hover:text-white disabled:opacity-40"
>Delayed (5s)</button>
```

The full row becomes: Full page | Select region | Delayed (5s) | Skip

---

## Change 4 — `FeedbackWidget.tsx`: file upload + use AnnotationModal + delay hook

### 4a. Add imports

Add to the existing imports at the top:

```typescript
import { AnnotationModal } from './feedback/AnnotationModal';
```

Keep the existing `AnnotationCanvas` import — **remove it** since `AnnotationCanvas`
is now only used inside `AnnotationModal`, not directly in `FeedbackWidget`.

Add a `useRef` for the file input (the existing `useRef` import already covers this):
```typescript
const fileInputRef = useRef<HTMLInputElement>(null);
```

Also **remove** `annotRef` — it's no longer used directly in `FeedbackWidget`.

### 4b. Update `onCaptured` to reset state when coming from delayed capture

Replace:
```typescript
const onCaptured = (dataUrl: string) => {
  setRawCapture(dataUrl);
  setShotStep('annotate');
};
```
with:
```typescript
const onCaptured = (dataUrl: string) => {
  setRawCapture(dataUrl);
  setShotStep('annotate');
  // If we were hidden during a delayed capture, reopen the widget popover.
  setState((s) => s === 'capturing' ? 'open' : s);
};
```

### 4c. Update `attachAnnotated` to accept the already-processed dataUrl from the modal

The modal calls `onSave(dataUrl)` with the annotated URL directly. Replace:
```typescript
const attachAnnotated = () => {
  const url = annotRef.current?.getAnnotatedDataURL() ?? rawCapture;
  setScreenshot(url);
  setRawCapture(null);
  setShotStep('none');
};
```
with:
```typescript
const attachAnnotated = (dataUrl: string) => {
  setScreenshot(dataUrl);
  setRawCapture(null);
  setShotStep('none');
};
```

### 4d. Add file-upload handler

Add this function after `attachAnnotated`:

```typescript
const onFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
  const file = e.target.files?.[0];
  if (!file) return;
  // Reset the input so the same file can be re-selected after cancel.
  e.target.value = '';
  const reader = new FileReader();
  reader.onload = (ev) => {
    const dataUrl = ev.target?.result;
    if (typeof dataUrl === 'string') onCaptured(dataUrl);
  };
  reader.readAsDataURL(file);
};
```

### 4e. Update the JSX

**4e-i. Add the AnnotationModal and hidden file input OUTSIDE the `isVisible` block.**

At the very top of the outer `<div>` (the fixed container), before `{isVisible && ...}`, add:

```tsx
{/* Annotation modal — fullscreen via portal, shown when a capture/upload is ready */}
{shotStep === 'annotate' && rawCapture && (
  <AnnotationModal
    imageSrc={rawCapture}
    onSave={attachAnnotated}
    onCancel={() => { setRawCapture(null); setShotStep('none'); }}
  />
)}

{/* Hidden file input for "Upload image" */}
<input
  ref={fileInputRef}
  type="file"
  accept="image/*"
  className="hidden"
  onChange={onFileUpload}
/>
```

**4e-ii. Replace the screenshot section inside the form.**

Find the `{/* Screenshot: capture ... */}` `<div className="space-y-2">` block
(around line 297–345). Replace the entire block with:

```tsx
{/* Attach image — screenshot or upload */}
<div className="space-y-2">
  {shotStep === 'capture' ? (
    <ScreenshotCapture
      onCapture={onCaptured}
      onCancel={() => setShotStep('none')}
      onDelayStart={() => setState('capturing')}
    />
  ) : screenshot ? (
    <div className="relative rounded-lg overflow-hidden border border-gray-200">
      <img src={screenshot} alt="Attached image" className="w-full object-cover max-h-28" />
      <button
        type="button"
        onClick={() => setScreenshot(null)}
        className="absolute top-1 right-1 w-5 h-5 rounded-full bg-gray-900/70 text-white text-[10px] flex items-center justify-center hover:bg-gray-900"
        title="Remove image"
      >
        ✕
      </button>
      <div className="absolute bottom-1 left-1 text-[9px] font-mono bg-gray-900/60 text-white rounded px-1.5 py-0.5">
        image attached
      </div>
    </div>
  ) : (
    <div className="flex gap-2">
      {/* Take screenshot */}
      <Button unstyled
        onClick={() => setShotStep('capture')}
        disabled={state === 'submitting'}
        className="flex-1 flex items-center justify-center gap-1.5 text-xs py-1.5 px-3 rounded-lg border border-dashed border-gray-300 text-gray-500 hover:border-gray-400 hover:text-gray-700 transition-colors disabled:opacity-40"
      >
        <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zM18.75 10.5h.008v.008h-.008V10.5z" />
        </svg>
        Screenshot
      </Button>
      {/* Upload from disk */}
      <Button unstyled
        onClick={() => fileInputRef.current?.click()}
        disabled={state === 'submitting'}
        className="flex-1 flex items-center justify-center gap-1.5 text-xs py-1.5 px-3 rounded-lg border border-dashed border-gray-300 text-gray-500 hover:border-gray-400 hover:text-gray-700 transition-colors disabled:opacity-40"
      >
        <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
        Upload
      </Button>
    </div>
  )}
</div>
```

Note: the `shotStep === 'annotate'` case is intentionally absent here — when the
annotation modal is open it renders fullscreen via portal, so the widget form just
shows whatever was visible before (the capture buttons). The modal covers everything.

**4e-iii. Remove the stale `annotRef` usage.**

The existing code has `const annotRef = useRef<AnnotationCanvasHandle>(null)`.
Since `AnnotationCanvas` is no longer rendered directly in `FeedbackWidget`,
remove this ref declaration and its import (`AnnotationCanvasHandle` type from
`AnnotationCanvas`). The `AnnotationModal` owns the canvas ref internally.

---

## Verification

```bash
# Type-check — must be clean (zero errors)
cd frontend && npx tsc --noEmit

# Run existing feedback component tests
cd frontend && npx vitest src/components/feedback --run

# Quick build check
npm run build
```

Expected: no TypeScript errors, existing tests pass (they don't test the new
tools or modal, so they'll stay green).

---

## Commit

```bash
git add frontend/src/components/feedback/AnnotationCanvas.tsx \
        frontend/src/components/feedback/AnnotationModal.tsx \
        frontend/src/components/feedback/ScreenshotCapture.tsx \
        frontend/src/components/FeedbackWidget.tsx

git commit -m "feat(feedback): delayed screenshot, image upload, fullscreen annotation modal

Three UX improvements to the FeedbackWidget screenshot flow:

1. DELAYED SCREENSHOT (fix for dropdown capture)
   ScreenshotCapture gains a 'Delayed (5s)' button. Clicking it shows a
   full-screen countdown overlay; the widget hides itself via setState('capturing').
   The user re-opens their dropdown, capture fires at 0, widget resumes.

2. IMAGE UPLOAD
   Two side-by-side buttons replace the single 'Attach Screenshot' button:
   'Screenshot' (existing flow) and 'Upload' (hidden file input, any image/*).
   Uploaded images go through the same annotation modal as screenshots.

3. FULLSCREEN ANNOTATION MODAL (AnnotationModal.tsx — new component)
   After any capture or upload, an AnnotationModal opens fullscreen via React
   portal (z-[10000]) instead of the cramped inline canvas. Provides a
   scrollable, centred canvas with a visible toolbar. Save & attach / Cancel.

4. NEW ANNOTATION TOOLS (AnnotationCanvas.tsx)
   Added: Circle (ellipse, same drag-to-size as Rect) and Text (click canvas
   → input appears in toolbar → Enter commits text at clicked position).
   Tool row is now: Pen | Rect | Circle | Arrow | Text | Undo | Clear"
```

---

## What NOT to do

- Do not add a new npm package. html2canvas is already installed; the text tool
  uses canvas native `fillText`; the portal uses `react-dom` (already a dep).
- Do not change the `submit()` function or the Supabase insert logic — the
  `screenshot` state still holds a data URL as before.
- Do not touch the backend, admin panel, or any other frontend file.
- Do not modify the existing `AnnotationCanvas` test file — the new tools don't
  require new unit tests now; they can be added in a follow-up.
- The `WidgetState` type in `FeedbackWidget` does NOT need a new value — the
  existing `'capturing'` state is reused to hide the widget during delayed capture.
