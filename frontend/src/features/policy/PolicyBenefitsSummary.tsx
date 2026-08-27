import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Badge, Card, Select } from '../../components/antigravity';
import {
  policySummaryAPI,
  type PolicySummaryResponse,
  type PolicySummaryCategory,
  type PolicySummaryRow,
} from '../../api/policySummary';
import { HrNoCompanyOnboarding, isNoCompanyError } from './hrNoCompanyOnboarding';

// AIQ-225 (P1-5) — company policy "truth board". Read-only view of the active
// published policy, by category and tier. Always reflects the current published
// version; the backend computes the status banner and joins validator identity
// so the view never has to guess expiry logic or make a second round-trip.

function formatDate(val: string | null | undefined): string {
  if (!val) return '—';
  try {
    return new Date(val).toLocaleDateString('en-GB', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return val;
  }
}

// UX constraint: never show a benefit figure without its unit/currency.
// Monetary caps carry a currency (cap_unit null → fall back to cap_currency);
// count/duration caps carry a unit (e.g. "days", "nights"). Either way a bare
// number is never rendered.
function formatCap(row: PolicySummaryRow): string | null {
  if (row.cap_value === null || row.cap_value === undefined) return null;
  const num = row.cap_value.toLocaleString('en-GB');
  const unit = row.cap_unit || row.cap_currency;
  return unit ? `${num} ${unit}` : num;
}

function validationLine(row: PolicySummaryRow): string {
  if (row.validated_by_name) {
    return `Last validated by ${row.validated_by_name} on ${formatDate(row.validated_at)}`;
  }
  return 'Not yet validated';
}

const BANNER_COPY: Record<'under_review' | 'expired', string> = {
  under_review: 'This policy is currently under review. Contact HR for current guidance.',
  expired: 'This policy has expired. Contact HR for current guidance.',
};

const ALL_TIERS = '';

export const PolicyBenefitsSummary: React.FC<{ companyId?: string | null }> = ({ companyId }) => {
  const [data, setData] = useState<PolicySummaryResponse | null>(null);
  const [tierOptions, setTierOptions] = useState<{ value: string; label: string }[]>([]);
  const [tier, setTier] = useState<string>(ALL_TIERS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // [T2.4-ext] HR account not yet linked to a company → policy summary 403s.
  const [noCompany, setNoCompany] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setNoCompany(false);
    policySummaryAPI
      .get({ companyId: companyId ?? undefined, tier: tier || undefined })
      .then((res) => {
        if (cancelled) return;
        setData(res);
        // Populate the tier dropdown only from the unfiltered load so the
        // options don't collapse to the single selected tier after filtering.
        if (tier === ALL_TIERS) {
          const seen = new Map<string, string>();
          for (const cat of res.categories) {
            for (const row of cat.rows) {
              if (row.tier_name) seen.set(row.tier_name.toLowerCase(), row.tier_name);
            }
          }
          setTierOptions(
            Array.from(seen.values()).map((name) => ({ value: name, label: name })),
          );
        }
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        // [T2.4-ext] 403 = HR not linked to a company → onboarding, not an error.
        if (isNoCompanyError(e)) {
          setNoCompany(true);
          return;
        }
        const status = (e as { response?: { status?: number } })?.response?.status;
        setError(
          status === 400
            ? 'Select a company to view its policy summary.'
            : 'Could not load the policy summary. Please try again.',
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [companyId, tier]);

  const sortedCategories = useMemo<PolicySummaryCategory[]>(
    () => (data ? [...data.categories].sort((a, b) => a.sort_order - b.sort_order) : []),
    [data],
  );

  if (loading && !data) {
    return <div className="text-sm text-[#6b7280] py-8">Loading policy summary…</div>;
  }

  // [T2.4-ext] HR not linked to a company yet. Embedded in the /hr/policy tabs
  // (parent supplies AppShell), so render the card unwrapped.
  if (noCompany) {
    return <HrNoCompanyOnboarding />;
  }

  if (error) {
    return (
      <Alert variant="error" title="Policy summary unavailable">
        {error}
      </Alert>
    );
  }

  if (!data) return null;

  const { version, status_banner } = data;
  const showAmberBanner = status_banner === 'under_review' || status_banner === 'expired';

  return (
    <div className="space-y-4" data-testid="policy-benefits-summary">
      {/* Amber banner above the fold when the policy is not current. */}
      {showAmberBanner && (
        <Alert variant="warning" title="Policy not current">
          {BANNER_COPY[status_banner]}
        </Alert>
      )}

      {/* Version + effective date are always visible. */}
      <Card padding="md">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {version ? (
              <>
                <Badge variant={status_banner === 'active' ? 'success' : 'warning'} size="sm">
                  v{version.version_number} — {status_banner === 'active' ? 'active' : version.status}
                </Badge>
                <Badge variant="neutral" size="sm">
                  Effective {formatDate(version.effective_date)}
                </Badge>
                {version.expiry_date && (
                  <Badge variant="neutral" size="sm">
                    Expires {formatDate(version.expiry_date)}
                  </Badge>
                )}
              </>
            ) : (
              <Badge variant="neutral" size="sm">
                No published policy yet
              </Badge>
            )}
          </div>
          <div className="w-full sm:w-56">
            <Select
              label="Tier"
              value={tier}
              onChange={setTier}
              options={tierOptions}
              placeholder="All tiers"
              fullWidth
            />
          </div>
        </div>
      </Card>

      {status_banner === 'no_policy' ? (
        <Card padding="lg">
          <div className="text-sm text-[#6b7280]">
            No policy has been published yet. Once HR publishes a policy version, its benefits
            appear here automatically.
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {sortedCategories.map((cat) => (
            <Card key={cat.code} padding="none" className="overflow-hidden">
              <div className="px-4 py-3 border-b border-[#e2e8f0] bg-[#f8fafc] font-semibold text-[#0b2b43]">
                {cat.display_name}
              </div>
              {cat.rows.length === 0 ? (
                <div className="px-4 py-3 text-sm text-gray-500">No values set for this category.</div>
              ) : (
                // AIQ-1105: scannable table with explicit column headers (was a
                // header-less 3-col grid). overflow-x-auto keeps it usable on
                // narrow screens without dropping the header row.
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-sm">
                    <thead>
                      <tr className="border-b border-[#e2e8f0] text-left text-[11px] font-semibold uppercase tracking-wide text-[#6b7280]">
                        <th scope="col" className="px-4 py-2 font-semibold">Tier</th>
                        <th scope="col" className="px-4 py-2 font-semibold">Coverage</th>
                        <th scope="col" className="px-4 py-2 font-semibold">Notes</th>
                        <th scope="col" className="px-4 py-2 font-semibold text-right">Validated</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#eef2f7]">
                      {cat.rows.map((row, idx) => {
                        const cap = formatCap(row);
                        return (
                          <tr key={`${cat.code}-${row.tier_id ?? 'all'}-${idx}`} className="align-top">
                            <td className="px-4 py-3 whitespace-nowrap">
                              {row.tier_name ? (
                                <Badge variant="info" size="sm">
                                  {row.tier_name}
                                </Badge>
                              ) : (
                                <Badge variant="neutral" size="sm">
                                  All tiers
                                </Badge>
                              )}
                            </td>
                            <td className="px-4 py-3 font-medium text-[#0b2b43]">{cap ?? 'Not set'}</td>
                            <td className="px-4 py-3 text-xs text-[#6b7280]">{row.value_notes || '—'}</td>
                            {/* "Last validated by" line is mandatory on every row. */}
                            <td className="px-4 py-3 text-right text-xs text-[#6b7280] whitespace-nowrap">
                              {validationLine(row)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
