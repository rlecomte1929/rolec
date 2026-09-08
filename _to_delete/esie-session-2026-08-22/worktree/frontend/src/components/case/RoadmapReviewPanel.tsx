/**
 * RoadmapReviewPanel — [AIQ-1525] HR approves the roadmap before the employee acts on it.
 *
 * The intended order is:
 *   intake -> roadmap generated -> HR approves -> employee acknowledges -> tasks start
 *
 * Until HR approves, the employee sees "Your HR team is reviewing your plan" instead of
 * the roadmap (EmployeeCaseRoadmapPage + roadmapReleaseGate.ts). This panel is where HR
 * makes that call.
 *
 *   GET  /api/hr/cases/:caseId/roadmap-review
 *   POST /api/hr/cases/:caseId/roadmap-review/approve
 *   POST /api/hr/cases/:caseId/roadmap-review/request-changes   (a reason is required)
 *
 * `reviewed: false` (no decision ever recorded) is deliberately NOT rendered as
 * "approved", even though such a roadmap IS visible to the employee — the backend fails
 * open so that the 47 cases predating this gate didn't lose their plans. Showing that as
 * "You approved this" would be a lie about who decided what. It reads "Not yet reviewed —
 * visible to the employee", which is exactly what is true.
 */
import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiPost } from '../../api/client';
import { Alert, Badge, Button, Card } from '../antigravity';

interface RoadmapReview {
  case_id: string;
  released_to_user: boolean;
  regeneration_requested: boolean;
  reviewer_id?: string | null;
  notes?: string | null;
  /** False when no HR decision has ever been recorded for this case. */
  reviewed: boolean;
}

export const RoadmapReviewPanel: React.FC<{ caseId: string }> = ({ caseId }) => {
  const qc = useQueryClient();
  const [notes, setNotes] = useState('');
  const [showNotes, setShowNotes] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const key = ['roadmap-review', caseId];
  const { data, isLoading } = useQuery({
    queryKey: key,
    queryFn: () => apiGet<RoadmapReview>(`/api/hr/cases/${caseId}/roadmap-review`),
    enabled: !!caseId,
  });

  const settle = (res: RoadmapReview) => {
    qc.setQueryData(key, res);
    setShowNotes(false);
    setNotes('');
    setError(null);
  };

  const approve = useMutation({
    mutationFn: () => apiPost<RoadmapReview>(`/api/hr/cases/${caseId}/roadmap-review/approve`),
    onSuccess: settle,
    onError: () => setError('Could not approve the roadmap. Please try again.'),
  });

  const requestChanges = useMutation({
    mutationFn: () =>
      apiPost<RoadmapReview>(`/api/hr/cases/${caseId}/roadmap-review/request-changes`, { notes }),
    onSuccess: settle,
    onError: () => setError('Could not send the roadmap back. Please try again.'),
  });

  if (isLoading || !data) return null;

  const busy = approve.isPending || requestChanges.isPending;
  const released = data.released_to_user;

  return (
    <Card padding="lg">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[#0b2b43]">
            Roadmap review
          </h2>
          <p className="mt-1 text-sm text-[#475569]">
            {released
              ? 'The employee can see this roadmap and start their tasks.'
              : 'The employee sees “Your HR team is reviewing your plan”. They cannot start tasks until you approve.'}
          </p>
        </div>
        {/* Three states, not two. "Not yet reviewed" is visible to the employee but nobody
            has signed off — say that rather than claiming an approval that never happened. */}
        {released && data.reviewed ? (
          <Badge variant="success">Approved</Badge>
        ) : released ? (
          <Badge variant="neutral">Not yet reviewed</Badge>
        ) : (
          <Badge variant="warning">Changes requested</Badge>
        )}
      </div>

      {data.regeneration_requested && data.notes && (
        <Alert variant="warning" className="mt-4">
          <span className="font-semibold">You sent this back:</span> {data.notes}
          <div className="mt-1 text-xs text-[#64748b]">
            Only your team sees this note — the employee is told their plan is under review,
            not why.
          </div>
        </Alert>
      )}

      {error && (
        <Alert variant="error" className="mt-4">
          {error}
        </Alert>
      )}

      {showNotes && (
        <div className="mt-4">
          <label
            htmlFor="roadmap-review-notes"
            className="block text-sm font-medium text-[#0b2b43]"
          >
            What needs to change?
          </label>
          <textarea
            id="roadmap-review-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="mt-1 w-full rounded-lg border border-[#cbd5e1] px-3 py-2 text-sm"
            placeholder="e.g. Housing budget is wrong for this grade — regenerate with the updated policy."
          />
          <p className="mt-1 text-xs text-[#64748b]">
            Required. A rejection with no reason leaves the plan stuck with nobody able to act
            on it.
          </p>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        {!released || !data.reviewed ? (
          <Button
            variant="primary"
            disabled={busy}
            onClick={() => approve.mutate()}
          >
            {approve.isPending ? 'Approving…' : 'Approve & release to employee'}
          </Button>
        ) : null}

        {showNotes ? (
          <>
            <Button
              variant="secondary"
              disabled={busy || !notes.trim()}
              onClick={() => requestChanges.mutate()}
            >
              {requestChanges.isPending ? 'Sending…' : 'Send back'}
            </Button>
            <Button variant="ghost" disabled={busy} onClick={() => setShowNotes(false)}>
              Cancel
            </Button>
          </>
        ) : (
          <Button variant="secondary" disabled={busy} onClick={() => setShowNotes(true)}>
            Request changes
          </Button>
        )}
      </div>
    </Card>
  );
};
