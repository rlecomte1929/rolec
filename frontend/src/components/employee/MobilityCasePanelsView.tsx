/**
 * Presentational panels only (no API imports — safe for unit tests).
 */

import { Card } from '../antigravity';

export type MobilityCasePanelsViewProps = {
  routeOrigin: string;
  routeDestination: string;
  caseTypeLabel: string;
  familyStatusLine: string;
  missingItems: Array<{ id: string; code: string; status: string; detail: string }>;
  nextActions: Array<{ id: string; title: string; description: string; priority: number }>;
  loadState: 'skipped' | 'loading' | 'error' | 'loaded';
  errorMessage?: string;
};

export function MobilityCasePanelsView({
  routeOrigin,
  routeDestination,
  caseTypeLabel,
  familyStatusLine,
  missingItems,
  nextActions,
  loadState,
  errorMessage,
}: MobilityCasePanelsViewProps) {
  return (
    <div className="space-y-4 mb-6" data-testid="mobility-panels-root">
      <Card padding="md">
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">Your relocation route</div>
        <ul className="text-sm text-[#374151] space-y-1 list-none p-0 m-0">
          <li>
            <span className="text-[#6b7280]">Origin: </span>
            {routeOrigin}
          </li>
          <li>
            <span className="text-[#6b7280]">Destination: </span>
            {routeDestination}
          </li>
          <li>
            <span className="text-[#6b7280]">Case type: </span>
            {caseTypeLabel}
          </li>
          <li>
            <span className="text-[#6b7280]">Family: </span>
            {familyStatusLine}
          </li>
        </ul>
      </Card>

      <Card padding="md">
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">Missing or needs review</div>
        {loadState === 'skipped' && (
          <p className="text-sm text-[#6b7280] m-0" data-testid="missing-empty-unlinked">
            No mobility evaluations yet. When your case is linked to the mobility tracker, items that need attention
            will appear here.
          </p>
        )}
        {loadState === 'loading' && (
          <p className="text-sm text-[#6b7280] m-0" data-testid="missing-loading" aria-busy="true">
            Checking requirements…
          </p>
        )}
        {loadState === 'error' && (
          <p className="text-sm text-red-700 m-0" data-testid="missing-error">
            {errorMessage || 'Could not load evaluations.'}
          </p>
        )}
        {loadState === 'loaded' && missingItems.length === 0 && (
          <p className="text-sm text-[#6b7280] m-0" data-testid="missing-empty-ok">
            Nothing missing right now. You’re all set on tracked requirements.
          </p>
        )}
        {loadState === 'loaded' && missingItems.length > 0 && (
          <ul className="space-y-2 m-0 p-0 list-none" data-testid="missing-list">
            {missingItems.map((m) => (
              <li key={m.id} className="text-sm border border-[#e5e7eb] rounded-md p-2 bg-[#f9fafb]">
                <div className="font-medium text-[#0b2b43]">{m.code.replace(/_/g, ' ')}</div>
                <div className="text-xs text-[#6b7280] mt-0.5 capitalize">{m.status.replace(/_/g, ' ')}</div>
                {m.detail ? <div className="text-[#374151] mt-1">{m.detail}</div> : null}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card padding="md">
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">Next steps</div>
        {loadState === 'skipped' && (
          <p className="text-sm text-[#6b7280] m-0" data-testid="next-empty-unlinked">
            Suggested next steps will show here once your case is linked to mobility tracking.
          </p>
        )}
        {loadState === 'loading' && (
          <p className="text-sm text-[#6b7280] m-0" data-testid="next-loading" aria-busy="true">
            Loading next steps…
          </p>
        )}
        {loadState === 'error' && (
          <p className="text-sm text-red-700 m-0" data-testid="next-error">
            {errorMessage || 'Could not load next steps.'}
          </p>
        )}
        {loadState === 'loaded' && nextActions.length === 0 && (
          <p className="text-sm text-[#6b7280] m-0" data-testid="next-empty-ok">
            No suggested actions right now.
          </p>
        )}
        {loadState === 'loaded' && nextActions.length > 0 && (
          <ol className="space-y-2 m-0 p-0 list-decimal list-inside" data-testid="next-list">
            {nextActions.map((a) => (
              <li key={a.id} className="text-sm text-[#374151]">
                <span className="font-medium text-[#0b2b43]">{a.title}</span>
                <div className="text-[#6b7280] mt-0.5 pl-0">{a.description}</div>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  );
}
