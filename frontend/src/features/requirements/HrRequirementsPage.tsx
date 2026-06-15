import { useNavigate, useSearchParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Button, Card } from '../../components/antigravity';
import { ROUTE_DEFS, buildRoute } from '../../navigation/routes';
import { useSelectedCase } from '../../contexts/SelectedCaseContext';
import { ImmigrationStatusPanel } from '../../components/case/ImmigrationStatusPanel';

/**
 * [NAV-001] HR Requirements tab — corridor immigration compliance.
 *
 * Replaces the old sidebar "Requirements" entry that pointed at /resources (a
 * lifestyle destination guide). This page shows the real corridor compliance
 * view for the selected case: document checklist, risk flags, milestone tracker
 * and employee-intake progress — all sourced from live DB endpoints, with no
 * fabricated content (the coverage gate is enforced by the panel: covered=false
 * renders a "no checklist for this corridor yet" state).
 *
 * Per the "compose, don't duplicate" guardrail, the page composes the existing
 * ImmigrationStatusPanel (which already fetches /immigration-requirements +
 * /immigration/interview-status and embeds the MilestoneTracker) rather than
 * re-implementing the sections. This page only adds case resolution + the
 * no-case empty state + the route/sidebar wiring.
 */
const SUBTITLE =
  'Corridor immigration compliance for the selected case — required documents, risk flags, milestones, and employee intake progress. Sourced from live data.';

export function HrRequirementsPage() {
  const [searchParams] = useSearchParams();
  const { selectedCaseId } = useSelectedCase();
  const navigate = useNavigate();

  // Case-scoped: resolve from ?caseId= (deep links) then the HR selected-case
  // context — the same resolution other HR case-scoped pages use.
  const caseId = searchParams.get('caseId') || selectedCaseId || '';

  if (!caseId) {
    return (
      <AppShell section="HR Operations" title="Requirements" subtitle={SUBTITLE}>
        <Card padding="lg">
          <div className="flex flex-col items-center justify-center py-12 text-center max-w-md mx-auto">
            <h2 className="text-lg font-semibold text-[#0b2b43]">No case selected</h2>
            <p className="text-sm text-[#64748b] mt-1.5">
              Open a case from the Mobility command center to see its immigration document
              checklist, risk flags, and milestones.
            </p>
            <div className="mt-5">
              <Button onClick={() => navigate(ROUTE_DEFS.hrCommandCenter.path)}>
                Go to Mobility command center →
              </Button>
            </div>
          </div>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell section="HR Operations" title="Requirements" subtitle={SUBTITLE}>
      <ImmigrationStatusPanel
        caseId={caseId}
        moveDate={null}
        onFindVendor={() => navigate(buildRoute('hrCommandCenterCase', { id: caseId }))}
        onViewProfile={() => navigate(buildRoute('hrAssignmentReview', { id: caseId }))}
      />
    </AppShell>
  );
}
