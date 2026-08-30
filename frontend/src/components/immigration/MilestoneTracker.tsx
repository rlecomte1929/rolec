/**
 * MilestoneTracker — IMM-14
 *
 * Vertical timeline of immigration milestones for a case, calculated from the
 * case's move date. Each milestone shows its label, a calculated target date, a
 * status, and a days-until / overdue indicator. HR can mark milestones complete
 * (persisted via the immigration_milestones API). Corridors flagged for early
 * booking (e.g. IN→DE) show a prominent alert.
 *
 * Pure Tailwind — no external timeline library.
 */

import React, { useCallback, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button } from '../antigravity/Button';
import { hrAPI } from '../../api/client';
import {
  MILESTONE_DEFS,
  BOOK_EARLY_ALERTS,
  computeMilestoneTargets,
  diffDaysISO,
  formatISODate,
  todayISODate,
  type MilestoneDef,
} from './milestoneTimeline';

interface MilestoneTrackerProps {
  caseId: string;
  /** ISO date (case expected start / move date). Null → timeline can't be drawn. */
  moveDate?: string | null;
  corridorFrom?: string | null;
  corridorTo?: string | null;
}

interface ApiMilestone {
  id: string;
  milestone_type: string;
  status: string;
  sort_order: number;
  target_date: string | null;
  completed_date: string | null;
  notes: string | null;
  evidence_url: string | null;
  book_early_alert: string | null;
}

