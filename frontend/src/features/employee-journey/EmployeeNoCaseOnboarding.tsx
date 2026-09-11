import React from 'react';
import { Card } from '../../components/antigravity';

/**
 * [TASK-024] Onboarding reassurance for an unlinked employee.
 * AIQ-2292 embeds this inside the single empty-state + claim card.
 */
export const EmployeeNoCaseOnboarding: React.FC<{ embedded?: boolean }> = ({ embedded = false }) => {
  const body = (
    <div data-testid="employee-no-case-onboarding">
      <div className="text-lg font-semibold text-[#0b2b43] mb-1">
        Your HR team is setting things up
      </div>
      <p className="text-sm text-[#4b5563]">
        Once your case is ready, you&apos;ll see your plan, documents, and next steps
        right here. Nothing&apos;s gone wrong — there&apos;s just nothing for you to do yet.
      </p>
      <p className="text-sm text-[#4b5563] mt-2">
        We&apos;ll email you when everything is in place.
      </p>
    </div>
  );

  if (embedded) return body;
  return (
    <Card padding="lg" className="mb-6 border border-[#e2e8f0] bg-[#f8fafc]">
      {body}
    </Card>
  );
};
