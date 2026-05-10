import React, { useEffect, useMemo, useState } from 'react';
import { hrAPI } from '../../api/client';
import { benefitKeyForProviderService, humanizeServiceKey } from './providerServiceBenefitMap';
import { PolicyCapEstimateRow } from './PolicyCapEstimateRow';
import type { PolicyCapCompareResultRow } from './policyCapCompareTypes';
import { usePolicyCapsCompare } from './usePolicyCapsCompare';

type SvcRow = {
  key: string;
  service_key: string;
  label: string;
  estimate: number | null;
  currency: string;
  benefit_key: string | null;
};

export const HrAssignmentServicesCapPanel: React.FC<{ assignmentId: string }> = ({ assignmentId }) => {
  const [loadingSvc, setLoadingSvc] = useState(true);
  const [svcError, setSvcError] = useState<string | null>(null);
  const [rows, setRows] = useState<SvcRow[]>([]);
  const [assignmentType, setAssignmentType] = useState<string | null>(null);
  const [familyStatus, setFamilyStatus] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoadingSvc(true);
    setSvcError(null);
    void (async () => {
      try {
        const [svcRes, polRes] = await Promise.all([
          hrAPI.getAssignmentServices(assignmentId),
          hrAPI.getResolvedPolicy(assignmentId),
        ]);
        if (cancelled) return;
        const rc = (polRes.resolution_context || {}) as {
          assignment_type?: string;
          family_status?: string;
        };
        setAssignmentType(rc.assignment_type ?? null);
        setFamilyStatus(rc.family_status ?? null);

        const list = svcRes.services ?? [];
        const next: SvcRow[] = list
          .filter((s) => s.selected === true || s.selected === 1)
          .map((s) => ({
            key: s.id || s.service_key,
            service_key: s.service_key,
            label: humanizeServiceKey(s.service_key),
            estimate: s.estimated_cost != null ? Number(s.estimated_cost) : null,
            currency: (s.currency || 'USD').trim() || 'USD',
            benefit_key: benefitKeyForProviderService(s.service_key),
          }));
        setRows(next);
      } catch (e: unknown) {
        if (!cancelled) {
          setSvcError(e instanceof Error ? e.message : 'Failed to load services');
          setRows([]);
        }
      } finally {
        if (!cancelled) setLoadingSvc(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [assignmentId]);

  const estimates = useMemo(
    () =>
      rows
        .filter((r) => r.estimate != null && Number.isFinite(r.estimate) && r.benefit_key)
        .map((r) => ({
          benefit_key: r.benefit_key!,
          amount: r.estimate!,
          currency: r.currency,
        })),
    [rows]
  );

  const { results, loading: cmpLoading, error: cmpError } = usePolicyCapsCompare({
    enabled: estimates.length > 0,
    assignmentType,
    familyStatus,
    estimates,
  });

  const paired = useMemo(() => {
    let j = 0;
    return rows.map((row) => {
      if (row.estimate == null || !Number.isFinite(row.estimate)) {
        return {
          row,
          mode: 'no_estimate' as const,
          result: undefined as PolicyCapCompareResultRow | null | undefined,
        };
      }
      if (!row.benefit_key) {
        return { row, mode: 'unmapped' as const, result: undefined };
      }
      if (cmpLoading) {
        return { row, mode: 'compare' as const, result: null };
      }
      const r = results?.[j++];
      return { row, mode: 'compare' as const, result: r ?? null };
    });
  }, [rows, results, cmpLoading]);

  if (loadingSvc) {
    return <div className="text-sm text-[#6b7280]">Loading services and estimates…</div>;
  }
  if (svcError) {
    return <div className="text-sm text-red-600">{svcError}</div>;
  }
  if (rows.length === 0) {
    return (
      <div className="text-sm text-[#6b7280]">
        No relocation services selected for this assignment yet.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-[#64748b]">
        Provider estimates from the employee services flow are compared to published policy caps (HR view
        only).
      </p>
      {cmpError ? <div className="text-xs text-red-600">{cmpError}</div> : null}
      {paired.map(({ row, mode, result }) => {
        if (mode === 'no_estimate') {
          return (
            <div
              key={row.key}
              className="rounded-lg border border-[#e2e8f0] bg-white p-3 text-sm text-[#6b7280]"
            >
              <div className="font-medium text-[#0b2b43]">{row.label}</div>
              <div className="mt-1 text-xs">No provider estimate entered for this service.</div>
            </div>
          );
        }
        if (mode === 'unmapped') {
          return (
            <PolicyCapEstimateRow
              key={row.key}
              title={row.label}
              subtitle="Employee services estimate"
              unmapped
              estimateAmount={row.estimate!}
              estimateCurrency={row.currency}
            />
          );
        }
        return (
          <PolicyCapEstimateRow
            key={row.key}
            title={row.label}
            subtitle="Employee services estimate"
            result={result ?? null}
            estimateAmount={row.estimate!}
            estimateCurrency={row.currency}
          />
        );
      })}
    </div>
  );
};
