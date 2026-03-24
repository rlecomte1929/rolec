import type { RelocationPlanTaskOwnerWire, RelocationPlanTaskStatusWire } from '../../types/relocationPlanView';

export function ownerLabel(owner: RelocationPlanTaskOwnerWire): string {
  switch (owner) {
    case 'employee':
      return 'You';
    case 'hr':
      return 'HR';
    case 'joint':
      return 'You & HR';
    case 'provider':
      return 'Provider';
    default:
      return owner;
  }
}

export function taskStatusLabel(status: RelocationPlanTaskStatusWire): string {
  switch (status) {
    case 'not_started':
      return 'Not started';
    case 'in_progress':
      return 'In progress';
    case 'completed':
      return 'Done';
    case 'blocked':
      return 'Blocked';
    case 'not_applicable':
      return 'N/A';
    default:
      return status;
  }
}

export { relocationPhaseStatusLabel as phaseStatusLabel } from '../relocation-plan/phase-timeline/relocationPhaseStatusUtils';
