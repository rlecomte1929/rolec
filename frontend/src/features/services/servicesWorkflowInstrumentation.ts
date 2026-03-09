/**
 * Phase 1 Step 6: Lightweight instrumentation for services workflow.
 */

type WorkflowEvent =
  | 'save_preferences_started'
  | 'save_preferences_succeeded'
  | 'save_preferences_skipped_duplicate'
  | 'save_preferences_failed'
  | 'recommendations_load_started'
  | 'recommendations_load_succeeded'
  | 'recommendations_load_failed';

export function logServicesWorkflow(event: WorkflowEvent, meta?: Record<string, unknown>) {
  if (process.env.NODE_ENV === 'development' || typeof window !== 'undefined') {
    try {
      console.debug(`[services-workflow] ${event}`, meta ?? {});
    } catch {
      // no-op
    }
  }
}
