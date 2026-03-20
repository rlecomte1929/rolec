import React, { useState, useEffect } from 'react';
import { Card } from '../../components/antigravity';
import { employeeAPI } from '../../api/client';
import {
  DISPLAY_CATEGORY_ORDER,
  DISPLAY_CATEGORY_LABELS,
  getBenefitDisplayCategory,
  formatBenefitLabel,
  type DisplayCategory,
} from './benefitCategories';

type CoverageStatus = 'covered' | 'partially_covered' | 'not_covered' | 'approval_required';

interface ResolvedBenefit {
  benefit_key: string;
  included: boolean;
  min_value?: number | null;
  standard_value?: number | null;
  max_value?: number | null;
  currency?: string;
  amount_unit?: string;
  frequency?: string;
  approval_required: boolean;
  evidence_required_json?: string[];
  exclusions_json?: Array<{ domain?: string; description?: string }>;
  condition_summary?: string;
}

interface ResolvedExclusion {
  benefit_key?: string;
  domain: string;
  description?: string;
}

interface ResolvedPolicyResponse {
  has_policy?: boolean;
  policy: { id: string; title: string; version: number; effective_date: string; company_name?: string | null } | null;
  benefits: ResolvedBenefit[];
  exclusions: ResolvedExclusion[];
  resolved_at?: string;
  resolution_context?: {
    assignment_type?: string;
    family_status?: string;
    tier?: string;
  };
  message?: string;
}

interface CategoryCardData {
  category: DisplayCategory;
  benefits: ResolvedBenefit[];
  coverageStatus: CoverageStatus;
  valueCap: string | null;
  conditionsSummary: string | null;
  exclusionsSummary: string | null;
  evidence: string[];
  plainLanguageSentence: string | null;
}

function formatDate(val: string | null | undefined): string {
  if (!val) return '—';
  try {
    return new Date(val).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return val;
  }
}

function formatValue(b: ResolvedBenefit): string | null {
  const cur = b.currency || 'USD';
  const vals = [b.min_value, b.standard_value, b.max_value].filter((v) => v != null && v > 0) as number[];
  if (vals.length === 0) return null;
  const max = Math.max(...vals);
  return `${cur} ${max.toLocaleString()}${b.amount_unit ? ` ${b.amount_unit}` : ''}${b.frequency ? ` per ${b.frequency}` : ''}`;
}

function deriveCoverageStatus(benefits: ResolvedBenefit[]): CoverageStatus {
  const anyExcluded = benefits.some((b) => !b.included);
  const anyApproval = benefits.some((b) => b.included && b.approval_required);
  const anyCovered = benefits.some((b) => b.included && !b.approval_required);
  const anyPartial = benefits.some((b) => b.included && (b.min_value != null || b.max_value != null));

  if (anyExcluded && !anyCovered && !anyApproval) return 'not_covered';
  if (anyApproval && !anyCovered) return 'approval_required';
  if (anyPartial && anyExcluded) return 'partially_covered';
  if (anyCovered || anyApproval) return anyApproval ? 'approval_required' : 'covered';
  return 'not_covered';
}

function buildCategoryCards(benefits: ResolvedBenefit[], exclusions: ResolvedExclusion[]): CategoryCardData[] {
  const byCategory = new Map<DisplayCategory, ResolvedBenefit[]>();
  for (const b of benefits) {
    const cat = getBenefitDisplayCategory(b.benefit_key);
    const list = byCategory.get(cat) ?? [];
    list.push(b);
    byCategory.set(cat, list);
  }

  const result: CategoryCardData[] = [];
  for (const cat of DISPLAY_CATEGORY_ORDER) {
    const list = byCategory.get(cat) ?? [];
    if (list.length === 0) continue;

    const status = deriveCoverageStatus(list);
    const includedList = list.filter((b) => b.included);
    const valueCap = includedList.length
      ? formatValue(includedList.find((b) => (b.max_value ?? b.standard_value ?? b.min_value) != null) ?? includedList[0]) ?? null
      : null;

    const condParts = [...new Set(list.map((b) => b.condition_summary).filter(Boolean))] as string[];
    const conditionsSummary = condParts.length ? condParts.join('. ') : null;

    const exclParts = list.flatMap((b) => (b.exclusions_json ?? []).map((e) => e.description || e.domain).filter(Boolean));
    const globalExcl = exclusions.filter((e) => !e.benefit_key || list.some((lb) => lb.benefit_key === e.benefit_key));
    exclParts.push(...globalExcl.map((e) => e.description || e.domain).filter(Boolean));
    const exclusionsSummary = exclParts.length ? [...new Set(exclParts)].join('. ') : null;

    const evidence = [...new Set(list.flatMap((b) => (b.evidence_required_json ?? []).filter(Boolean)))];

    let plainLanguage: string | null = null;
    if (status === 'covered' && valueCap) {
      plainLanguage = `You are covered up to ${valueCap}.`;
    } else if (status === 'approval_required') {
      plainLanguage = 'Approval from your manager or HR is required before using this benefit.';
    } else if (status === 'not_covered') {
      plainLanguage = 'This benefit is not included in your assignment policy.';
    } else if (status === 'partially_covered') {
      plainLanguage = `Partially covered. ${valueCap ? `Cap: ${valueCap}.` : ''} Some items may be excluded.`;
    }

    result.push({
      category: cat,
      benefits: list,
      coverageStatus: status,
      valueCap,
      conditionsSummary,
      exclusionsSummary,
      evidence,
      plainLanguageSentence: plainLanguage,
    });
  }
  return result;
}

