/**
 * [P1-6] Employee Roadmap page — /employee/case/:caseId/roadmap
 * Wraps the platform-v2 RoadmapScreen with live CaseForm doc counts per step.
 */
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import RoadmapScreen from '../../features/platform-v2/roadmap/RoadmapScreen';
import { useTextSelection } from '../../hooks/useTextSelection';
import { ExplainTermPopover } from '../../features/explain/ExplainTermPopover';
import { getCaseRoadmapV2, type RoadmapV2Track } from '../../api/roadmapV2';
import { fetchRelocationPlanView } from '../../api/relocationPlanView';
import { adaptPlanViewToTracks } from './relocationPlanToRoadmap';
import type { RoadmapTrack, RoadmapStep } from '../../types/relopass-api-contracts';
import { buildRoute } from '../../navigation/routes';
import { PhaseContextBar } from '../../components/antigravity';
import { RoadmapBeingBuilt } from '../../features/employee-journey/RoadmapBeingBuilt';
import {
  successProbability,
  type ConfidenceLevel,
  type ScoringStep,
  type SuccessProbabilityResult,
} from '../../features/platform-v2/roadmap/scoring';

/**
 * Map the wire/display confidence vocabulary (UPPER — shared with P3-04 and
 * confidence.tokens.ts) onto the scoring module's internal lowercase enum.
 */
function toScoringLevel(level: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN'): ConfidenceLevel {
  return level.toLowerCase() as ConfidenceLevel;
}

/**
 * [P2-05] Build the probability-of-success estimate from the roadmap, but only
 * when at least one step carries a confidence_level. Today the deterministic
 * employee feed has none, so this returns null and the dial is hidden (graceful
 * guard); it lights up automatically once the backend emits confidence_level
 * (P3-04e) — the same field that drives the P3-04 ConfidenceBadge.
 */
function computeSuccessScore(v2Tracks: RoadmapV2Track[]): SuccessProbabilityResult | null {
  const scored: ScoringStep[] = [];
  for (const track of v2Tracks) {
    for (const step of track.steps) {
      if (step.confidence_level) {
        scored.push({ id: step.id, title: step.title, confidence: toScoringLevel(step.confidence_level) });
      }
    }
  }
  if (scored.length === 0) return null;
  // No similar-case history is available yet (P2-04) → official_only basis.
  return successProbability({ steps: scored }, []);
}

function adaptTracks(v2Tracks: RoadmapV2Track[]): (RoadmapTrack & { steps: RoadmapStep[] })[] {
  return v2Tracks.map((t) => ({
    id: t.id,
    case_id: '',
    name: t.name,
    icon: t.icon,
    sort_order: t.sort_order,
    is_mandatory: true,
    progress_pct: t.progress_pct,
    created_at: '',
    updated_at: '',
    steps: t.steps.map((s) => ({
      id: s.id,
      track_id: t.id,
      case_id: '',
      title: s.title,
      description: s.description,
      status: s.status,
      owner: s.owner as RoadmapStep['owner'],
      vendor_id: s.vendor_id,
      due_date: s.due_date,
      completed_at: null,
      sort_order: s.sort_order,
      dependency_ids: s.dependency_ids,
      ai_suggestion: s.ai_suggestion,
      created_at: '',
      updated_at: '',
      confidence_level: s.confidence_level,
      source_url: s.source_url,
      source_fetched_at: s.source_fetched_at,
      source_excerpt: s.source_excerpt,
    })),
  }));
}

export const EmployeeCaseRoadmapPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  // I-6: select a term inside the roadmap → "explain this term" popover.
  const selectionRef = useRef<HTMLDivElement>(null);
  const { selection, clear } = useTextSelection(selectionRef);
  const [tracks, setTracks] = useState<(RoadmapTrack & { steps: RoadmapStep[] })[]>([]);
  const [successScore, setSuccessScore] = useState<SuccessProbabilityResult | null>(null);
  const [docChips, setDocChips] = useState<Record<string, { count: number; worstStatus: string | null }>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    getCaseRoadmapV2(caseId)
      .then(async (data) => {
        if (data.tracks.length > 0) {
          setTracks(adaptTracks(data.tracks));
          setSuccessScore(computeSuccessScore(data.tracks));
          const chips: Record<string, { count: number; worstStatus: string | null }> = {};
          for (const track of data.tracks) {
            for (const step of track.steps) {
              if (step.doc_count > 0) {
                chips[step.id] = { count: step.doc_count, worstStatus: step.worst_doc_status };
              }
            }
          }
          setDocChips(chips);
          return;
        }
        // [AIQ-1005] The case_forms-projected V2 roadmap is empty. Fall back to
        // the seeded relocation plan (case_milestones via relocation-plans/view)
        // so the employee sees their milestones instead of the "being built"
        // placeholder. An empty/errored plan leaves tracks [] → placeholder shows
        // (graceful), which is the correct pre-intake state.
        const plan = await fetchRelocationPlanView(caseId, { role: 'employee' });
        setTracks(adaptPlanViewToTracks(plan));
        setSuccessScore(null);
        setDocChips({});
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : 'Failed to load roadmap');
      })
      .finally(() => setLoading(false));
  }, [caseId]);

  const handleDocChipClick = (stepId: string) => {
    if (!caseId) return;
    const base = buildRoute('employeeCaseDossier', { caseId });
    navigate(`${base}?roadmap_step=${stepId}`);
  };

  const phaseBar = (
    <div className="mx-auto max-w-5xl px-6 pt-6">
      <PhaseContextBar
        phases={[
          { key: 'intake', label: 'Intake', status: 'done' },
          { key: 'services', label: 'Services & policy', status: 'done' },
          { key: 'roadmap', label: 'Roadmap', status: 'current' },
        ]}
        onSelect={(key) => {
          if (key === 'intake') navigate(buildRoute('employeeIntake'));
          if (key === 'services') navigate(buildRoute('services'));
        }}
      />
    </div>
  );

  const isEmpty = tracks.length === 0;

  if (loading) {
    return (
      <AppShell>
        <div style={{ padding: '24px', color: 'var(--text-muted)' }}>Loading roadmap…</div>
      </AppShell>
    );
  }
  if (error || isEmpty) {
    return (
      <AppShell>
        {phaseBar}
        <div className="mx-auto max-w-5xl px-6 py-6">
          <RoadmapBeingBuilt onMessageTeam={() => navigate(buildRoute('messages'))} />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      {phaseBar}
      <div ref={selectionRef}>
        <RoadmapScreen
          tracks={tracks}
          docChips={docChips}
          onStepDocChipClick={handleDocChipClick}
          successScore={successScore}
          caseId={caseId}
        />
      </div>
      {selection && (
        <ExplainTermPopover selection={selection} assignmentId={caseId ?? ''} onClose={clear} />
      )}
    </AppShell>
  );
};
