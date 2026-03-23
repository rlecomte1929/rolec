import React from 'react';
import type { HrPolicyPipelineDerived } from './hrPolicyDegradedState';
import { HR_POLICY_PIPELINE_COPY } from './hrPolicyDegradedState';

const VARIANT_STYLES: Record<
  (typeof HR_POLICY_PIPELINE_COPY)[keyof typeof HR_POLICY_PIPELINE_COPY]['variant'],
  string
> = {
  success: 'border-[#bbf7d0] bg-[#f0fdf4] text-[#166534]',
  info: 'border-[#bfdbfe] bg-[#eff6ff] text-[#1e40af]',
  warning: 'border-[#fcd34d] bg-[#fffbeb] text-[#92400e]',
  error: 'border-[#fecaca] bg-[#fef2f2] text-[#991b1b]',
  neutral: 'border-[#e2e8f0] bg-[#f8fafc] text-[#475569]',
};

export const HrPolicyPipelineBanner: React.FC<{
  derived: HrPolicyPipelineDerived;
  loading?: boolean;
}> = ({ derived, loading }) => {
  if (loading) {
    return (
      <div
        className="rounded-lg border border-[#fde68a] bg-[#fffbeb] px-4 py-3 text-sm text-[#92400e]"
        role="status"
        aria-live="polite"
      >
        <div className="font-medium text-[#0b2b43]">Loading your policy workspace…</div>
        <p className="text-xs text-[#78350f] mt-1">
          Pulling the latest published version, working draft, and cost-comparison status. This usually takes a moment.
        </p>
      </div>
    );
  }

  const copy = HR_POLICY_PIPELINE_COPY[derived.state];
  const box = VARIANT_STYLES[copy.variant];

  return (
    <div className={`rounded-lg border px-4 py-3 text-sm ${box}`} data-hr-policy-pipeline-state={derived.state}>
      <div className="font-semibold">{copy.title}</div>
      <p className="mt-1 opacity-95 leading-snug">{copy.body}</p>
      {derived.detail && (
        <p className="mt-2 text-xs text-[#64748b] break-words border-t border-black/10 pt-2 leading-snug">
          {derived.detail.replace(/_/g, ' ')}
        </p>
      )}
    </div>
  );
};