function getStatusBadge(status: CoverageStatus) {
  const styles: Record<CoverageStatus, { bg: string; text: string; label: string }> = {
    covered: { bg: 'bg-[#dcfce7]', text: 'text-[#166534]', label: 'Covered' },
    partially_covered: { bg: 'bg-[#fef3c7]', text: 'text-[#92400e]', label: 'Partially covered' },
    not_covered: { bg: 'bg-[#fee2e2]', text: 'text-[#991b1b]', label: 'Not covered' },
    approval_required: { bg: 'bg-[#dbeafe]', text: 'text-[#1e40af]', label: 'Approval required' },
  };
  const s = styles[status];
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${s.bg} ${s.text}`}>
      {s.label}
    </span>
  );
}

const CATEGORY_ICONS: Record<DisplayCategory, React.ReactNode> = {
  housing: (
    <svg className="w-5 h-5 text-[#0b2b43] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  ),
  movers: (
    <svg className="w-5 h-5 text-[#0b2b43] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="1" y="3" width="15" height="13" />
      <polygon points="16 8 20 8 23 11 23 16 16 16 16 8" />
      <circle cx="5.5" cy="18.5" r="2.5" />
      <circle cx="18.5" cy="18.5" r="2.5" />
    </svg>
  ),
  schooling: (
    <svg className="w-5 h-5 text-[#0b2b43] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      <line x1="8" y1="7" x2="16" y2="7" />
      <line x1="8" y1="11" x2="16" y2="11" />
    </svg>
  ),
  immigration: (
    <svg className="w-5 h-5 text-[#0b2b43] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  travel: (
    <svg className="w-5 h-5 text-[#0b2b43] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
      <line x1="12" y1="11" x2="12" y2="17" />
    </svg>
  ),
  banking: (
    <svg className="w-5 h-5 text-[#0b2b43] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
      <line x1="1" y1="10" x2="23" y2="10" />
    </svg>
  ),
  medical: (
    <svg className="w-5 h-5 text-[#0b2b43] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  ),
  tax_other: (
    <svg className="w-5 h-5 text-[#0b2b43] flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="12" y1="1" x2="12" y2="23" />
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </svg>
  ),
};

export const EmployeeResolvedPolicyView: React.FC<{
  /** Legacy: fetch GET /api/employee/assignments/:id/policy */
  assignmentId?: string;
  /** Preferred on employee package page: data from GET /api/employee/me/assignment-package-policy (status=found) */
  resolvedSnapshot?: ResolvedPolicyResponse | null;
}> = ({ assignmentId, resolvedSnapshot }) => {
  const [data, setData] = useState<ResolvedPolicyResponse | null>(resolvedSnapshot ?? null);
  const [loading, setLoading] = useState(() => !resolvedSnapshot && Boolean(assignmentId));

  useEffect(() => {
    if (resolvedSnapshot) {
      setData(resolvedSnapshot);
      setLoading(false);
      return;
    }
    if (!assignmentId) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    employeeAPI
      .getResolvedPolicy(assignmentId)
      .then((res) => {
        if (!cancelled) setData(res as ResolvedPolicyResponse);
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
  }, [assignmentId, resolvedSnapshot]);

  if (loading) {
    return <div className="text-sm text-[#6b7280] py-8">Loading your policy…</div>;
  }

  if (!assignmentId && !resolvedSnapshot) {
    return null;
  }

  const hasPolicy = Boolean(data?.has_policy !== false && data?.policy?.id);
  if (!hasPolicy) {
    return (
      <Card padding="lg">
        <div className="text-center py-8">
          <p className="text-[#4b5563] font-medium">
            Your company has not yet published an assignment policy for this case.
          </p>
          <p className="text-sm text-[#6b7280] mt-2">
            Once HR publishes a policy that applies to your assignment, your benefits and limits will appear here.
          </p>
        </div>
      </Card>
    );
  }

  if (!data) {
    return null;
  }

  const policy = data.policy;
  if (!policy) {
    return (
      <Card padding="lg">
        <div className="text-center py-8 text-sm text-[#6b7280]">No policy details available.</div>
      </Card>
    );
  }
  const ctx = data.resolution_context ?? {};
  const assignmentType = ctx.assignment_type ? String(ctx.assignment_type).toUpperCase() : null;
  const benefitsList = data.benefits ?? [];
  const exclusionsList = data.exclusions ?? [];
  const cards = buildCategoryCards(benefitsList, exclusionsList);

  const included = benefitsList.filter((b) => b.included && !b.approval_required).map((b) => formatBenefitLabel(b.benefit_key));
  const approvalRequired = benefitsList.filter((b) => b.included && b.approval_required).map((b) => formatBenefitLabel(b.benefit_key));
  const notCovered = benefitsList.filter((b) => !b.included).map((b) => formatBenefitLabel(b.benefit_key));

  return (
    <div className="space-y-6">
      {/* Summary banner — read-only; company name + contact HR */}
      <Card padding="lg" className="bg-[#eef4f8] border border-[#0b2b43]/20">
        <div className="text-sm font-semibold text-[#0b2b43] mb-2">{policy.title}</div>
        {policy.company_name && (
          <div className="text-sm text-[#6b7280] mb-1">Company: {policy.company_name}</div>
        )}
        <div className="text-sm text-[#6b7280] flex flex-wrap gap-x-3 gap-y-1">
          {assignmentType && <span>Assignment type: {assignmentType}</span>}
          <span>Effective: {formatDate(policy.effective_date)}</span>
          {policy.version != null && <span>Version {policy.version}</span>}
        </div>
        <p className="text-sm text-[#4b5563] mt-3">
          This is the policy currently applied to your assignment. Questions about interpretation? Contact your HR representative through Messages.
        </p>
        {benefitsList.length === 0 && (
          <p className="text-sm text-[#6b7280] mt-3 border-t border-[#e2e8f0] pt-3">
            Your policy is linked, but no benefit limits matched your assignment profile yet. HR can add or publish benefit rules that apply to your assignment type and family status.
          </p>
        )}
      </Card>

      {/* Interpretation section */}
      <Card padding="lg">
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">Summary</div>
        <div className="grid gap-4 sm:grid-cols-3">
          {included.length > 0 && (
            <div>
              <div className="text-xs font-medium text-[#059669] mb-1">Included</div>
              <ul className="text-sm text-[#4b5563] list-disc list-inside space-y-0.5">
                {included.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </div>
          )}
          {approvalRequired.length > 0 && (
            <div>
              <div className="text-xs font-medium text-[#1e40af] mb-1">Approval required</div>
              <ul className="text-sm text-[#4b5563] list-disc list-inside space-y-0.5">
                {approvalRequired.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </div>
          )}
          {notCovered.length > 0 && (
            <div>
              <div className="text-xs font-medium text-[#991b1b] mb-1">Not covered</div>
              <ul className="text-sm text-[#4b5563] list-disc list-inside space-y-0.5">
                {notCovered.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
        {included.length === 0 && approvalRequired.length === 0 && notCovered.length === 0 && (
          <p className="text-sm text-[#6b7280]">No benefit categories resolved yet.</p>
        )}
      </Card>

      {/* Category cards */}
      <div className="space-y-4">
        {cards.map((card) => (
          <Card key={card.category} padding="lg">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 mt-0.5">{CATEGORY_ICONS[card.category]}</div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span className="font-semibold text-[#0b2b43]">{DISPLAY_CATEGORY_LABELS[card.category]}</span>
                  {getStatusBadge(card.coverageStatus)}
                </div>
                {card.valueCap && (
                  <div className="text-sm text-[#4b5563] mb-1">Cap: {card.valueCap}</div>
                )}
                {card.conditionsSummary && (
                  <div className="text-xs text-[#6b7280] mb-1">
                    <span className="font-medium">Conditions: </span>{card.conditionsSummary}
                  </div>
                )}
                {card.exclusionsSummary && (
                  <div className="text-xs text-[#991b1b] mb-1">
                    <span className="font-medium">Exclusions: </span>{card.exclusionsSummary}
                  </div>
                )}
                {card.evidence.length > 0 && (
                  <div className="text-xs text-[#6b7280] mb-1">
                    <span className="font-medium">Required evidence: </span>
                    {card.evidence.join(', ')}
                  </div>
                )}
                {card.plainLanguageSentence && (
                  <div className="text-sm text-[#0b2b43] mt-2 pt-2 border-t border-[#e2e8f0] italic">
                    What this means for you: {card.plainLanguageSentence}
                  </div>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
};
