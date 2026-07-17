/**
 * Employee Benefit Comparison dashboard (P3-2 / AIQ-237).
 *
 * Progressive disclosure: KPI tiles → per-category table → out-of-pocket
 * summary → policy footer. Data comes from the comparison engine via
 * `employeeAPI.getPolicyServiceComparison`; this component is presentational
 * and never fabricates numbers (see benefitComparisonModel).
 */
import React, { useMemo, useState } from 'react';
import { Button } from '../../components/antigravity/Button';
import { Badge, Card } from '../../components/antigravity';
import type { EffectiveServiceComparisonRow } from '../../types';
import { RequestExceptionModal } from '../exceptions/RequestExceptionModal';
import type { ExceptionRequest } from '../../api/exceptions';
import {
  buildKpis,
  formatMoney,
  isPolicyExpired,
  mapComparisonRows,
  outOfPocketRows,
  type ComparisonRow,
  type CoverageBadge,
} from './benefitComparisonModel';

export interface PolicyFooter {
  companyName?: string | null;
  version?: number | null;
  effectiveDate?: string | null;
  expiryDate?: string | null;
}

const BADGE_VARIANT: Record<CoverageBadge, 'success' | 'warning' | 'error' | 'neutral'> = {
  covered: 'success',
  partial: 'warning',
  uncovered: 'error',
  info: 'neutral',
};

