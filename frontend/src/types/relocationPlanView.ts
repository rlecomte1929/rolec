/**
 * Canonical relocation plan view — mirrors backend `relocation_plan_view_schemas.py`
 * (GET /api/relocation-plans/{case_id}/view).
 */
export type RelocationPlanViewRole = 'employee' | 'hr';

export type RelocationPlanTaskStatusWire =
  | 'not_started'
  | 'in_progress'
  | 'completed'
  | 'blocked'
  | 'not_applicable';

export type RelocationPlanPhaseStatusWire = 'completed' | 'active' | 'upcoming' | 'blocked';

export type RelocationPlanTaskOwnerWire = 'employee' | 'hr' | 'joint' | 'provider';

export type RelocationPlanTaskPriorityWire = 'standard' | 'critical';

/** Matches backend RelocationPlanCtaType */
export type RelocationPlanCtaTypeWire =
  | 'upload_document'
  | 'open_internal_route'
  | 'open_external_url'
  | 'complete_wizard_step'
  | 'contact_hr'
  | 'open_messages'
  | 'view_details'
  | 'none';

export type RelocationPlanRequiredInputTypeWire =
  | 'document'
  | 'profile_field'
  | 'assignment_field'
  | 'approval'
  | 'other';

export type RelocationPlanAutoCompletionSourceWire =
  | 'document_presence'
  | 'manual'
  | 'evaluation'
  | 'system_rule'
  | 'unspecified';

export interface RelocationPlanSummaryDTO {
  total_tasks: number;
  completed_tasks: number;
  in_progress_tasks: number;
  blocked_tasks: number;
  overdue_tasks: number;
  due_soon_tasks: number;
  completion_ratio: number;
}

export interface RelocationPlanCtaDTO {
  type: RelocationPlanCtaTypeWire;
  label: string;
  target?: string | null;
}

export interface RelocationPlanNextActionDTO {
  task_id: string;
  title: string;
  owner: RelocationPlanTaskOwnerWire;
  status: RelocationPlanTaskStatusWire;
  priority: RelocationPlanTaskPriorityWire;
  due_date?: string | null;
  reason: string;
  cta?: RelocationPlanCtaDTO | null;
  blocking: boolean;
}

export interface RelocationPlanPhaseTaskCountsDTO {
  total: number;
  completed: number;
  in_progress: number;
  blocked: number;
}

export interface RelocationPlanRequiredInputDTO {
  type: RelocationPlanRequiredInputTypeWire;
  key: string;
  label: string;
  present: boolean;
}

export interface RelocationPlanPhaseTaskDTO {
  task_id: string;
  task_code: string;
  title: string;
  short_label?: string | null;
  status: RelocationPlanTaskStatusWire;
  owner: RelocationPlanTaskOwnerWire;
  priority: RelocationPlanTaskPriorityWire;
  due_date?: string | null;
  is_overdue: boolean;
  is_due_soon: boolean;
  blocked_by: string[];
  depends_on: string[];
  why_this_matters?: string | null;
  instructions: string[];
  required_inputs: RelocationPlanRequiredInputDTO[];
  cta?: RelocationPlanCtaDTO | null;
  auto_completion_source: RelocationPlanAutoCompletionSourceWire;
  notes_enabled: boolean;
}

export interface RelocationPlanPhaseDTO {
  phase_key: string;
  title: string;
  status: RelocationPlanPhaseStatusWire;
  completion_ratio: number;
  task_counts: RelocationPlanPhaseTaskCountsDTO;
  tasks: RelocationPlanPhaseTaskDTO[];
}

export interface RelocationPlanDataFreshnessDTO {
  documents_checked_at?: string | null;
  compliance_checked_at?: string | null;
}

export interface RelocationPlanViewResponseDTO {
  case_id: string;
  assignment_id?: string | null;
  role: RelocationPlanViewRole;
  summary: RelocationPlanSummaryDTO;
  next_action?: RelocationPlanNextActionDTO | null;
  phases: RelocationPlanPhaseDTO[];
  last_evaluated_at?: string | null;
  data_freshness?: RelocationPlanDataFreshnessDTO | null;
  empty_state_reason?: string | null;
  debug?: Record<string, unknown> | null;
}
