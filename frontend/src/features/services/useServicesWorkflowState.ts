/**
 * Phase 1 Step 6: Explicit services workflow state machine.
 * Ensures deterministic flow: edit → save → load → navigate.
 */
import { useCallback, useState } from 'react';

export type ServicesWorkflowState =
  | 'idle'
  | 'editing'
  | 'saving_answers'
  | 'answers_saved'
  | 'loading_recommendations'
  | 'recommendations_ready'
  | 'error';

export type ServicesWorkflowResult =
  | 'saved'
  | 'skipped_duplicate'
  | 'failed';

export function useServicesWorkflowState() {
  const [state, setState] = useState<ServicesWorkflowState>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const transitionTo = useCallback((next: ServicesWorkflowState, error?: string) => {
    setState(next);
    setErrorMessage(error ?? null);
  }, []);

  const toEditing = useCallback(() => transitionTo('editing'), [transitionTo]);
  const toSavingAnswers = useCallback(() => transitionTo('saving_answers'), [transitionTo]);
  const toAnswersSaved = useCallback(() => transitionTo('answers_saved'), [transitionTo]);
  const toLoadingRecommendations = useCallback(() => transitionTo('loading_recommendations'), [transitionTo]);
  const toRecommendationsReady = useCallback(() => transitionTo('recommendations_ready'), [transitionTo]);
  const toError = useCallback((msg: string) => transitionTo('error', msg), [transitionTo]);
  const clearError = useCallback(() => transitionTo('editing'), [transitionTo]);

  const isBusy =
    state === 'saving_answers' ||
    state === 'loading_recommendations';

  const canProceed = !isBusy && state !== 'error';

  return {
    state,
    errorMessage,
    transitionTo,
    toEditing,
    toSavingAnswers,
    toAnswersSaved,
    toLoadingRecommendations,
    toRecommendationsReady,
    toError,
    clearError,
    isBusy,
    canProceed,
  };
}