function KpiTile({
  label,
  value,
  hint,
  emphasis,
}: {
  label: string;
  value: string;
  hint?: string;
  emphasis?: 'danger' | 'default';
}) {
  return (
    <Card padding="lg" className="border-[#e2e8f0] bg-white">
      <div className="text-xs font-medium uppercase tracking-wide text-[#64748b]">{label}</div>
      <div
        className={`mt-2 text-3xl font-bold leading-tight tabular-nums ${
          emphasis === 'danger' ? 'text-[#b91c1c]' : 'text-[#0b2b43]'
        }`}
      >
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-[#94a3b8]">{hint}</div>}
    </Card>
  );
}

function CoverageCell({ row }: { row: ComparisonRow }) {
  return (
    <Badge variant={BADGE_VARIANT[row.coverage]} size="sm">
      {row.coverageLabel}
    </Badge>
  );
}

export const BenefitComparisonDashboard: React.FC<{
  rows: EffectiveServiceComparisonRow[];
  caseId: string | null;
  policy?: PolicyFooter | null;
  /** Injectable for tests; defaults to current time at render. */
  now?: Date;
}> = ({ rows, caseId, policy, now }) => {
  const mapped = useMemo(() => mapComparisonRows(rows), [rows]);
  const kpis = useMemo(() => buildKpis(mapped), [mapped]);
  const oopRows = useMemo(() => outOfPocketRows(mapped), [mapped]);
  const expired = isPolicyExpired(policy?.expiryDate, now ?? new Date());

  const [exceptionFor, setExceptionFor] = useState<ComparisonRow | null>(null);
  const [requested, setRequested] = useState<Set<string>>(new Set());
  // AIQ-1477: page-level "ask for more" request, not tied to a specific over-cap row.
  const [generalOpen, setGeneralOpen] = useState(false);

  if (!mapped.length) {
    return (
      <Card padding="lg" className="border-[#e2e8f0] bg-[#f8fafc]">
        <p className="text-sm text-[#475569]">
          No services to compare yet. Once you select services and add estimates in the Services
          flow, your coverage and out-of-pocket view appears here.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {expired && (
        <div
          role="alert"
          className="rounded-lg border border-amber-200 bg-amber-50/90 px-4 py-3 text-sm text-amber-950"
        >
          <span className="font-semibold">Heads up:</span> your company&apos;s relocation policy has
          expired. The figures below may not reflect your current coverage — contact HR before
          relying on them.
        </div>
      )}

      {/* (1) KPI tiles — large typography for scannability */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <KpiTile
          label="Total policy allocation"
          value={formatMoney(kpis.totalAllocation, kpis.currency)}
          hint="What your company has committed to cover"
        />
        <KpiTile
          label="Total service ask"
          value={formatMoney(kpis.totalAsk, kpis.currency)}
          hint="Your estimated cost across selected services"
        />
        <KpiTile
          label="Estimated out-of-pocket"
          value={formatMoney(kpis.outOfPocket, kpis.currency)}
          emphasis={kpis.outOfPocket > 0 ? 'danger' : 'default'}
          hint={kpis.outOfPocket > 0 ? 'The portion you would pay yourself' : 'Nothing over cap so far'}
        />
      </div>

      {kpis.hasUncomparable && (
        <p className="text-xs text-[#64748b]">
          Some items can&apos;t be compared numerically yet (your policy doesn&apos;t define a
          comparable limit for them). Totals above reflect only what we can compare with confidence.
        </p>
      )}

      {/* AIQ-1477: page-level "ask for more" CTA + instructions. The per-row "Request
          exception" action only appears for over-cap/uncovered rows and was easy to miss,
          so surface the capability prominently. Reuses the existing modal + endpoint. */}
      {caseId && (
        <Card padding="lg" className="border-[#e2e8f0] bg-[#f8fafc]">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-sm font-semibold text-[#0b2b43]">Need something that isn&apos;t covered?</div>
              <p className="mt-0.5 text-sm text-[#475569]">
                You can ask HR for a policy exception — for a benefit that&apos;s over your cap, not
                covered, or anything else you need. HR reviews each request and you&apos;ll see the
                decision here.
              </p>
            </div>
            <Button type="button" onClick={() => setGeneralOpen(true)} className="shrink-0">
              Request an exception
            </Button>
          </div>
        </Card>
      )}

      {/* (2) Per-category table */}
      <Card padding="none" className="overflow-hidden border-[#e2e8f0]">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="bg-[#f8fafc] text-xs uppercase tracking-wide text-[#64748b]">
              <tr>
                <th className="px-4 py-3 font-medium">Category</th>
                <th className="px-4 py-3 font-medium">Policy cap</th>
                <th className="px-4 py-3 font-medium">Your ask</th>
                <th className="px-4 py-3 font-medium">Coverage</th>
                <th className="px-4 py-3 font-medium">Delta</th>
                <th className="px-4 py-3 font-medium">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#f1f5f9]">
              {mapped.map((row) => {
                const overCap = row.delta != null && row.delta > 0;
                return (
                  <tr key={row.serviceKey} className="align-top">
                    <td className="px-4 py-3">
                      <div className="font-medium text-[#0b2b43]">{row.label}</div>
                      <div className="mt-0.5 text-xs text-[#94a3b8]">{row.explanation}</div>
                    </td>
                    <td className="px-4 py-3 tabular-nums text-[#1e293b]">
                      {formatMoney(row.policyCap, row.currency)}
                    </td>
                    <td className="px-4 py-3 tabular-nums text-[#1e293b]">
                      {formatMoney(row.ask, row.currency)}
                    </td>
                    <td className="px-4 py-3">
                      <CoverageCell row={row} />
                      {row.approvalRequired && (
                        <div className="mt-1 text-xs text-[#92400e]">Approval required</div>
                      )}
                    </td>
                    <td
                      className={`px-4 py-3 tabular-nums ${
                        overCap ? 'font-semibold text-[#b91c1c]' : 'text-[#64748b]'
                      }`}
                    >
                      {row.delta == null
                        ? '—'
                        : overCap
                          ? `+${formatMoney(row.delta, row.currency)}`
                          : formatMoney(row.delta, row.currency)}
                    </td>
                    <td className="px-4 py-3">
                      {row.canRequestException ? (
                        requested.has(row.serviceKey) ? (
                          <span className="text-xs text-[#1f8e8b]">Request sent</span>
                        ) : (
                          <Button unstyled
                            type="button"
                            onClick={() => setExceptionFor(row)}
                            className="rounded-md border border-[#0b2b43] px-3 py-1.5 text-xs font-medium text-[#0b2b43] transition-colors hover:bg-[#0b2b43] hover:text-white"
                          >
                            Request exception
                          </Button>
                        )
                      ) : (
                        <span className="text-xs text-[#cbd5e1]">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* (3) Out-of-pocket summary — only Partial / Uncovered categories */}
      {oopRows.length > 0 && (
        <section aria-labelledby="oop-heading">
          <h2 id="oop-heading" className="mb-2 text-sm font-semibold text-[#0b2b43]">
            Where you may pay out of pocket
          </h2>
          <Card padding="lg" className="border-[#e2e8f0] bg-white">
            <ul className="divide-y divide-[#f1f5f9]">
              {oopRows.map((row) => (
                <li key={row.serviceKey} className="flex items-center justify-between gap-4 py-2.5">
                  <div className="min-w-0">
                    <div className="font-medium text-[#0b2b43]">{row.label}</div>
                    <div className="text-xs text-[#94a3b8]">
                      {row.coverage === 'uncovered'
                        ? 'Not covered by your policy'
                        : 'Above your policy cap'}
                    </div>
                  </div>
                  <div className="shrink-0 text-right tabular-nums font-semibold text-[#b91c1c]">
                    {row.outOfPocket != null ? formatMoney(row.outOfPocket, row.currency) : 'TBD'}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        </section>
      )}

      {/* (5) Policy version + effective date footer — always visible */}
      <footer className="border-t border-[#e2e8f0] pt-3 text-xs text-[#94a3b8]">
        {policy && (policy.version != null || policy.effectiveDate || policy.companyName) ? (
          <>
            Based on {policy.companyName ? `${policy.companyName} ` : ''}relocation policy
            {policy.version != null ? ` v${policy.version}` : ''}
            {policy.effectiveDate ? `, effective ${String(policy.effectiveDate).slice(0, 10)}` : ''}.
          </>
        ) : (
          'Based on your company’s published relocation policy.'
        )}
      </footer>

      {exceptionFor && caseId && (
        <RequestExceptionModal
          open
          caseId={caseId}
          category={exceptionFor.serviceKey}
          categoryLabel={exceptionFor.label}
          // These are the policy's own numbers, in the policy's own currency — NOT USD.
          // They were previously passed through props named `…Usd` into a modal that sent a
          // hardcoded 'USD', so a 25,000 NOK cap reached HR as $25,000.
          requestedAmount={exceptionFor.ask ?? 0}
          capAmount={exceptionFor.policyCap ?? 0}
          currency={exceptionFor.currency}
          // The engine already told us which this is; don't re-infer it from the cap value.
          // 'partial' = exceeds_envelope (a cap exists and is exceeded) -> cap_override.
          // 'uncovered' = excluded (no such benefit in the package)     -> new_category.
          exceptionType={exceptionFor.coverage === 'uncovered' ? 'new_category' : 'cap_override'}
          displayRequested={formatMoney(exceptionFor.ask, exceptionFor.currency)}
          displayCap={formatMoney(exceptionFor.policyCap, exceptionFor.currency)}
          onClose={() => setExceptionFor(null)}
          onSuccess={(_req: ExceptionRequest) => {
            setRequested((prev) => new Set(prev).add(exceptionFor.serviceKey));
            setExceptionFor(null);
          }}
        />
      )}

      {/* AIQ-1477: general "ask for more" request from the page-level CTA. */}
      {generalOpen && caseId && (
        <RequestExceptionModal
          open
          caseId={caseId}
          category="other"
          categoryLabel="Other / general request"
          // A general ask names no benefit and no amounts by design; the reason carries it.
          requestedAmount={0}
          capAmount={0}
          currency="USD"
          exceptionType="new_category"
          displayRequested="—"
          displayCap="—"
          generalRequest
          onClose={() => setGeneralOpen(false)}
          onSuccess={(_req: ExceptionRequest) => setGeneralOpen(false)}
        />
      )}
    </div>
  );
};
