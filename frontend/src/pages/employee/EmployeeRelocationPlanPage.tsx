/**
 * Employee relocation plan — shared task checklist (moved from My case summary).
 */
import React from 'react';
import { Link, useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { RelocationTaskTracker } from '../../features/timeline/RelocationTaskTracker';

const backLinkClass =
  'inline-flex font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#0b2b43] border-2 border-[#0b2b43] text-[#0b2b43] hover:bg-[#e6f2f4] px-3 py-1.5 text-sm';

export const EmployeeRelocationPlanPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const assignmentId = caseId;

  return (
    <AppShell title="Relocation plan" subtitle="Your shared checklist with HR for this assignment.">
      <div className="mb-4">
        <Link
          to={assignmentId ? `/employee/case/${assignmentId}/summary` : '/employee/dashboard'}
          className={backLinkClass}
        >
          ← Back to My case
        </Link>
      </div>
      {assignmentId ? (
        <RelocationTaskTracker
          assignmentId={assignmentId}
          deferredEnsureWhenEmpty
          title="Your relocation plan & actions"
        />
      ) : (
        <p className="text-sm text-[#64748b]">Select an assignment from your dashboard to view your plan.</p>
      )}
    </AppShell>
  );
};
