import React from 'react';
import { Card } from '../../components/antigravity';

/**
 * [TASK-024] Onboarding reassurance shown on the employee dashboard when no case
 * is linked yet. Sets expectations to reduce the "did something go wrong?" anxiety
 * a blank dashboard creates.
 *
 * Scope note: the task brief assumed a passive no-CTA dead-end, but the real
 * no-case screen has a working case-code claim flow — so this panel sits ABOVE
 * that flow (kept) rather than replacing it. The "we'll email you" line is omitted
 * because no case-assignment email trigger exists, and the HR-contact link is
 * omitted because that data isn't available on this surface.
 */
export const EmployeeNoCaseOnboarding: React.FC = () => (
  <Card padding="lg" className="mb-6 border border-[#e2e8f0] bg-[#f8fafc]">
    <div data-testid="employee-no-case-onboarding">
      <div className="text-lg font-semibold text-[#0b2b43] mb-1">
        Your HR team is setting things up
      </div>
      <p className="text-sm text-[#4b5563]">
        Once your case is ready, you&apos;ll see your plan, documents, and next steps
        right here. Nothing&apos;s gone wrong — there&apos;s just nothing for you to do yet.
      </p>
      <p className="text-sm text-[#4b5563] mt-2">
        Already have a case code from HR? Link it below to get started now.
      </p>
    </div>
  </Card>
);
