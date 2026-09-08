/**
 * TestDriveFrictionPrompt — TD-M1 (AIQ-1557): recover the dropout voice.
 *
 * When a test-drive tester stalls on a stage (idle) or moves to leave (cursor exits
 * the top of the viewport), a one-tap "What stopped you here?" prompt appears and,
 * on submit or dismiss, records a `friction` funnel event tagged with the stage.
 *
 * Discipline (the hard constraint): it must NEVER fire for a tester advancing
 * normally, and it is a complete no-op for real users. Guards:
 *   - only mounts behavior when getTestDriveSession() is present (test-drive only);
 *   - fires at most once per stage; advancing (a route change) resets to the new
 *     stage and clears any open prompt — advancing is the opposite of friction;
 *   - the idle timer resets on every interaction, so an active tester never trips it.
 *
 * Best-effort throughout — nothing here blocks navigation or surfaces an error.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { getTestDriveSession, emitTestDriveFriction } from '../api/testDrive';

/** Map a pathname to a coarse, human-readable stage label for the friction metadata. */
export function stageFromPath(pathname: string): string {
  const p = (pathname || '').toLowerCase();
  if (p.includes('/intake')) return 'intake';
  if (p.includes('/roadmap')) return 'roadmap';
  if (p.includes('/dossier')) return 'dossier';
  if (p.includes('/services') || p.includes('/vendor')) return 'services';
  if (p.includes('/employee/case')) return 'employee-case';
  if (p.startsWith('/hr')) return 'hr';
  if (p.includes('/test-drive/survey')) return 'survey';
  if (p.includes('/test-drive')) return 'test-drive-start';
  return p.replace(/^\//, '').split('/')[0] || 'unknown';
}

const REASONS: { key: string; label: string }[] = [
  { key: 'confusing', label: 'Confusing' },
  { key: 'broken', label: 'Something broke' },
  { key: 'boring', label: 'Boring' },
  { key: 'no-time', label: 'No time right now' },
  { key: 'other', label: 'Other' },
];

export interface TestDriveFrictionPromptProps {
  /** Idle-on-stage timeout before the prompt appears. Overridable for tests. */
  idleMs?: number;
}

export function TestDriveFrictionPrompt({ idleMs = 90_000 }: TestDriveFrictionPromptProps) {
  const location = useLocation();
  const stage = stageFromPath(location.pathname);

  const [active] = useState(() => !!getTestDriveSession());
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<string | null>(null);
  const [text, setText] = useState('');
  // One prompt per stage: once fired (submitted or dismissed) for a stage, don't re-arm.
  const firedStages = useRef<Set<string>>(new Set());
  const idleTimer = useRef<number | null>(null);

  const trigger = useCallback(() => {
    if (!active) return;
    if (open) return;
    if (firedStages.current.has(stage)) return;
    setReason(null);
    setText('');
    setOpen(true);
  }, [active, open, stage]);

  // Advancing (a route change) is the opposite of friction: clear any open prompt and
  // reset arming for the new stage. This is why a happy-path run never sees the prompt.
  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  // Idle-on-stage timer + exit-intent (cursor leaving via the top of the viewport).
  useEffect(() => {
    if (!active) return undefined;
    const resetIdle = () => {
      if (idleTimer.current) window.clearTimeout(idleTimer.current);
      idleTimer.current = window.setTimeout(trigger, idleMs);
    };
    const onExitIntent = (e: MouseEvent) => {
      if (e.clientY <= 0) trigger(); // moving up to the tab bar / close button
    };
    const activity = ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'];
    activity.forEach((ev) => window.addEventListener(ev, resetIdle, { passive: true }));
    document.addEventListener('mouseleave', onExitIntent);
    resetIdle();
    return () => {
      if (idleTimer.current) window.clearTimeout(idleTimer.current);
      activity.forEach((ev) => window.removeEventListener(ev, resetIdle));
      document.removeEventListener('mouseleave', onExitIntent);
    };
  }, [active, idleMs, trigger, location.pathname]);

  if (!active || !open) return null;

  const record = (r: string) => {
    firedStages.current.add(stage);
    emitTestDriveFriction(stage, r, text);
    setOpen(false);
  };

  return (
    <div
      data-html2canvas-ignore
      className="fixed bottom-4 left-4 z-50 w-80 rounded-xl border border-gray-200 bg-white shadow-xl"
      role="dialog"
      aria-label="What stopped you here?"
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <p className="text-sm font-semibold text-gray-900">What stopped you here?</p>
        <button
          type="button"
          onClick={() => record('dismissed')}
          aria-label="Dismiss"
          className="text-gray-400 hover:text-gray-600"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div className="px-4 py-3 space-y-3">
        <div className="flex flex-wrap gap-2">
          {REASONS.map((r) => (
            <button
              key={r.key}
              type="button"
              onClick={() => setReason(r.key)}
              className={`text-xs py-1.5 px-3 rounded-full border font-medium transition-colors ${
                reason === r.key
                  ? 'bg-gray-900 text-white border-gray-900'
                  : 'border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
        <textarea
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Anything else? (optional)"
          className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 text-gray-800 placeholder-gray-300 resize-none focus:outline-none focus:ring-1 focus:ring-gray-400"
        />
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => record('dismissed')}
            className="text-xs text-gray-400 hover:text-gray-600"
          >
            Skip
          </button>
          <button
            type="button"
            onClick={() => record(reason || 'other')}
            className="text-xs font-semibold px-4 py-2 rounded-lg bg-gray-900 text-white hover:bg-gray-700 transition-colors"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

export default TestDriveFrictionPrompt;
