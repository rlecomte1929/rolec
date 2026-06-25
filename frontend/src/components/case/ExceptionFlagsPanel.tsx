/**
 * ExceptionFlagsPanel — surface immigration/policy exception flags to HR,
 * with inline Approve / Deny / Escalate controls.
 *
 * Fetches from GET /api/cases/{caseId}/exceptions on mount and after any
 * status update. Renders nothing when there are no flags or if the fetch
 * fails (fail-open).
 *
 * Resolution flow per flag:
 *   1. HR clicks Approve / Deny / Escalate.
 *   2. An optional resolution notes textarea appears.
 *   3. HR confirms → PATCH /api/cases/{caseId}/exceptions/{id}.
 *   4. The flag list re-fetches to reflect the new status.
 *
 * Resolved flags (non-pending) are shown collapsed with a status badge so
 * HR has an audit trail without the action buttons cluttering the view.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Button } from '../antigravity/Button';
import { fetchCaseExceptions, updateCaseException } from '../../api/cases';
import type { ExceptionResolutionStatus } from '../../api/cases';
import type { CaseExceptionsResponse, ExceptionFlag } from '../../types';

// ── Label maps ────────────────────────────────────────────────────────────────

const EXCEPTION_TYPE_LABELS: Record<string, string> = {
  tenure_insufficient:          'Insufficient employment tenure',
  no_sponsoring_entity:         'No sponsoring entity confirmed',
  timeline_breach:              'Timeline too tight',
  cost_threshold:               'Package cost exceeds threshold',
  role_category_ambiguous:      'Visa role category unclear',
  dual_intent_conflict:         'Dual intent conflict',
  points_threshold_unconfirmed: 'UK points eligibility not confirmed',
  policy_custom:                'Custom policy exception',
};

const STATUS_LABELS: Record<string, { label: string; className: string }> = {
  approved:  { label: 'Approved',  className: 'bg-[#dcfce7] text-[#166534]' },
  denied:    { label: 'Denied',    className: 'bg-[#fee2e2] text-[#991b1b]' },
  escalated: { label: 'Escalated', className: 'bg-[#fef9c3] text-[#854d0e]' },
  withdrawn: { label: 'Withdrawn', className: 'bg-[#f1f5f9] text-[#475569]' },
  pending:   { label: 'Pending',   className: 'bg-[#e0f2fe] text-[#0369a1]' },
};

function exceptionLabel(type: string): string {
  return EXCEPTION_TYPE_LABELS[type] ?? type.replace(/_/g, ' ');
}

function statusBadge(status: string) {
  const s = STATUS_LABELS[status] ?? STATUS_LABELS.pending ?? { label: 'Pending', className: 'bg-[#e0f2fe] text-[#0369a1]' };
  return (
    <span className={`text-xs font-medium rounded-full px-2 py-0.5 ${s.className}`}>
      {s.label}
    </span>
  );
}

// ── Inline action widget ──────────────────────────────────────────────────────

interface ActionWidgetProps {
  flag: ExceptionFlag;
  caseId: string;
  onResolved: () => void;
  isBlocker: boolean;
}

const ActionWidget: React.FC<ActionWidgetProps> = ({ flag, caseId, onResolved, isBlocker }) => {
  const [chosen, setChosen] = useState<ExceptionResolutionStatus | null>(null);
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleConfirm = async () => {
    if (!chosen) return;
    setSaving(true);
    setError('');
    try {
      await updateCaseException(caseId, flag.id, {
        status: chosen,
        resolution_notes: notes.trim() || undefined,
      });
      onResolved();
    } catch {
      setError('Failed to save. Please try again.');
      setSaving(false);
    }
  };

  if (chosen) {
    const actionColors: Record<ExceptionResolutionStatus, string> = {
      approved:  'border-[#bbf7d0] bg-[#f0fdf4]',
      denied:    'border-[#fecaca] bg-[#fef2f2]',
      escalated: 'border-[#fef08a] bg-[#fefce8]',
      withdrawn: 'border-[#e2e8f0] bg-[#f8fafc]',
    };
    return (
      <div className={`mt-2 rounded-lg border p-3 ${actionColors[chosen]}`}>
        <div className="text-xs font-semibold text-[#374151] mb-1">
          {chosen.charAt(0).toUpperCase() + chosen.slice(1)} — add a note (optional)
        </div>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className="w-full text-sm rounded border border-[#d1d5db] px-2 py-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-[#3b82f6]"
          placeholder="Resolution notes visible in audit log…"
        />
        {error && <div className="text-xs text-[#dc2626] mt-1">{error}</div>}
        <div className="flex gap-2 mt-2">
          <Button unstyled
            onClick={handleConfirm}
            disabled={saving}
            className="text-xs font-semibold px-3 py-1.5 rounded bg-[#0b2b43] text-white hover:bg-[#1a3d5c] disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Confirm'}
          </Button>
          <Button unstyled
            onClick={() => { setChosen(null); setNotes(''); setError(''); }}
            disabled={saving}
            className="text-xs px-3 py-1.5 rounded border border-[#d1d5db] text-[#374151] hover:bg-[#f9fafb] disabled:opacity-50"
          >
            Cancel
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      <Button unstyled
        onClick={() => setChosen('approved')}
        className="text-xs font-medium px-2.5 py-1 rounded border border-[#86efac] bg-[#f0fdf4] text-[#166534] hover:bg-[#dcfce7]"
      >
        ✓ Approve
      </Button>
      {isBlocker && (
        <Button unstyled
          onClick={() => setChosen('escalated')}
          className="text-xs font-medium px-2.5 py-1 rounded border border-[#fde68a] bg-[#fefce8] text-[#854d0e] hover:bg-[#fef08a]"
        >
          ↑ Escalate
        </Button>
      )}
      <Button unstyled
        onClick={() => setChosen('denied')}
        className="text-xs font-medium px-2.5 py-1 rounded border border-[#fca5a5] bg-[#fef2f2] text-[#991b1b] hover:bg-[#fee2e2]"
      >
        ✕ Deny
      </Button>
      <Button unstyled
        onClick={() => setChosen('withdrawn')}
        className="text-xs font-medium px-2.5 py-1 rounded border border-[#e2e8f0] bg-white text-[#6b7280] hover:bg-[#f9fafb]"
      >
        Withdraw
      </Button>
    </div>
  );
};

// ── Flag row ──────────────────────────────────────────────────────────────────

interface FlagRowProps {
  flag: ExceptionFlag;
  caseId: string;
  isBlocker: boolean;
  onResolved: () => void;
}

const FlagRow: React.FC<FlagRowProps> = ({ flag, caseId, isBlocker, onResolved }) => {
  const isPending = flag.status === 'pending';

  return (
    <li className="border-t border-current/10 pt-3 first:border-t-0 first:pt-0">
      <div className="flex items-start gap-2">
        <span className={`mt-0.5 shrink-0 text-base ${isBlocker ? 'text-[#dc2626]' : 'text-[#d97706]'}`}>
          {isBlocker ? '🚫' : '⚠️'}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-sm">{exceptionLabel(flag.exception_type)}</span>
            {statusBadge(flag.status)}
          </div>
          <p className="mt-0.5 text-sm opacity-90 leading-snug">{flag.reason}</p>
          {flag.recommended_action && (
            <p className="mt-1 text-xs opacity-75 italic leading-snug">
              <span className="not-italic font-medium">Recommended action: </span>
              {flag.recommended_action}
            </p>
          )}
          {flag.resolution_notes && !isPending && (
            <p className="mt-1 text-xs text-[#4b5563] leading-snug">
              <span className="font-medium">Note: </span>{flag.resolution_notes}
            </p>
          )}
          {isPending && (
            <ActionWidget
              flag={flag}
              caseId={caseId}
              isBlocker={isBlocker}
              onResolved={onResolved}
            />
          )}
        </div>
      </div>
    </li>
  );
};

// ── Main panel ────────────────────────────────────────────────────────────────

interface ExceptionFlagsPanelProps {
  /** The relocation case ID (not assignment ID). Available as assignment.caseId in HR views. */
  caseId: string;
}

