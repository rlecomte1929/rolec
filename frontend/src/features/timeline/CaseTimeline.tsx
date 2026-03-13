import React, { useCallback, useEffect, useState } from 'react';
import { Card, Button } from '../../components/antigravity';
import { timelineAPI, type TimelineMilestone } from '../../api/client';

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-slate-100 text-slate-700 border-slate-200',
  in_progress: 'bg-blue-100 text-blue-800 border-blue-200',
  done: 'bg-green-100 text-green-800 border-green-200',
  skipped: 'bg-gray-100 text-gray-500 border-gray-200',
  overdue: 'bg-amber-100 text-amber-800 border-amber-200',
};

const STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  in_progress: 'In progress',
  done: 'Done',
  skipped: 'Skipped',
  overdue: 'Overdue',
};

interface CaseTimelineProps {
  assignmentId: string;
  ensureDefaults?: boolean;
}

export const CaseTimeline: React.FC<CaseTimelineProps> = ({
  assignmentId,
  ensureDefaults = true,
}) => {
  const [milestones, setMilestones] = useState<TimelineMilestone[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);

  const load = useCallback(async () => {
    if (!assignmentId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await timelineAPI.getByAssignment(assignmentId, {
        ensureDefaults,
      });
      setMilestones(data.milestones || []);
      if (data.milestones?.length && !selectedId) {
        setSelectedId(data.milestones[0]?.id ?? null);
      }
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      setError(String(msg || 'Failed to load timeline'));
      setMilestones([]);
    } finally {
      setLoading(false);
    }
  }, [assignmentId, ensureDefaults]);

  useEffect(() => {
    load();
  }, [load]);

  const selected = milestones.find((m) => m.id === selectedId);
  const handleStatusChange = useCallback(
    async (milestoneId: string, status: string) => {
      if (!assignmentId || !selected?.case_id) return;
      setUpdating(true);
      try {
        await timelineAPI.updateMilestone(selected.case_id, milestoneId, { status });
        await load();
      } catch (err: unknown) {
        const msg =
          err && typeof err === 'object' && 'response' in err
            ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
            : (err as Error)?.message;
        setError(String(msg || 'Failed to update'));
      } finally {
        setUpdating(false);
      }
    },
    [assignmentId, selected?.case_id, load]
  );

  if (loading && milestones.length === 0) {
    return (
      <Card padding="lg">
        <div className="text-sm text-[#6b7280]">Loading timeline...</div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card padding="lg">
        <div className="text-sm text-red-600">{error}</div>
        <Button variant="outline" size="sm" className="mt-2" onClick={load}>
          Retry
        </Button>
      </Card>
    );
  }

  if (milestones.length === 0) {
    return (
      <Card padding="lg">
        <div className="text-sm text-[#6b7280]">No milestones yet.</div>
        <Button variant="outline" size="sm" className="mt-2" onClick={() => load()}>
          Load defaults
        </Button>
      </Card>
    );
  }

  return (
    <Card padding="lg">
      <h3 className="text-base font-semibold text-[#0b2b43] mb-4">Relocation timeline</h3>
      <div className="flex gap-4">
        <div className="flex-shrink-0 w-48 space-y-1">
          {milestones.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => setSelectedId(m.id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                selectedId === m.id
                  ? 'bg-[#0b2b43] text-white'
                  : 'hover:bg-[#f1f5f9] text-[#4b5563]'
              }`}
            >
              <div className="font-medium truncate">{m.title}</div>
              <div
                className={`text-xs mt-0.5 ${
                  selectedId === m.id ? 'text-white/80' : 'text-[#6b7280]'
                }`}
              >
                {m.target_date
                  ? new Date(m.target_date).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })
                  : '—'}
              </div>
            </button>
          ))}
        </div>
        <div className="flex-1 min-w-0 border-l border-[#e2e8f0] pl-4">
          {selected ? (
            <div>
              <div className="flex items-center justify-between gap-2 mb-2">
                <h4 className="font-semibold text-[#0b2b43]">{selected.title}</h4>
                <span
                  className={`px-2 py-0.5 rounded text-xs font-medium border ${
                    STATUS_STYLES[selected.status] || STATUS_STYLES.pending
                  }`}
                >
                  {STATUS_LABELS[selected.status] || selected.status}
                </span>
              </div>
              {selected.description && (
                <p className="text-sm text-[#4b5563] mb-3">{selected.description}</p>
              )}
              <dl className="grid grid-cols-2 gap-2 text-sm mb-4">
                {selected.target_date && (
                  <div>
                    <dt className="text-[#6b7280]">Target</dt>
                    <dd>
                      {new Date(selected.target_date).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </dd>
                  </div>
                )}
                {selected.actual_date && (
                  <div>
                    <dt className="text-[#6b7280]">Actual</dt>
                    <dd>
                      {new Date(selected.actual_date).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </dd>
                  </div>
                )}
              </dl>
              <div className="flex flex-wrap gap-1">
                {(['pending', 'in_progress', 'done', 'skipped'] as const).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => handleStatusChange(selected.id, s)}
                    disabled={updating || selected.status === s}
                    className={`px-2 py-1 rounded text-xs font-medium ${
                      selected.status === s
                        ? STATUS_STYLES[s]
                        : 'bg-[#f1f5f9] text-[#6b7280] hover:bg-[#e2e8f0]'
                    }`}
                  >
                    {STATUS_LABELS[s]}
                  </button>
                ))}
              </div>
              {selected.links && selected.links.length > 0 && (
                <div className="mt-4 pt-3 border-t border-[#e2e8f0]">
                  <div className="text-xs font-medium text-[#6b7280] mb-1">Linked</div>
                  <div className="flex flex-wrap gap-1">
                    {selected.links.map((l) => (
                      <span
                        key={l.id}
                        className="px-2 py-0.5 bg-[#f1f5f9] rounded text-xs"
                      >
                        {l.linked_entity_type}:{l.linked_entity_id.slice(0, 8)}…
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm text-[#6b7280]">Select a milestone</div>
          )}
        </div>
      </div>
    </Card>
  );
};
