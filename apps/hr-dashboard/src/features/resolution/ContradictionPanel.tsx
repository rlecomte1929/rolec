import { useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { cn } from '../../lib/utils';
import {
  useCorrectionHistoryQuery,
  useResolveContradictionMutation,
} from '../../hooks/useContradictionsQuery';
import { CandidateCard } from './CandidateCard';
import { ReasonCodeForm } from './ReasonCodeForm';
import { CorrectionHistory } from './CorrectionHistory';
import { reasonRequiresFreetext, type ReasonCode } from './reasonCodes';
import type { Contradiction, ResolvePayload } from './types';

interface ContradictionPanelProps {
  caseId: string;
  contradiction: Contradiction;
  /**
   * Called after a successful resolve so the parent can advance to the
   * next pending contradiction.
   */
  onResolved?: (contradictionId: string) => void;
}

const TYPE_LABELS: Record<Contradiction['type'], string> = {
  DIRECT_CONTRADICTION: 'Direct disagreement between sources',
  MISSING_VALUE: 'Missing value in one source',
  TEMPORAL_INCONSISTENCY: 'Temporal inconsistency',
  FORMAT_MISMATCH: 'Format / unit mismatch',
  UNIT_MISMATCH: 'Unit mismatch',
};

/**
 * The full Resolution UI for one Contradiction row.
 *
 * Layout per the brief:
 *   header (field + entity + type)
 *   2-up CandidateCard side-by-side
 *   ReasonCodeForm (dropdown + freetext-if-OTHER)
 *   Resolve / Escalate buttons
 *   CorrectionHistory at the bottom
 */
export function ContradictionPanel({
  caseId,
  contradiction,
  onResolved,
}: ContradictionPanelProps): JSX.Element {
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [reasonCode, setReasonCode] = useState<ReasonCode | ''>('');
  const [reasonFreetext, setReasonFreetext] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const history = useCorrectionHistoryQuery(caseId, contradiction.contradiction_id);
  const resolve = useResolveContradictionMutation(caseId);

  const validate = (): string | null => {
    if (!selectedCandidateId) {
      return 'Pick a winning candidate before resolving.';
    }
    if (!reasonCode) {
      return 'Choose a reason code.';
    }
    if (reasonRequiresFreetext(reasonCode) && reasonFreetext.trim().length === 0) {
      return 'OTHER requires an explanation in the free-text field.';
    }
    return null;
  };

  const handleResolve = async (): Promise<void> => {
    const err = validate();
    if (err) {
      setFormError(err);
      return;
    }
    setFormError(null);
    const payload: ResolvePayload = {
      winner_candidate_id: selectedCandidateId as string,
      reason_code: reasonCode as ReasonCode,
      ...(reasonRequiresFreetext(reasonCode as ReasonCode)
        ? { reason_freetext: reasonFreetext.trim() }
        : {}),
    };
    try {
      await resolve.mutateAsync({
        contradictionId: contradiction.contradiction_id,
        payload,
      });
      onResolved?.(contradiction.contradiction_id);
      // Reset so the next contradiction starts clean.
      setSelectedCandidateId(null);
      setReasonCode('');
      setReasonFreetext('');
    } catch (e) {
      setFormError(
        e instanceof Error ? e.message : 'Resolve failed. Try again or escalate.',
      );
    }
  };

  // Cohort 1 contradictions always have exactly 2 candidates (per §3.6).
  // We render however many show up to stay forward-compatible.
  const candidates = contradiction.candidates;

  return (
    <article
      aria-labelledby="contradiction-title"
      className="flex flex-col gap-6"
    >
      <header className="flex flex-col gap-1 rounded-lg border border-border bg-card p-4 shadow-sm">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {TYPE_LABELS[contradiction.type] ?? contradiction.type}
        </p>
        <h2 id="contradiction-title" className="text-xl font-semibold text-foreground">
          {contradiction.field_key.replace(/_/g, ' ')}
        </h2>
        {contradiction.canonical_entity_label ? (
          <p className="text-sm text-muted-foreground">
            for {contradiction.canonical_entity_label}
          </p>
        ) : contradiction.canonical_entity_id ? (
          <p className="font-mono text-xs text-muted-foreground">
            entity {contradiction.canonical_entity_id.slice(0, 8)}…
          </p>
        ) : null}
      </header>

      <div
        className={cn(
          'grid gap-4',
          candidates.length === 2 ? 'md:grid-cols-2' : 'md:grid-cols-3',
        )}
      >
        {candidates.map((candidate) => (
          <CandidateCard
            key={candidate.candidate_id}
            candidate={candidate}
            isSelected={selectedCandidateId === candidate.candidate_id}
            onSelect={() => setSelectedCandidateId(candidate.candidate_id)}
            disabled={resolve.isPending}
          />
        ))}
      </div>

      <ReasonCodeForm
        reasonCode={reasonCode}
        reasonFreetext={reasonFreetext}
        onChangeReasonCode={setReasonCode}
        onChangeReasonFreetext={setReasonFreetext}
        disabled={resolve.isPending}
        errorMessage={formError ?? undefined}
      />

      <div className="flex flex-wrap items-center justify-end gap-2">
        <button
          type="button"
          className={cn(
            'inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm font-medium',
            'text-warning hover:bg-warning/10',
            'focus-visible:shadow-focus',
          )}
          // Escalation wiring lands with the audit-log endpoint (C1-16).
          disabled
          title="Escalation queue ships with C1-16 audit endpoint."
        >
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          Escalate (C1-16)
        </button>
        <button
          type="button"
          onClick={() => {
            void handleResolve();
          }}
          disabled={resolve.isPending}
          className={cn(
            'inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
            'shadow-sm hover:opacity-90 focus-visible:shadow-focus',
            resolve.isPending && 'opacity-60',
          )}
        >
          {resolve.isPending ? 'Resolving…' : 'Resolve'}
        </button>
      </div>

      <CorrectionHistory
        corrections={history.data ?? []}
        isLoading={history.isLoading}
      />
    </article>
  );
}
