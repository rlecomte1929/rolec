/**
 * ProviderCoordinationPanel
 *
 * The primary HR surface for managing external providers on a case.
 * Renders on HrCommandCenterCaseDetail below ExceptionFlagsPanel.
 *
 * Features:
 *  - List providers involved in this case, each showing their task list
 *  - Per-task status controls (pending → in_progress → completed / blocked)
 *  - Assign Task modal (create a new provider task)
 *  - Invite Provider modal (2-step: pick/create → email → magic link)
 *  - Realtime updates via Supabase postgres_changes subscription
 *  - Polling fallback when realtime is unavailable
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Button } from '../antigravity/Button';
import { listCaseProviders, listProviderTasks } from '../../api/providers';
import type { ProviderItem, ProviderTaskItem } from '../../api/providers';
import { useProviderRealtime } from '../../hooks/useProviderRealtime';
import { ProviderRow } from './ProviderRow';
import { AssignTaskModal } from './AssignTaskModal';
import { InviteProviderModal } from './InviteProviderModal';
import { Card } from '../antigravity';

interface ProviderCoordinationPanelProps {
  caseId: string;
}

export const ProviderCoordinationPanel: React.FC<ProviderCoordinationPanelProps> = ({ caseId }) => {
  const [providers, setProviders]   = useState<ProviderItem[]>([]);
  const [tasks, setTasks]           = useState<ProviderTaskItem[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');

  // Modal state
  const [assignTarget, setAssignTarget]   = useState<ProviderItem | null>(null);
  const [inviteTarget, setInviteTarget]   = useState<ProviderItem | null>(null);
  const [showInviteNew, setShowInviteNew] = useState(false);

  // ── Data loading ──────────────────────────────────────────────────────────

  const load = useCallback(async () => {
    if (!caseId) return;
    try {
      const [provs, taskList] = await Promise.all([
        listCaseProviders(caseId),
        listProviderTasks(caseId),
      ]);
      setProviders(provs);
      setTasks(taskList);
      setError('');
    } catch {
      setError('Could not load provider coordination data.');
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => { load(); }, [load]);

  // Realtime: re-fetch on any insert/update to provider_tasks
  useProviderRealtime(caseId, load);

  // ── Local optimistic updates ───────────────────────────────────────────────

  const handleTaskUpdated = (updated: ProviderTaskItem) => {
    setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
  };

  const handleTaskCreated = (task: ProviderTaskItem) => {
    setTasks((prev) => [...prev, task]);
    // Ensure the provider is in the list
    if (!providers.find((p) => p.id === task.provider_id)) {
      load();
    }
    setAssignTarget(null);
  };

  const handleInviteSent = () => {
    load(); // re-fetch provider list in case new provider was just created
    setInviteTarget(null);
    setShowInviteNew(false);
  };

  // ── Group tasks by provider ───────────────────────────────────────────────

  const tasksByProvider = (providerId: string) =>
    tasks.filter((t) => t.provider_id === providerId);

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <Card padding="lg">
        <div className="text-sm text-[#94a3b8]">Loading provider coordination…</div>
      </Card>
    );
  }

  return (
    <>
      <Card padding="lg">
        {/* Header */}
        <div className="flex items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="text-sm font-semibold text-[#0b2b43]">Provider coordination</h2>
            {providers.length > 0 && (
              <p className="text-xs text-[#6b7280] mt-0.5">
                {providers.length} provider{providers.length > 1 ? 's' : ''} ·{' '}
                {tasks.filter((t) => t.status === 'completed').length}/{tasks.length} tasks done
              </p>
            )}
          </div>
          <Button unstyled
            onClick={() => setShowInviteNew(true)}
            className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-[#0b2b43] text-white hover:bg-[#1a3d5c] transition-colors shrink-0"
          >
            + Invite provider
          </Button>
        </div>

        {/* Error banner */}
        {error && (
          <div className="mb-4 rounded-lg border border-[#fca5a5] bg-[#fef2f2] px-3 py-2 text-sm text-[#991b1b]">
            {error}
          </div>
        )}

        {/* Provider list */}
        {providers.length === 0 ? (
          <div className="rounded-lg border border-dashed border-[#d1d5db] bg-[#f9fafb] px-6 py-8 text-center">
            <p className="text-sm text-[#6b7280]">No providers on this case yet.</p>
            <p className="text-xs text-[#94a3b8] mt-1">
              Click <span className="font-medium">+ Invite provider</span> to add one.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {providers.map((p) => (
              <ProviderRow
                key={p.id}
                provider={p}
                tasks={tasksByProvider(p.id)}
                caseId={caseId}
                onTaskUpdated={handleTaskUpdated}
                onInvite={(prov) => setInviteTarget(prov)}
                onAssignTask={(prov) => setAssignTarget(prov)}
              />
            ))}
          </div>
        )}
      </Card>

      {/* Assign task modal */}
      {assignTarget && (
        <AssignTaskModal
          provider={assignTarget}
          caseId={caseId}
          onCreated={handleTaskCreated}
          onClose={() => setAssignTarget(null)}
        />
      )}

      {/* Invite existing provider (from ProviderRow "Invite" button) */}
      {inviteTarget && (
        <InviteProviderModal
          caseId={caseId}
          preselectedProvider={inviteTarget}
          onInviteSent={handleInviteSent}
          onClose={() => setInviteTarget(null)}
        />
      )}

      {/* Invite new (from "+ Invite provider" header button) */}
      {showInviteNew && (
        <InviteProviderModal
          caseId={caseId}
          onInviteSent={handleInviteSent}
          onClose={() => setShowInviteNew(false)}
        />
      )}
    </>
  );
};
