// AIQ-1492 — "New feedback": admin authors a dispatch-ready product-stream item.
// Posts to POST /api/admin/feedback (createAdminFeedback). Screenshot is optional and
// supports BOTH upload (png/jpg, compressed client-side) and "Capture current screen"
// (same html2canvas util + JPEG 0.65 as the tester widget). On success the parent
// refreshes the Inbox; the new item lands already dispatch-ready.
import { useState } from 'react';
import { Plus, Camera, Upload, X } from 'lucide-react';
import { Modal, Button, Input } from '../antigravity';
import { FileInput } from '../antigravity/FileInput';
import { createAdminFeedback } from '../../api/adminFeedback';
import { captureScreenshotDataUrl } from '../../utils/captureScreenshot';
import { getApiErrorMessage } from '../../utils/apiDetail';

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (id: string) => void;
}

type Category = 'bug' | 'idea' | 'other';
const MAX_UPLOAD_BYTES = 8_000_000;

// Compress an uploaded image the same way as the widget capture (JPEG, capped dimension)
// so upload + capture produce the same stored shape.
async function compressImageFile(file: File): Promise<string> {
  const rawUrl = await new Promise<string>((resolve, reject) => {
    const r = new FileReader();
    // readAsDataURL always yields a string result.
    r.onload = () => resolve(r.result as string);
    r.onerror = () => reject(new Error('Could not read the file.'));
    r.readAsDataURL(file);
  });
  const img = await new Promise<HTMLImageElement>((resolve, reject) => {
    const el = new Image();
    el.onload = () => resolve(el);
    el.onerror = () => reject(new Error('Could not load the image.'));
    el.src = rawUrl;
  });
  const maxDim = 1600;
  const scale = Math.min(1, maxDim / Math.max(img.width, img.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(img.width * scale);
  canvas.height = Math.round(img.height * scale);
  const ctx = canvas.getContext('2d');
  if (!ctx) return rawUrl;
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL('image/jpeg', 0.7);
}

export function NewFeedbackModal({ open, onClose, onCreated }: Props) {
  const [pageUrl, setPageUrl] = useState(window.location.pathname);
  const [category, setCategory] = useState<Category>('bug');
  const [message, setMessage] = useState('');
  const [dispatchContext, setDispatchContext] = useState('');
  const [severity, setSeverity] = useState('');
  const [area, setArea] = useState('');
  const [stepsToReproduce, setStepsToReproduce] = useState('');
  const [expected, setExpected] = useState('');
  const [actual, setActual] = useState('');
  const [persona, setPersona] = useState('');
  const [screenshot, setScreenshot] = useState<string | null>(null);
  const [capturing, setCapturing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  function reset() {
    setPageUrl(window.location.pathname);
    setCategory('bug'); setMessage(''); setDispatchContext('');
    setSeverity(''); setArea('');
    setStepsToReproduce(''); setExpected(''); setActual(''); setPersona('');
    setScreenshot(null); setError('');
  }

  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    setError('');
    const file = e.target.files?.[0];
    if (!file) return;
    if (!/^image\/(png|jpe?g)$/.test(file.type)) { setError('Only PNG or JPG images are supported.'); return; }
    if (file.size > MAX_UPLOAD_BYTES) { setError('Image is too large (max 8 MB).'); return; }
    try {
      setScreenshot(await compressImageFile(file));
    } catch (err) {
      setError((err as { message?: string })?.message ?? 'Could not attach the image.');
    }
  }

  async function onCapture() {
    setError('');
    setCapturing(true);
    try {
      // Hide the whole modal (backdrop included) from the capture so the screenshot
      // shows the underlying screen undimmed — the backdrop is the `.fixed` ancestor.
      const panel = document.getElementById('new-feedback-modal');
      const overlay = (panel?.closest('.fixed') as HTMLElement | null) ?? panel;
      setScreenshot(await captureScreenshotDataUrl(overlay));
    } catch {
      setError('Screen capture failed in this browser.');
    } finally {
      setCapturing(false);
    }
  }

  async function submit() {
    setError('');
    if (!message.trim()) { setError('A description is required.'); return; }
    if (!dispatchContext.trim()) { setError('Dispatch context is required so the item is dispatch-ready.'); return; }
    setSubmitting(true);
    try {
      const client_context: Record<string, unknown> = {};
      if (stepsToReproduce.trim()) client_context.steps_to_reproduce = stepsToReproduce.trim();
      if (expected.trim()) client_context.expected = expected.trim();
      if (actual.trim()) client_context.actual = actual.trim();
      if (persona.trim()) client_context.persona = persona.trim();
      const { id } = await createAdminFeedback({
        page_url: pageUrl.trim() || window.location.pathname,
        category,
        message: message.trim(),
        dispatch_context: dispatchContext.trim(),
        severity: severity.trim() || null,
        area: area.trim() || null,
        screenshot_data: screenshot,
        client_context: Object.keys(client_context).length ? client_context : null,
      });
      reset();
      onCreated(id);
      onClose();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Could not create the feedback item.'));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="New feedback" className="max-w-lg w-full p-5">
      <div id="new-feedback-modal" className="space-y-3 max-h-[70vh] overflow-y-auto">
        <Input label="Page / route" value={pageUrl} onChange={setPageUrl} fullWidth />

        <div className="flex gap-3">
          <label className="flex-1 text-sm">
            <span className="block mb-1 text-slate-600">Category</span>
            <select value={category} onChange={(e) => setCategory(e.target.value as Category)}
              className="w-full border border-slate-200 rounded px-2 py-1.5 text-sm">
              <option value="bug">Bug</option>
              <option value="idea">Idea</option>
              <option value="other">Other</option>
            </select>
          </label>
          <Input label="Severity" value={severity} onChange={setSeverity} placeholder="e.g. medium" />
          <Input label="Area" value={area} onChange={setArea} placeholder="e.g. api" />
        </div>

        <label className="block text-sm">
          <span className="block mb-1 text-slate-600">Description *</span>
          <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={3}
            className="w-full border border-slate-200 rounded px-2 py-1.5 text-sm" />
        </label>

        <label className="block text-sm">
          <span className="block mb-1 text-slate-600">Dispatch context * <span className="text-slate-400">(makes it dispatch-ready)</span></span>
          <textarea value={dispatchContext} onChange={(e) => setDispatchContext(e.target.value)} rows={3}
            className="w-full border border-slate-200 rounded px-2 py-1.5 text-sm" />
        </label>

        <details className="text-sm">
          <summary className="cursor-pointer text-slate-600">Structured details (optional)</summary>
          <div className="space-y-2 mt-2">
            <Input label="Steps to reproduce" value={stepsToReproduce} onChange={setStepsToReproduce} fullWidth />
            <div className="flex gap-2">
              <Input label="Expected" value={expected} onChange={setExpected} fullWidth />
              <Input label="Actual" value={actual} onChange={setActual} fullWidth />
            </div>
            <Input label="Persona (HR | Employee | Admin)" value={persona} onChange={setPersona} fullWidth />
          </div>
        </details>

        {/* Screenshot: upload OR capture, optional */}
        <div className="text-sm">
          <span className="block mb-1 text-slate-600">Screenshot (optional)</span>
          {screenshot ? (
            <div className="relative inline-block">
              <img src={screenshot} alt="attached screenshot" className="max-h-28 rounded border border-slate-200" />
              <button type="button" onClick={() => setScreenshot(null)} aria-label="Remove screenshot"
                className="absolute -top-2 -right-2 bg-slate-800 text-white rounded-full w-5 h-5 flex items-center justify-center">
                <X className="w-3 h-3" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <label className="inline-flex items-center gap-1.5 cursor-pointer border border-slate-200 rounded px-3 py-1.5 hover:bg-slate-50">
                <Upload className="w-4 h-4" /> Upload
                <FileInput accept="image/png,image/jpeg" onChange={onPickFile} className="hidden" />
              </label>
              <Button type="button" variant="ghost" onClick={() => void onCapture()} disabled={capturing}
                className="inline-flex items-center gap-1.5 border border-slate-200 !py-1.5">
                <Camera className="w-4 h-4" /> {capturing ? 'Capturing…' : 'Capture current screen'}
              </Button>
            </div>
          )}
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="button" onClick={() => void submit()} disabled={submitting}
            className="inline-flex items-center gap-1.5">
            <Plus className="w-4 h-4" /> {submitting ? 'Creating…' : 'Create & make dispatch-ready'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
