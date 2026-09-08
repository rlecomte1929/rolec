import React from 'react';

/**
 * Mock UI preview of a relocation case for the Platform hero.
 * Standalone component: does not replace or modify existing hero content.
 */
export const CasePreviewMock: React.FC<{ className?: string }> = ({ className = '' }) => {
  return (
    <div className={`relative max-w-md w-full ${className}`}>
      {/* Optional depth: faint background cards */}
      <div
        className="absolute -inset-1 rounded-[24px] bg-marketing-surface-muted/60 border border-marketing-border-subtle"
        aria-hidden
      />
      <div
        className="absolute -inset-0.5 rounded-[22px] bg-marketing-surface-subtle/80 border border-marketing-border-subtle"
        aria-hidden
      />

      {/* Main card */}
      <div className="relative rounded-[20px] border border-marketing-border bg-marketing-surface shadow-lg p-5 sm:p-6">
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-2 mb-5">
          <div>
            <p className="text-sm font-semibold text-marketing-primary">
              Marie Dubois: France to Singapore
            </p>
          </div>
          <span className="inline-flex items-center rounded-full bg-marketing-accent/12 px-2.5 py-1 text-xs font-medium text-marketing-accent">
            In progress
          </span>
        </div>

        {/* Progress */}
        <div className="mb-5">
          <p className="text-xs font-medium text-marketing-text-muted mb-1.5">
            Case progress
          </p>
          <div className="h-2 w-full rounded-full bg-marketing-surface-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-marketing-accent"
              style={{ width: '60%' }}
            />
          </div>
          <p className="mt-1.5 text-xs text-marketing-text-subtle">
            3 of 5 milestones completed
          </p>
        </div>

        {/* Main content: 2 columns */}
        <div className="grid grid-cols-2 gap-4 mb-5">
          <div className="space-y-2">
            <p className="text-xs font-medium text-marketing-text-muted">Documents & requirements</p>
            <ul className="space-y-1.5 text-xs text-marketing-primary">
              <li className="flex items-center gap-2">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-marketing-accent" />
                Passport uploaded
              </li>
              <li className="flex items-center gap-2">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-marketing-accent" />
                Eligibility review complete
              </li>
              <li className="flex items-center gap-2">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-marketing-border" />
                Lease support pending
              </li>
            </ul>
          </div>
          <div className="space-y-2">
            <p className="text-xs font-medium text-marketing-text-muted">Case details</p>
            <ul className="space-y-1.5 text-xs text-marketing-primary">
              <li>Singapore</li>
              <li>Family move</li>
              <li>Start date: 14 Apr</li>
            </ul>
          </div>
        </div>

        {/* Activity row */}
        <div className="pt-4 border-t border-marketing-border">
          <p className="text-xs font-medium text-marketing-text-muted mb-2">Recent activity</p>
          <ul className="space-y-1.5 text-xs text-marketing-text-subtle">
            <li>Service provider assigned</li>
            <li>Document request sent</li>
            <li>Review scheduled</li>
            <li>Awaiting housing provider update</li>
          </ul>
        </div>
      </div>
    </div>
  );
};
