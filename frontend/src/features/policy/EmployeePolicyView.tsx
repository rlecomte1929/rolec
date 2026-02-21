import React, { useState, useEffect } from 'react';
import { Card } from '../../components/antigravity';
import { employeeAPI } from '../../api/client';

const BENEFIT_ICONS: Record<string, React.ReactNode> = {
  temporaryHousing: (
    <svg className="w-5 h-5 text-[#0b2b43] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  ),
  educationSupport: (
    <svg className="w-5 h-5 text-[#0b2b43] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      <line x1="8" y1="7" x2="16" y2="7" />
      <line x1="8" y1="11" x2="16" y2="11" />
    </svg>
  ),
  shipment: (
    <svg className="w-5 h-5 text-[#0b2b43] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="1" y="3" width="15" height="13" />
      <polygon points="16 8 20 8 23 11 23 16 16 16 16 8" />
      <circle cx="5.5" cy="18.5" r="2.5" />
      <circle cx="18.5" cy="18.5" r="2.5" />
    </svg>
  ),
  houseHunting: (
    <svg className="w-5 h-5 text-[#0b2b43] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  ),
  taxAssistance: (
    <svg className="w-5 h-5 text-[#0b2b43] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <line x1="12" y1="1" x2="12" y2="23" />
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </svg>
  ),
  spousalSupport: (
    <svg className="w-5 h-5 text-[#0b2b43] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  languageTraining: (
    <svg className="w-5 h-5 text-[#0b2b43] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  ),
  travel: (
    <svg className="w-5 h-5 text-[#0b2b43] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
      <line x1="12" y1="11" x2="12" y2="17" />
    </svg>
  ),
};

const getBenefitIcon = (key: string) => BENEFIT_ICONS[key] ?? null;

interface AllowedBenefit {
  key: string;
  label: string;
  allowed: boolean;
  maxAllowed: { min?: number; medium?: number; extensive?: number; premium?: number };
  currency: string;
  preApprovalRequired: boolean;
  documentationRequired: string[];
  explanatoryText: string;
}

interface ApplicablePolicy {
  policy: {
    policyId: string;
    policyName: string;
    effectiveDate: string;
    employeeBands: string[];
    assignmentTypes: string[];
  } | null;
  allowedBenefits: AllowedBenefit[];
  wizardCriteria: Record<string, unknown>;
  employeeBand?: string;
  assignmentType?: string;
}

export const EmployeePolicyView: React.FC<{
  assignmentId?: string;
  compact?: boolean;
}> = ({ assignmentId, compact }) => {
  const [data, setData] = useState<ApplicablePolicy | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    employeeAPI
      .getApplicablePolicy(assignmentId)
      .then((res) => {
        if (!cancelled) setData(res as unknown as ApplicablePolicy);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [assignmentId]);

  if (loading) return <div className="text-sm text-[#6b7280] py-8">Loading policy...</div>;
  if (!data) return null;
  if (!data.policy || data.allowedBenefits.length === 0) {
    return (
      <Card padding="lg">
        <p className="text-[#4b5563]">
          No matching policy has been published for your band and assignment type yet. Contact HR to confirm your benefit limits.
        </p>
      </Card>
    );
  }

  const formatTier = (ma: AllowedBenefit['maxAllowed']) => {
    const parts: string[] = [];
    if (ma.min != null && ma.min > 0) parts.push(`Min: ${ma.min.toLocaleString()}`);
    if (ma.medium != null && ma.medium > 0) parts.push(`Med: ${ma.medium.toLocaleString()}`);
    if (ma.extensive != null && ma.extensive > 0) parts.push(`Ext: ${ma.extensive.toLocaleString()}`);
    if (ma.premium != null && ma.premium > 0) parts.push(`Prem: ${ma.premium.toLocaleString()}`);
    return parts.join(' · ') || '—';
  };

  if (compact) {
    return (
      <Card padding="md" className="bg-[#eef4f8] border border-[#0b2b43]/20">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-[#0b2b43]">
              Your policy: {data.policy.policyName}
            </div>
            <div className="text-xs text-[#6b7280] mt-0.5">
              {data.employeeBand} · {data.assignmentType} · {data.allowedBenefits.length} benefits
            </div>
          </div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-sm text-[#0b2b43] hover:underline"
          >
            {expanded ? 'Hide' : 'View details'}
          </button>
        </div>
        {expanded && (
          <div className="mt-4 pt-4 border-t border-[#0b2b43]/20 space-y-2">
            {data.allowedBenefits.map((b) => (
              <div key={b.key} className="text-sm flex items-center gap-2">
                {getBenefitIcon(b.key)}
                <span className="font-medium text-[#0b2b43]">{b.label}:</span>{' '}
                <span className="text-[#4b5563]">
                  {b.currency} {formatTier(b.maxAllowed)}
                  {b.preApprovalRequired && ' · Pre-approval required'}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>
    );
  }

  return (
    <Card padding="lg">
      <h3 className="text-lg font-semibold text-[#0b2b43] mb-2">Applicable policy summary</h3>
      <div className="text-sm text-[#6b7280] mb-4">
        Employee band: {data.employeeBand || '—'} · Assignment: {data.assignmentType || '—'} · Effective:{' '}
        {data.policy.effectiveDate ? new Date(data.policy.effectiveDate).toLocaleDateString() : '—'}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#e2e8f0]">
              <th className="text-left py-2 pr-4">Benefit</th>
              <th className="text-left py-2 pr-4">Tier ranges</th>
              <th className="text-left py-2">Pre-approval</th>
            </tr>
          </thead>
          <tbody>
            {data.allowedBenefits.map((b) => (
              <tr key={b.key} className="border-b border-[#e2e8f0]">
                <td className="py-2 pr-4 font-medium text-[#0b2b43]">
                  <span className="flex items-center gap-2">
                    {getBenefitIcon(b.key)}
                    {b.label}
                  </span>
                </td>
                <td className="py-2 pr-4 text-[#4b5563]">
                  {b.currency} {formatTier(b.maxAllowed)}
                </td>
                <td className="py-2">{b.preApprovalRequired ? 'Yes' : 'No'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.allowedBenefits.some((b) => b.documentationRequired?.length) && (
        <div className="mt-4 pt-4 border-t border-[#e2e8f0]">
          <div className="text-xs font-semibold text-[#6b7280] mb-2">Required documentation</div>
          <ul className="text-sm text-[#4b5563] space-y-1">
            {data.allowedBenefits.flatMap((b) =>
              (b.documentationRequired || []).map((d) => (
                <li key={`${b.key}-${d}`}>
                  • {b.label}: {d}
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </Card>
  );
};
