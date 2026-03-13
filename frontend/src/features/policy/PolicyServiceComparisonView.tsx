import React from 'react';
import { Card } from '../../components/antigravity';
import type { PolicyServiceComparisonItem, PolicyStatus } from '../../types';

const STATUS_LABELS: Record<PolicyStatus, string> = {
  included: 'Covered',
  capped: 'Covered up to cap',
  approval_required: 'Requires approval',
  partial: 'Partially covered',
  excluded: 'Not covered',
  out_of_scope: 'Out of scope',
};

const STATUS_STYLES: Record<PolicyStatus, string> = {
  included: 'bg-[#eaf5f4] text-[#1f8e8b]',
  capped: 'bg-[#fff7ed] text-[#9a3412]',
  approval_required: 'bg-[#fef3c7] text-[#92400e]',
  partial: 'bg-[#fef3c7] text-[#92400e]',
  excluded: 'bg-[#fef2f2] text-[#7a2a2a]',
  out_of_scope: 'bg-[#e2e8f0] text-[#4b5563]',
};

const formatCurrency = (value: number | undefined | null, currency = 'USD') => {
  const safe = typeof value === 'number' && isFinite(value) ? value : 0;
  return safe.toLocaleString('en-US', { style: 'currency', currency, maximumFractionDigits: 0 });
};

export const PolicyServiceComparisonView: React.FC<{
  comparisons: PolicyServiceComparisonItem[];
  resolvedAt?: string;
  showDiagnostics?: boolean;
  diagnostics?: { benefits_count: number; services_count: number; answers_keys: string[] };
  emptyMessage?: string;
}> = ({ comparisons, resolvedAt, showDiagnostics, diagnostics, emptyMessage }) => {
  if (!comparisons.length) {
    return (
      <Card padding="md" className="bg-[#f8fafc]">
        <p className="text-sm text-[#6b7280]">
          {emptyMessage ?? 'No selected services to compare. Select services and save your answers first.'}
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-2">
      {resolvedAt && (
        <div className="text-xs text-[#6b7280]">
          Resolved policy: {new Date(resolvedAt).toLocaleString()}
        </div>
      )}
      <div className="space-y-2">
        {comparisons.map((c) => (
          <div
            key={c.service_category}
            className="rounded-lg border border-[#e2e8f0] bg-white px-4 py-3"
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="font-medium text-[#0b2b43]">{c.label}</div>
                <span
                  className={`mt-1 inline-block rounded px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[c.policy_status] ?? STATUS_STYLES.out_of_scope}`}
                >
                  {STATUS_LABELS[c.policy_status] ?? c.policy_status}
                </span>
              </div>
              {(c.policy_max_value != null || c.policy_standard_value != null) && (
                <div className="text-right text-sm text-[#4b5563]">
                  Policy limit: {formatCurrency(c.policy_max_value ?? c.policy_standard_value, c.currency)}
                  {c.approval_required && ' · Pre-approval required'}
                </div>
              )}
            </div>
            <p className="mt-2 text-sm text-[#6b7280]">{c.explanation}</p>
            {showDiagnostics && c.variance_json && Object.keys(c.variance_json).length > 0 && (
              <div className="mt-2 rounded bg-[#f1f5f9] px-2 py-1.5 text-xs text-[#475569]">
                Variance: {JSON.stringify(c.variance_json)}
              </div>
            )}
            {c.evidence_required_json?.length > 0 && (
              <ul className="mt-2 list-inside list-disc text-xs text-[#6b7280]">
                {c.evidence_required_json.map((ev, i) => (
                  <li key={i}>{ev}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
      {showDiagnostics && diagnostics && (
        <div className="mt-3 rounded border border-[#e2e8f0] bg-[#f8fafc] px-3 py-2 text-xs text-[#6b7280]">
          <span className="font-medium">Diagnostics:</span> {diagnostics.benefits_count} benefits,{' '}
          {diagnostics.services_count} services, {diagnostics.answers_keys?.length ?? 0} answer keys
        </div>
      )}
    </div>
  );
};
