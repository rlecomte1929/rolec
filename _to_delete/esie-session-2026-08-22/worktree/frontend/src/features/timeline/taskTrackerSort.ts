import type { TimelineMilestone } from '../../api/client';

export type UrgencyLevel = 'red' | 'orange' | 'green' | 'neutral';

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

/** Parse YYYY-MM-DD to local date (noon to avoid TZ drift). */
export function parseYmd(d?: string | null): Date | null {
  if (!d || typeof d !== 'string' || d.length < 10) return null;
  const x = new Date(`${d.slice(0, 10)}T12:00:00`);
  return Number.isNaN(x.getTime()) ? null : x;
}

export function getTaskUrgency(m: TimelineMilestone, today: Date = new Date()): UrgencyLevel {
  const st = (m.status || 'pending').toLowerCase();
  if (st === 'done' || st === 'skipped') return 'green';
  const td = parseYmd(m.target_date);
  const t0 = startOfDay(today);
  if (td) {
    const d0 = startOfDay(td);
    if (d0 < t0) return 'red';
    if ((d0 - t0) / 86400000 <= 7) return 'orange';
  }
  if (st === 'blocked') return 'orange';
  if (st === 'in_progress') return 'orange';
  return 'neutral';
}

/**
 * Priority bucket for default ordering:
 * 0 overdue, 1 due this week, 2 blocked, 3 in progress, 4 upcoming, 5 completed.
 */
export function taskPriorityBucket(m: TimelineMilestone, today: Date = new Date()): number {
  const st = (m.status || 'pending').toLowerCase();
  if (st === 'done' || st === 'skipped') return 5;
  const td = parseYmd(m.target_date);
  const t0 = startOfDay(today);
  if (td && startOfDay(td) < t0) return 0;
  if (td && (startOfDay(td) - t0) / 86400000 <= 7) return 1;
  if (st === 'blocked') return 2;
  if (st === 'in_progress') return 3;
  return 4;
}

export function sortTasksForTracker(list: TimelineMilestone[], today: Date = new Date()): TimelineMilestone[] {
  return [...list].sort((a, b) => {
    const ba = taskPriorityBucket(a, today);
    const bb = taskPriorityBucket(b, today);
    if (ba !== bb) return ba - bb;
    const ad = parseYmd(a.target_date);
    const bd = parseYmd(b.target_date);
    const at = ad ? startOfDay(ad) : Infinity;
    const bt = bd ? startOfDay(bd) : Infinity;
    if (ba === 5) {
      if (at !== bt) return bt - at;
    } else {
      if (at !== bt) return at - bt;
    }
    const so = (a.sort_order ?? 0) - (b.sort_order ?? 0);
    if (so !== 0) return so;
    return a.id.localeCompare(b.id);
  });
}
