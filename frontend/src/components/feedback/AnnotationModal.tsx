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
