/**
 * Phase 1 Step 6: Lightweight instrumentation for services workflow.
 */

type WorkflowEvent =
  | 'save_answers_started'
  | 'save_answers_succeeded'
  | 'save_answers_skipped'
  | 'save_answers_failed'
  | 'recommendations_started'
  | 'recommendations_succeeded'
  | 'recommendations_failed'
  | 'resolved_destination_context'
  | 'save_preferences_started'
  | 'save_preferences_succeeded'
  | 'save_preferences_skipped_duplicate'
  | 'save_preferences_failed'
  | 'recommendations_load_started'
  | 'recommendations_load_succeeded'
  | 'recommendations_load_failed'
  | 'services_autosave_scheduled'
  | 'services_autosave_cancelled_unmount'
  | 'services_autosave_cancelled_route_change'
  | 'services_autosave_blocked_wrong_route'
  | 'services_autosave_blocked_wrong_state'
  | 'services_save_started'
  | 'services_save_aborted'
  | 'services_save_failed'
  | 'services_save_skipped_duplicate';

export function logServicesWorkflow(event: WorkflowEvent, meta?: Record<string, unknown>) {
  if (process.env.NODE_ENV === 'development' || typeof window !== 'undefined') {
    try {
      console.debug(`[services-workflow] ${event}`, meta ?? {});
    } catch {
      // no-op
    }
  }
}
