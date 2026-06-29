import React, { useEffect, useState } from 'react';
import {
  getCaseRuleUpdates,
  dismissCaseRuleUpdate,
  type CaseRuleUpdate,
} from '../../../api/caseRuleUpdates';

/**
 * [P2-02e] "Rule updated — please review" roadmap banner.
 *
 * Shows when the user's case has one or more approved rule-update notifications
 * (an admin approved a material source change in P2-02d). Dismissible per source.
 * Renders nothing when there are no active updates.
 */
export const RuleUpdateBanner: React.FC<{ caseId: string }> = ({ caseId }) => {
  const [updates, setUpdates] = useState<CaseRuleUpdate[]>([]);
  const [dismissing, setDismissing] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    getCaseRuleUpdates(caseId)
      .then((r) => {
        if (!cancelled) setUpdates(r.items ?? []);
      })
      .catch(() => {
        // Banner is non-critical; never block the roadmap on its failure.
        if (!cancelled) setUpdates([]);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  const handleDismiss = async (id: string) => {
    setDismissing(id);
    try {
      await dismissCaseRuleUpdate(caseId, id);
      setUpdates((prev) => prev.filter((u) => u.id !== id));
    } catch {
      // Leave it in place if the dismiss failed; the user can retry.
    } finally {
      setDismissing(null);
    }
  };

  if (updates.length === 0) return null;

  return (
    <div
      role="alert"
      className="mx-4 mt-4 rounded-xl border border-amber-300 bg-amber-50 p-4"
    >
      <div className="font-semibold text-amber-900">Rule updated — please review</div>
      <p className="mt-0.5 text-sm text-amber-800">
        A rule your roadmap relies on has changed. Please review the update
        {updates.length > 1 ? 's' : ''} below.
      </p>
      <ul className="mt-3 space-y-2">
        {updates.map((u) => (
          <li
            key={u.id}
            className="flex items-center justify-between gap-3 rounded-lg bg-white/70 px-3 py-2"
          >
            <span className="text-sm text-amber-900">
              {u.source_url ? (
                <a
                  href={u.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium hover:underline"
                >
                  {u.source_name || u.source_url}
                </a>
              ) : (
                <span className="font-medium">{u.source_name || 'Updated source'}</span>
              )}
            </span>
            <button
              type="button"
              aria-label="Dismiss"
              disabled={dismissing === u.id}
              onClick={() => handleDismiss(u.id)}
              className="rounded-md px-2 py-1 text-sm text-amber-700 hover:bg-amber-100 disabled:opacity-50"
            >
              Dismiss
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default RuleUpdateBanner;
