/**
 * Derivations for the redesigned employee roadmap (template-aligned).
 * Pure functions over the plan-view DTO — no fetching, no React.
 */
import type { LucideIcon } from 'lucide-react';
import { User, Stamp, Package, PlaneTakeoff, Home, MapPin } from 'lucide-react';
import type {
  RelocationPlanPhaseDTO,
  RelocationPlanPhaseTaskDTO,
  RelocationPlanTaskOwnerWire,
} from '../../../types/relocationPlanView';

/** phase_key → hero/section icon (keys come from the backend PHASE_ORDER). */
const PHASE_ICON: Record<string, LucideIcon> = {
  pre_departure: User,
  immigration: Stamp,
  logistics: Package,
  arrival: PlaneTakeoff,
  post_arrival: Home,
  settlement: Home,
};
export function phaseIcon(phaseKey: string): LucideIcon {
  return PHASE_ICON[phaseKey] ?? MapPin;
}

const ACTIONABLE_OWNERS: RelocationPlanTaskOwnerWire[] = ['employee', 'joint'];
const HR_OWNERS: RelocationPlanTaskOwnerWire[] = ['hr', 'provider'];

export function allTasks(phases: RelocationPlanPhaseDTO[]): RelocationPlanPhaseTaskDTO[] {
  return phases.flatMap((p) => p.tasks);
}

/** task_code → short human title, for resolving `blocked_by` codes. */
export function titlesByCode(phases: RelocationPlanPhaseDTO[]): Record<string, string> {
  const m: Record<string, string> = {};
  for (const t of allTasks(phases)) m[t.task_code] = t.short_label || t.title;
  return m;
}

/** A task the employee can act on right now (owned by them, in motion, unblocked). */
export function isActionable(t: RelocationPlanPhaseTaskDTO): boolean {
  return (
    ACTIONABLE_OWNERS.includes(t.owner) &&
    (t.status === 'not_started' || t.status === 'in_progress') &&
    t.blocked_by.length === 0
  );
}

function urgencyRank(t: RelocationPlanPhaseTaskDTO): number {
  // lower = more urgent: overdue → critical → due-soon → in-progress → rest
  if (t.is_overdue) return 0;
  if (t.priority === 'critical') return 1;
  if (t.is_due_soon) return 2;
  if (t.status === 'in_progress') return 3;
  return 4;
}
function dueMs(t: RelocationPlanPhaseTaskDTO): number {
  return t.due_date ? new Date(t.due_date).getTime() : Number.MAX_SAFE_INTEGER;
}

export function actionableTasks(
  phases: RelocationPlanPhaseDTO[],
  limit = 3,
): RelocationPlanPhaseTaskDTO[] {
  return allTasks(phases)
    .filter(isActionable)
    .sort((a, b) => urgencyRank(a) - urgencyRank(b) || dueMs(a) - dueMs(b))
    .slice(0, limit);
}

/** Tasks HR / partners are carrying for the employee (in motion or queued, not done). */
export function hrHandledTasks(phases: RelocationPlanPhaseDTO[]): RelocationPlanPhaseTaskDTO[] {
  return allTasks(phases).filter(
    (t) => HR_OWNERS.includes(t.owner) && t.status !== 'completed' && t.status !== 'not_applicable',
  );
}

export function resolveBlockedBy(
  t: RelocationPlanPhaseTaskDTO,
  titles: Record<string, string>,
): string {
  const names = t.blocked_by.map((c) => titles[c]).filter(Boolean);
  return names.join(', ');
}

export type RowTone = 'done' | 'progress' | 'ready' | 'wait' | 'muted';

export function rowStatus(t: RelocationPlanPhaseTaskDTO): { label: string; tone: RowTone } {
  if (t.status === 'completed') return { label: 'Completed', tone: 'done' };
  if (t.status === 'not_applicable') return { label: 'Not applicable', tone: 'muted' };
  if (t.status === 'blocked' || (t.blocked_by.length > 0 && t.status !== 'in_progress')) {
    return { label: 'Waiting', tone: 'wait' };
  }
  if (t.status === 'in_progress') return { label: 'In progress', tone: 'progress' };
  // not_started, unblocked
  if (t.owner === 'employee' || t.owner === 'joint') return { label: 'Ready for you', tone: 'ready' };
  return { label: 'In progress', tone: 'progress' }; // HR / partner queue
}

export function formatDue(t: RelocationPlanPhaseTaskDTO): string {
  if (!t.due_date) return 'No date set';
  const d = new Date(t.due_date);
  const abs = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  // [AIQ-1340] An estimated date reads as "Suggested · <date>" — never "Overdue"
  // or a "Due in N days" countdown, which would imply a committed deadline.
  if (t.due_date_is_suggested) return `Suggested · ${abs}`;
  if (t.is_overdue) return 'Overdue';
  const days = Math.ceil((d.getTime() - Date.now()) / 86_400_000);
  if (days >= 0 && days <= 7) return days === 0 ? 'Due today' : `Due in ${days} day${days === 1 ? '' : 's'}`;
  return `Due ${abs}`;
}

export function docCount(t: RelocationPlanPhaseTaskDTO): { present: number; total: number } | null {
  const docs = t.required_inputs.filter((r) => r.type === 'document');
  if (!docs.length) return null;
  return { present: docs.filter((r) => r.present).length, total: docs.length };
}

export function daysUntil(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const days = Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000);
  return Number.isNaN(days) ? null : days;
}
