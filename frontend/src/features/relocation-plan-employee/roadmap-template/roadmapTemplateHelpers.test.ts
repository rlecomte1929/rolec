import { describe, it, expect } from 'vitest';
import type { RelocationPlanPhaseTaskDTO } from '../../../types/relocationPlanView';
import { formatDue, phaseIcon } from './roadmapTemplateHelpers';
import { Undo2, MapPin } from 'lucide-react';

function task(p: Partial<RelocationPlanPhaseTaskDTO>): RelocationPlanPhaseTaskDTO {
  return {
    task_id: 't',
    task_code: 't',
    title: 'T',
    status: 'not_started',
    owner: 'employee',
    priority: 'standard',
    is_overdue: false,
    is_due_soon: false,
    blocked_by: [],
    depends_on: [],
    instructions: [],
    required_inputs: [],
    auto_completion_source: 'manual',
    notes_enabled: true,
    ...p,
  };
}

describe('formatDue (AIQ-1340 suggested dates)', () => {
  it('returns "No date set" only when truly undated', () => {
    expect(formatDue(task({ due_date: null }))).toBe('No date set');
  });

  it('labels a suggested date "Suggested · …" and never "Overdue"/countdown', () => {
    const s = formatDue(task({ due_date: '2026-09-03', due_date_is_suggested: true, is_overdue: true }));
    expect(s).toMatch(/^Suggested · /);
    expect(s).not.toMatch(/Overdue|Due in/);
  });

  it('keeps "Overdue" for a real (non-suggested) overdue deadline', () => {
    expect(formatDue(task({ due_date: '2020-01-01', is_overdue: true }))).toBe('Overdue');
  });

  it('shows a plain "Due …" for a real future deadline, not "Suggested"', () => {
    const s = formatDue(task({ due_date: '2099-12-31', due_date_is_suggested: false }));
    expect(s).not.toMatch(/Suggested/);
    expect(s).toMatch(/^Due /);
  });
});

describe('phaseIcon', () => {
  it('uses Undo2 for the return phase', () => {
    expect(phaseIcon('return')).toBe(Undo2);
  });

  it('falls back to MapPin for an unknown phase', () => {
    expect(phaseIcon('not-a-phase')).toBe(MapPin);
  });
});
