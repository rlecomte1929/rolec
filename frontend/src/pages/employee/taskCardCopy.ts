/**
 * Plain-English guidance for the employee Tasks list (BUG-260909-73EA).
 *
 * The wire already carries description, due dates, effort, and requirement
 * provenance (`source_url` / excerpt). These helpers only format that payload —
 * they do not invent citations or legal deadlines.
 */
import type { TaskType } from '../../api/client';
import type { RoadmapV2Step } from '../../api/roadmapV2';

const HR_EXPECTED: Record<TaskType, string> = {
  document_upload:
    'Upload the document your HR team asked for. Add a note if anything is missing or delayed.',
  address_confirmation:
    'Confirm the address your HR team needs so they can finish paperwork that depends on it.',
  acknowledgment:
    'Read the request and confirm you understand. Add a note if you have questions.',
  selection: 'Choose the option your HR team asked for and submit your choice.',
  custom: 'Complete the action your HR team described and submit when you are done.',
};

export type TimelineKind = 'due' | 'suggested' | 'effort' | 'open';

export interface TimelineLine {
  kind: TimelineKind;
  text: string;
}

export function formatAbsoluteDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export function hrWhatsExpected(
  taskType: TaskType,
  description: string | null | undefined,
): { instruction: string; detail: string | null } {
  const instruction = HR_EXPECTED[taskType] ?? HR_EXPECTED.custom;
  const detail = description?.trim() || null;
  return { instruction, detail };
}

export function hrTaskTimeline(dueDate: string | null | undefined): TimelineLine[] {
  if (!dueDate) {
    return [
      {
        kind: 'open',
        text: 'No due date yet — complete this as soon as you can so your move stays on track.',
      },
    ];
  }
  const abs = formatAbsoluteDate(dueDate);
  const days = Math.ceil((new Date(dueDate).getTime() - Date.now()) / 86_400_000);
  if (Number.isNaN(days)) {
    return [{ kind: 'due', text: `Complete by ${abs}.` }];
  }
  if (days < 0) {
    const n = Math.abs(days);
    return [
      {
        kind: 'due',
        text: `Complete by ${abs} (${n} day${n === 1 ? '' : 's'} overdue).`,
      },
    ];
  }
  if (days === 0) return [{ kind: 'due', text: `Complete by ${abs} (today).` }];
  if (days === 1) return [{ kind: 'due', text: `Complete by ${abs} (tomorrow).` }];
  if (days <= 14) {
    return [{ kind: 'due', text: `Complete by ${abs} (${days} days left).` }];
  }
  return [{ kind: 'due', text: `Complete by ${abs}.` }];
}

export function roadmapWhatsExpected(
  step: Pick<RoadmapV2Step, 'description' | 'ai_suggestion'>,
): { instruction: string; howTo: string | null } {
  const instruction =
    step.description?.trim() ||
    'Complete this step for your move. Follow the official source below when one is listed — that is what this requirement is based on.';
  const howTo = step.ai_suggestion?.trim() || null;
  return { instruction, howTo };
}

export function roadmapTaskTimeline(
  step: Pick<RoadmapV2Step, 'due_date' | 'due_date_is_suggested' | 'estimated_effort'>,
): TimelineLine[] {
  const lines: TimelineLine[] = [];
  if (step.due_date) {
    const abs = formatAbsoluteDate(step.due_date);
    if (step.due_date_is_suggested) {
      lines.push({
        kind: 'suggested',
        text: `Suggested by ${abs} (based on your move date, not a legal deadline).`,
      });
    } else {
      lines.push({ kind: 'due', text: `Complete by ${abs}.` });
    }
  }
  if (step.estimated_effort?.trim()) {
    lines.push({
      kind: 'effort',
      text: `Typical time to complete: ${step.estimated_effort.trim()}.`,
    });
  }
  if (lines.length === 0) {
    lines.push({
      kind: 'open',
      text: 'No date on this step yet — start as soon as you can, and check the official source for any legal deadline.',
    });
  }
  return lines;
}

export function sourceHostLabel(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}