export const ExceptionFlagsPanel: React.FC<ExceptionFlagsPanelProps> = ({ caseId }) => {
  const [data, setData] = useState<CaseExceptionsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    if (!caseId) { setLoading(false); return; }
    fetchCaseExceptions(caseId)
      .then(setData)
      .finally(() => setLoading(false));
  }, [caseId]);

  useEffect(() => { load(); }, [load]);

  if (loading || !data || data.total === 0) return null;

  const { blockers, warnings } = data;
  // Separate pending from resolved for each severity group.
  const pendingBlockers  = blockers.filter((f) => f.status === 'pending');
  const resolvedBlockers = blockers.filter((f) => f.status !== 'pending');
  const pendingWarnings  = warnings.filter((f) => f.status === 'pending');
  const resolvedWarnings = warnings.filter((f) => f.status !== 'pending');

  const hasActive = pendingBlockers.length + pendingWarnings.length > 0;
  const hasResolved = resolvedBlockers.length + resolvedWarnings.length > 0;

  return (
    <div className="space-y-3">
      {/* ── Active blockers ─────────────────────────────────────────────── */}
      {pendingBlockers.length > 0 && (
        <div className="rounded-lg border border-[#fca5a5] bg-[#fef2f2] px-4 py-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-[#dc2626] text-base">🚫</span>
            <h3 className="text-sm font-semibold text-[#991b1b]">
              {pendingBlockers.length} Case blocker{pendingBlockers.length > 1 ? 's' : ''} — HR action required
            </h3>
            <span className="ml-auto text-xs text-[#b91c1c] bg-[#fee2e2] rounded-full px-2 py-0.5 font-medium">
              Cannot proceed
            </span>
          </div>
          <ul className="space-y-3 text-[#7f1d1d]">
            {pendingBlockers.map((flag) => (
              <FlagRow key={flag.id} flag={flag} caseId={caseId} isBlocker onResolved={load} />
            ))}
          </ul>
        </div>
      )}

      {/* ── Active warnings ─────────────────────────────────────────────── */}
      {pendingWarnings.length > 0 && (
        <div className="rounded-lg border border-[#fcd34d] bg-[#fffbeb] px-4 py-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-[#d97706] text-base">⚠️</span>
            <h3 className="text-sm font-semibold text-[#92400e]">
              {pendingWarnings.length} Immigration warning{pendingWarnings.length > 1 ? 's' : ''} — review recommended
            </h3>
          </div>
          <ul className="space-y-3 text-[#78350f]">
            {pendingWarnings.map((flag) => (
              <FlagRow key={flag.id} flag={flag} caseId={caseId} isBlocker={false} onResolved={load} />
            ))}
          </ul>
        </div>
      )}

      {/* ── Resolved flags (audit trail, collapsed) ─────────────────────── */}
      {hasResolved && (
        <details className="rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3">
          <summary className="cursor-pointer text-xs font-medium text-[#64748b] select-none">
            {resolvedBlockers.length + resolvedWarnings.length} resolved flag
            {resolvedBlockers.length + resolvedWarnings.length > 1 ? 's' : ''} (audit trail)
          </summary>
          <ul className="mt-3 space-y-3 text-[#374151]">
            {[...resolvedBlockers, ...resolvedWarnings].map((flag) => (
              <FlagRow
                key={flag.id}
                flag={flag}
                caseId={caseId}
                isBlocker={flag.severity === 'blocker'}
                onResolved={load}
              />
            ))}
          </ul>
        </details>
      )}

      {/* ── All-clear banner once every flag is resolved ─────────────────── */}
      {!hasActive && hasResolved && (
        <div className="rounded-lg border border-[#bbf7d0] bg-[#f0fdf4] px-4 py-3 flex items-center gap-2">
          <span className="text-[#16a34a]">✓</span>
          <span className="text-sm font-medium text-[#166534]">
            All exception flags have been resolved.
          </span>
        </div>
      )}
    </div>
  );
};