export const MilestoneTracker: React.FC<MilestoneTrackerProps> = ({
  caseId,
  moveDate,
  corridorFrom,
  corridorTo,
}) => {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [savingType, setSavingType] = useState<string | null>(null);

  const milestonesQuery = useQuery({
    queryKey: ['immigration-milestones', caseId],
    queryFn: async () => {
      const resp = await hrAPI.listImmigrationMilestones(caseId);
      return resp.milestones || [];
    },
  });
  const apiMilestones = milestonesQuery.data ?? [];
  const loading = milestonesQuery.isLoading;
  // The mark-done mutation below also writes `error`; surface a load failure alongside it.
  const displayedError = error || (milestonesQuery.isError ? 'Failed to load milestones.' : null);

  const moveDateISO = useMemo(() => {
    if (!moveDate) return null;
    const d = new Date(moveDate);
    if (Number.isNaN(d.getTime())) return null;
    return moveDate.slice(0, 10);
  }, [moveDate]);

  const targetsByType = useMemo(() => {
    if (!moveDateISO) return {};
    return Object.fromEntries(
      computeMilestoneTargets(moveDateISO).map((t) => [t.type, t.targetISO]),
    );
  }, [moveDateISO]);

  const bookEarlyMessage = corridorFrom && corridorTo
    ? BOOK_EARLY_ALERTS[`${corridorFrom}>${corridorTo}`]
    : undefined;

  const byType = useMemo(() => {
    const m: Record<string, ApiMilestone> = {};
    for (const ms of apiMilestones) m[ms.milestone_type] = ms;
    return m;
  }, [apiMilestones]);

  const handleMarkDone = useCallback(
    async (def: MilestoneDef, persisted: ApiMilestone | undefined, computedISO: string | null) => {
      setSavingType(def.type);
      setError(null);
      const today = new Date().toISOString().slice(0, 10);
      try {
        let milestoneId = persisted?.id;
        if (!milestoneId) {
          const created = await hrAPI.createImmigrationMilestone(caseId, {
            milestone_type: def.type,
            target_date: computedISO,
            sort_order: MILESTONE_DEFS.findIndex((d) => d.type === def.type),
            book_early_alert: bookEarlyMessage ?? null,
          });
          milestoneId = created.id;
        }
        await hrAPI.updateImmigrationMilestone(caseId, milestoneId, {
          status: 'completed',
          completed_date: today,
        });
        await queryClient.invalidateQueries({ queryKey: ['immigration-milestones', caseId] });
      } catch {
        setError('Could not update the milestone. Please try again.');
      } finally {
        setSavingType(null);
      }
    },
    [caseId, bookEarlyMessage, queryClient],
  );

  // ── Render ────────────────────────────────────────────────────────────────

  if (!moveDateISO) {
    return (
      <section>
        <SectionHeading />
        {bookEarlyMessage && <BookEarlyAlert message={bookEarlyMessage} />}
        <div className="rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-4 py-6 text-center">
          <p className="text-sm font-medium text-[#64748b]">Set a move date to see your timeline</p>
          <p className="mt-1 text-xs text-slate-500">
            Milestone deadlines are calculated from the case&apos;s expected move date.
          </p>
        </div>
      </section>
    );
  }

  const todayISO = todayISODate();

  return (
    <section>
      <SectionHeading />
      {bookEarlyMessage && <BookEarlyAlert message={bookEarlyMessage} />}

      {loading && (
        <div className="py-4 text-center text-sm text-slate-500">Loading milestones…</div>
      )}
      {displayedError && (
        <div className="mb-3 rounded-lg border border-[#fecaca] bg-[#fff5f5] px-3 py-2 text-xs text-[#b91c1c]">
          {displayedError}
        </div>
      )}

      {!loading && (
        <ol className="relative">
          {MILESTONE_DEFS.map((def, idx) => {
            const persisted = byType[def.type];
            // targetsByType is built from these same MILESTONE_DEFS and moveDateISO is set (early return above), so every def.type has a target
            const computedISO = targetsByType[def.type]!;
            const targetISO = persisted?.target_date
              ? persisted.target_date.slice(0, 10)
              : computedISO;
            const completed = persisted?.status === 'completed';
            const diff = diffDaysISO(targetISO, todayISO); // target - today
            const overdue = !completed && diff < 0;
            const isLast = idx === MILESTONE_DEFS.length - 1;

            const dotClass = completed
              ? 'bg-[#22c55e] border-[#22c55e]'
              : overdue
                ? 'bg-[#ef4444] border-[#ef4444]'
                : 'bg-white border-[#cbd5e1]';

            return (
              <li key={def.type} className="relative flex gap-3 pb-5 last:pb-0">
                {/* connector line */}
                {!isLast && (
                  <span
                    aria-hidden="true"
                    className="absolute left-[7px] top-4 h-full w-px bg-[#e2e8f0]"
                  />
                )}
                {/* dot */}
                <span
                  aria-hidden="true"
                  className={`relative z-10 mt-1 h-4 w-4 shrink-0 rounded-full border-2 ${dotClass}`}
                />

                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-[#0b2b43] leading-snug">
                        {def.label}
                        {def.conditional && (
                          <span className="ml-2 rounded-full bg-[#f1f5f9] px-1.5 py-0.5 text-[10px] font-normal text-[#64748b]">
                            If applicable
                          </span>
                        )}
                      </p>
                      <p className="mt-0.5 text-xs text-[#64748b]">
                        Target: {formatISODate(targetISO)}
                      </p>
                      {def.note && (
                        <p className="mt-0.5 text-xs text-slate-500">{def.note}</p>
                      )}
                    </div>

                    <div className="shrink-0 text-right">
                      {completed ? (
                        <span className="inline-flex items-center rounded-full bg-[#f0fdf4] border border-[#bbf7d0] px-2 py-0.5 text-xs font-medium text-[#15803d]">
                          Completed
                        </span>
                      ) : overdue ? (
                        <span className="inline-flex items-center rounded-full bg-[#fee2e2] border border-[#fecaca] px-2 py-0.5 text-xs font-medium text-[#b91c1c]">
                          {Math.abs(diff)} day{Math.abs(diff) === 1 ? '' : 's'} overdue
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full bg-[#f8fafc] border border-[#e2e8f0] px-2 py-0.5 text-xs font-medium text-[#64748b]">
                          {diff === 0 ? 'Today' : `in ${diff} day${diff === 1 ? '' : 's'}`}
                        </span>
                      )}
                    </div>
                  </div>

                  {!completed && (
                    <Button unstyled
                      type="button"
                      onClick={() => void handleMarkDone(def, persisted, computedISO)}
                      disabled={savingType === def.type}
                      className="mt-1.5 rounded-lg border border-[#e2e8f0] bg-white px-2.5 py-1 text-xs font-medium text-[#374151] hover:bg-[#f8fafc] transition-colors disabled:opacity-50"
                    >
                      {savingType === def.type ? 'Saving…' : 'Mark as done'}
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
};

const SectionHeading: React.FC = () => (
  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">
    Application timeline
  </div>
);

const BookEarlyAlert: React.FC<{ message: string }> = ({ message }) => (
  <div className="mb-4 rounded-lg border border-[#fde68a] bg-[#fffbeb] px-4 py-3">
    <div className="flex items-start gap-2">
      <svg className="mt-0.5 h-4 w-4 shrink-0 text-[#92400e]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M12 9v2m0 4h.01M5 19h14a2 2 0 001.84-2.75L13.74 4a2 2 0 00-3.48 0L3.16 16.25A2 2 0 005 19z" />
      </svg>
      <div>
        <p className="text-sm font-semibold text-[#92400e]">Book early</p>
        <p className="mt-0.5 text-xs text-[#92400e]">{message}</p>
      </div>
    </div>
  </div>
);

export default MilestoneTracker;
