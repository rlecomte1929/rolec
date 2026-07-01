import { useEffect, useState } from 'react';
import { Card } from '../../components/antigravity';
import { getImmigrationSnapshot, type ImmigrationSnapshot } from '../../api/immigrationSnapshot';

/**
 * "Your move at a glance" (relocation-assistant Slice 2) — the proactive opener
 * above the immigration Q&A. Fetches the employee's snapshot and surfaces the
 * risk flags + checklist summary for THEIR case. Collapses to nothing when there
 * is no case or the corridor is uncovered (best-effort; never blocks the page).
 */
const SEVERITY_BOX: Record<string, string> = {
  critical: 'border-rose-200 bg-rose-50',
  warning: 'border-amber-200 bg-amber-50',
  info: 'border-slate-200 bg-slate-50',
};
const SEVERITY_TEXT: Record<string, string> = {
  critical: 'text-rose-700',
  warning: 'text-amber-700',
  info: 'text-slate-600',
};

export function MoveAtAGlance({ caseId }: { caseId: string | null }) {
  const [snap, setSnap] = useState<ImmigrationSnapshot | null>(null);

  useEffect(() => {
    if (!caseId) return;
    let active = true;
    getImmigrationSnapshot(caseId)
      .then((s) => {
        if (active) setSnap(s);
      })
      .catch(() => {
        /* best-effort — the Q&A still works without the snapshot */
      });
    return () => {
      active = false;
    };
  }, [caseId]);

  if (!snap || !snap.covered) return null;
  const hasRisks = snap.risk_flags.length > 0;
  if (!hasRisks && snap.checklist_summary.total === 0) return null;

  return (
    <Card>
      <div className="space-y-3 p-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-navy-800">Your move at a glance</h2>
          <span className="text-xs text-slate-500">
            {snap.corridor_from} → {snap.corridor_to} · {snap.checklist_summary.total} requirements
            {snap.checklist_summary.conditional ? ` · ${snap.checklist_summary.conditional} conditional` : ''}
          </span>
        </div>
        {hasRisks ? (
          <ul className="space-y-2">
            {snap.risk_flags.map((r) => (
              <li key={r.flag_type} className={`rounded-lg border px-3 py-2 ${SEVERITY_BOX[r.severity] ?? SEVERITY_BOX.info}`}>
                <p className={`text-xs font-semibold ${SEVERITY_TEXT[r.severity] ?? SEVERITY_TEXT.info}`}>{r.title}</p>
                <p className="mt-0.5 text-sm text-slate-700">{r.description}</p>
                <p className="mt-1 text-xs text-slate-600">
                  <span className="font-medium">Do this:</span> {r.recommended_action}
                  {r.deadline ? ` (by ${r.deadline})` : ''}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">No immediate risks flagged for your move right now.</p>
        )}
      </div>
    </Card>
  );
}
