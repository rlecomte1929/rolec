/**
 * Admin specialist-review page (AIQ-633).
 *
 * Route: /admin/specialist-review/:case_id
 * Guard: RequireAdminRoute
 *
 * Lists all AI-generated roadmap steps for a case, each rendered with
 * <RoadmapStepDiff>. The admin can approve / reject / edit each step
 * individually, then submit an overall approve or reject decision.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Alert, Button, Card } from '../../components/antigravity';
import {
  RoadmapStepDiff,
  type AiStep,
  type StepReviewValue,
} from '../../features/admin/specialist-review/RoadmapStepDiff';
import { specialistReviewAPI } from '../../api/client';
import { AdminLayout } from './AdminLayout';

export function AdminSpecialistReviewPage() {
  const { case_id: caseId } = useParams<{ case_id: string }>();
  const [steps, setSteps] = useState<AiStep[]>([]);
  const [decisions, setDecisions] = useState<Record<string, StepReviewValue>>({});
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await specialistReviewAPI.getRoadmap(caseId);
      setSteps(res.steps);
      setDecisions(
        Object.fromEntries(res.steps.map((s) => [s.step_id, { decision: 'approve' as const }])),
      );
    } catch {
      setError('Failed to load roadmap.');
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  const allApproved = useMemo(
    () =>
      steps.length > 0 &&
      steps.every((s) => decisions[s.step_id]?.decision === 'approve'),
    [steps, decisions],
  );

  const submit = async (decision: 'approved' | 'rejected') => {
    if (!caseId) return;
    setSaving(true);
    setError(null);
    try {
      const items = steps.map((s) => {
        const d = decisions[s.step_id] ?? { decision: 'approve' as const };
        return {
          step_id: s.step_id,
          decision: d.decision,
          reason_code: d.reason_code,
          original_step: s,
          edited_step: d.edited,
        };
      });
      const res = await specialistReviewAPI.submit(caseId, { decision, notes, items });
      setDone(
        res.released_to_user
          ? 'Roadmap released to user.'
          : 'Submitted; re-generation requested.',
      );
    } catch {
      setError('Submit failed.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <AdminLayout title="Specialist review" subtitle={`Case ${caseId ?? ''}`}>
      {error && (
        <Alert variant="error" title="Error" className="mb-4">
          {error}
        </Alert>
      )}
      {done && (
        <Alert variant="success" title="Done" className="mb-4">
          {done}
        </Alert>
      )}
      {loading ? (
        <Card padding="lg">Loading roadmap…</Card>
      ) : (
        <div className="space-y-4">
          {steps.map((s) => (
            <RoadmapStepDiff
              key={s.step_id}
              step={s}
              value={decisions[s.step_id] ?? { decision: 'approve' }}
              onChange={(next) =>
                setDecisions((d) => ({ ...d, [s.step_id]: next }))
              }
            />
          ))}
          <Card padding="lg">
            <label
              className="mb-2 block text-sm opacity-80"
              htmlFor="overall-notes"
            >
              Overall notes
            </label>
            <textarea
              id="overall-notes"
              className="mb-3 w-full rounded border border-white/10 bg-transparent p-2"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={() => void submit('approved')}
                disabled={saving || !allApproved}
              >
                {saving ? 'Saving…' : 'Approve roadmap'}
              </Button>
              <Button
                variant="outline"
                onClick={() => void submit('rejected')}
                disabled={saving}
              >
                Reject roadmap
              </Button>
            </div>
          </Card>
        </div>
      )}
    </AdminLayout>
  );
}
