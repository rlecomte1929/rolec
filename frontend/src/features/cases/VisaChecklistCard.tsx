/**
 * Visa Checklist — the case cockpit's requirement checklist.
 *
 * Requirements come from GET /api/cases/{id}/requirements/checklist, which is backed by the
 * SAME requirements_builder the public corridor endpoint uses. There is no second source and
 * no client-side filtering of which requirements apply — that decision belongs to the engine.
 *
 * Completion state persists per case: a tick POSTs and the server returns the refreshed view,
 * so the progress counter reflects the stored total rather than an optimistic local guess.
 */

import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Clock } from 'lucide-react';
import { Card, ProgressBar } from '../../components/antigravity';
import { Checkbox } from '../../components/antigravity/Checkbox';
import { getCaseChecklist, setCaseChecklistItem, type ChecklistView } from '../../api/cases';
import { getCountryName } from '../../utils/countries';

export const VisaChecklistCard: React.FC<{ caseId: string | null | undefined }> = ({ caseId }) => {
  const queryClient = useQueryClient();
  const queryKey = ['case', 'checklist', caseId];

  const checklistQuery = useQuery({
    queryKey,
    queryFn: () => getCaseChecklist(caseId!),
    enabled: !!caseId,
    retry: false,
  });

  const toggle = useMutation({
    mutationFn: ({ id, completed }: { id: string; completed: boolean }) =>
      setCaseChecklistItem(caseId!, id, completed),
    // The server returns the whole view; seed the cache with it rather than refetching.
    onSuccess: (view: ChecklistView) => queryClient.setQueryData(queryKey, view),
  });

  if (!caseId) return null;

  if (checklistQuery.isLoading) {
    return (
      <Card padding="md">
        <div className="text-sm text-slate-500">Loading the visa checklist…</div>
      </Card>
    );
  }

  if (checklistQuery.isError || !checklistQuery.data) {
    return (
      <Card padding="md">
        <div className="text-sm font-semibold text-navy-800 mb-1">Visa Checklist</div>
        <div className="text-sm text-slate-500">
          Unable to load the checklist for this case right now.
        </div>
      </Card>
    );
  }

  const view = checklistQuery.data;

  // Three distinct empty states. "No catalogue" and "nothing applies" must never render the
  // same sentence — an empty list that reads as "nothing is required" is the AIQ-1473c bug.
  if (!view.covered) {
    return (
      <Card padding="md">
        <div className="text-sm font-semibold text-navy-800 mb-1">Visa Checklist</div>
        <div className="text-sm text-slate-500">
          No requirements catalogue for {getCountryName(view.destCountry) || view.destCountry} yet — nothing to check off until this
          corridor is covered.
        </div>
      </Card>
    );
  }

  if (view.items.length === 0) {
    return (
      <Card padding="md">
        <div className="text-sm font-semibold text-navy-800 mb-1">Visa Checklist</div>
        <div className="text-sm text-slate-500">
          No requirements apply to this case.
        </div>
      </Card>
    );
  }

  return (
    <Card padding="md">
      <div className="flex items-baseline justify-between gap-3 mb-1">
        <div className="text-sm font-semibold text-navy-800">Visa Checklist</div>
        <div className="text-xs text-slate-500">
          {view.completedCount} of {view.totalCount} complete
        </div>
      </div>
      {/* showLabel off: the "N of M complete" line above already states progress, and two
          readings of the same number invite them to disagree. */}
      <div className="mb-4">
        <ProgressBar value={view.percentComplete} showLabel={false} />
      </div>

      <ul className="divide-y divide-slate-100">
        {view.items.map((item) => (
          <li key={item.id} className="py-3 flex items-start gap-3">
            <Checkbox
              checked={item.completed}
              disabled={toggle.isPending}
              onChange={() => toggle.mutate({ id: item.id, completed: !item.completed })}
              className="mt-0.5 h-4 w-4 shrink-0"
              aria-label={`Mark "${item.title}" ${item.completed ? 'incomplete' : 'complete'}`}
            />
            <div className="min-w-0">
              <div
                className={`text-sm font-medium ${
                  item.completed ? 'text-slate-500 line-through' : 'text-navy-800'
                }`}
              >
                {item.title}
              </div>
              {item.description && (
                <div className="text-xs text-slate-500 mt-0.5">{item.description}</div>
              )}
              <div className="flex flex-wrap items-center gap-2 mt-1">
                <span className="inline-flex items-center rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                  {item.pillar}
                </span>
                {item.timing && (
                  <span className="inline-flex items-center gap-1 text-[11px] text-slate-500">
                    <Clock size={12} aria-hidden="true" />
                    {item.timing}
                  </span>
                )}
                {/* Explicitly `=== true`: null means "not modeled", which is not the same as
                    false and must not render the flag. */}
                {item.nonObvious === true && (
                  <span
                    className="inline-flex items-center gap-1 rounded-full border border-[#fde68a] bg-[#fef9c3] px-2 py-0.5 text-[11px] font-medium text-[#854d0e]"
                    title="Easy to miss — this is not something most people would anticipate."
                  >
                    <AlertTriangle size={11} aria-hidden="true" />
                    Easy to miss
                  </span>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>

      {toggle.isError && (
        <div className="mt-3 text-xs text-red-600">
          Couldn’t save that change — it has not been recorded. Try again.
        </div>
      )}
    </Card>
  );
};
