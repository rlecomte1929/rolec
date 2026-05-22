/**
 * [P1-6] Employee Roadmap page — /employee/case/:caseId/roadmap
 * Wraps the platform-v2 RoadmapScreen with live CaseForm doc counts per step.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import RoadmapScreen from '../../features/platform-v2/roadmap/RoadmapScreen';
import { getCaseRoadmapV2, type RoadmapV2Track } from '../../api/roadmapV2';
import type { RoadmapTrack, RoadmapStep } from '../../types/relopass-api-contracts';
import { buildRoute } from '../../navigation/routes';

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
    })),
  }));
}

export const EmployeeCaseRoadmapPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const [tracks, setTracks] = useState<(RoadmapTrack & { steps: RoadmapStep[] })[]>([]);
  const [docChips, setDocChips] = useState<Record<string, { count: number; worstStatus: string | null }>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    getCaseRoadmapV2(caseId)
      .then((data) => {
        setTracks(adaptTracks(data.tracks));
        const chips: Record<string, { count: number; worstStatus: string | null }> = {};
        for (const track of data.tracks) {
          for (const step of track.steps) {
            if (step.doc_count > 0) {
              chips[step.id] = { count: step.doc_count, worstStatus: step.worst_doc_status };
            }
          }
        }
        setDocChips(chips);
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

  if (loading) {
    return (
      <AppShell>
        <div style={{ padding: '24px', color: 'var(--text-muted)' }}>Loading roadmap…</div>
      </AppShell>
    );
  }
  if (error) {
    return (
      <AppShell>
        <div style={{ padding: '24px', color: 'var(--danger)' }}>{error}</div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <RoadmapScreen
        tracks={tracks}
        docChips={docChips}
        onStepDocChipClick={handleDocChipClick}
      />
    </AppShell>
  );
};
