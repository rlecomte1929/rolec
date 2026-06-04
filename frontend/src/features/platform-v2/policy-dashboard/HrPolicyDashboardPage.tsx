import { useCallback, useEffect, useMemo, useState } from 'react';
import { AppShell } from '../../../components/AppShell';
import { Breadcrumb } from '../../../components/Breadcrumb';
import { companyPolicyAPI, hrAPI } from '../../../api/client';
import {
  listExceptionRequestsForCompany,
  resolveExceptionRequest,
} from '../../../api/exceptions';
import type { ExceptionRequest } from '../../../api/exceptions';
import type { AssignmentSummary } from '../../../types';

/**
 * HR Aggregate Utilisation View & Exception Management Queue — P3-4 (AIQ-239).
 *
 * One operational control surface for HR built entirely on live data:
 *   1. Active-policy tile      ← companyPolicyAPI.getLatest()
 *   2. Employee compliance table ← hrAPI.listAssignments() ⨝ exception requests
 *   3. Exception queue (approve/reject) ← listExceptionRequestsForCompany() + resolveExceptionRequest()
 *   4. Category utilisation heatmap ← exception requests grouped by category
 *
 * Design decision (descope from the original P3-4 spec, approved in queue
 * triage): the "counter-offer" action is NOT offered — the backend PATCH
 * /api/exception-requests/{id} only accepts approved|reject (the P3-3 counter
 * branch was archived, never built). The cross-page real-time sync to the
 * employee Benefit Comparison dashboard (P3-2) is also dropped: that page does
 * not exist yet. Queue decisions persist via the real PATCH and update
 * optimistically so they reflect immediately without a page reload.
 */

// ── Types ─────────────────────────────────────────────────────────────────────

type ComplianceStatus = 'Pending' | 'Over-budget' | 'Compliant';

interface EmployeeRow {
  caseId: string;
  name: string;
  destination: string;
  tier: string;
  pendingCount: number;
  overCapDelta: number; // sum of (requested - cap) across over-cap exceptions
  currency: string;
  status: ComplianceStatus;
}

interface HeatCell {
  category: string;
  overEmployees: number;
  totalEmployees: number;
  pct: number;
  avgOverage: number;
  currency: string;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function fullName(a: AssignmentSummary): string {
  const joined = [a.employeeFirstName, a.employeeLastName].filter(Boolean).join(' ').trim();
  return joined || a.employeeIdentifier || 'Unknown employee';
}

function fmtMoney(n: number, currency: string): string {
  const symbol = currency === 'EUR' ? '€' : currency === 'USD' ? '$' : currency === 'GBP' ? '£' : '';
  return `${symbol}${Math.round(n).toLocaleString()}${symbol ? '' : ` ${currency}`}`;
}

function isOverCap(e: ExceptionRequest): boolean {
  return typeof e.requested_amount === 'number'
    && typeof e.cap_amount === 'number'
    && e.requested_amount > e.cap_amount;
}

// White → deep red scale matching the task spec's five bands.
function heatStyle(pct: number): string {
  if (pct === 0) return 'bg-white text-slate-300 border border-slate-100';
  if (pct <= 25) return 'bg-amber-50 text-amber-700 border border-amber-100';
  if (pct <= 50) return 'bg-amber-100 text-amber-800 border border-amber-200';
  if (pct <= 75) return 'bg-orange-200 text-orange-900 border border-orange-300';
  return 'bg-rose-500 text-white border border-rose-600';
}

function statusBadge(status: ComplianceStatus): string {
  switch (status) {
    case 'Pending':     return 'bg-amber-50 text-amber-700 ring-1 ring-amber-200';
    case 'Over-budget': return 'bg-rose-50 text-rose-700 ring-1 ring-rose-200';
    case 'Compliant':   return 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200';
  }
}

// Pending first, then Over-budget, then Compliant.
const STATUS_ORDER: Record<ComplianceStatus, number> = { Pending: 0, 'Over-budget': 1, Compliant: 2 };

function titleCase(s: string): string {
  return s.replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function HrPolicyDashboardPage() {
  const [policy, setPolicy] = useState<Record<string, unknown> | null>(null);
  const [companyName, setCompanyName] = useState<string | null>(null);
  const [assignments, setAssignments] = useState<AssignmentSummary[]>([]);
  const [employeeTotal, setEmployeeTotal] = useState(0);
  const [exceptions, setExceptions] = useState<ExceptionRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [deciding, setDeciding] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      // Each source is independent — settle all so one failure (e.g. no
      // published policy) doesn't blank the whole dashboard.
      const [policyRes, assignRes, excRes] = await Promise.allSettled([
        companyPolicyAPI.getLatest(),
        hrAPI.listAssignments({ limit: 100 }),
        listExceptionRequestsForCompany(),
      ]);
      if (cancelled) return;
      if (policyRes.status === 'fulfilled') {
        setPolicy((policyRes.value.policy as Record<string, unknown>) ?? null);
        setCompanyName(policyRes.value.company_name ?? null);
      }
      if (assignRes.status === 'fulfilled') {
        setAssignments(assignRes.value.assignments ?? []);
        setEmployeeTotal(assignRes.value.total ?? assignRes.value.assignments?.length ?? 0);
      }
      if (excRes.status === 'fulfilled') {
        setExceptions(excRes.value ?? []);
      }
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // ── Derived: exceptions grouped by case ─────────────────────────────────────
  const exceptionsByCase = useMemo(() => {
    const map = new Map<string, ExceptionRequest[]>();
    for (const e of exceptions) {
      const list = map.get(e.case_id) ?? [];
      list.push(e);
      map.set(e.case_id, list);
    }
    return map;
  }, [exceptions]);

  // ── Derived: employee compliance rows ───────────────────────────────────────
  const employeeRows = useMemo<EmployeeRow[]>(() => {
    const rows = assignments.map((a) => {
      const excs = exceptionsByCase.get(a.caseId) ?? [];
      const pendingCount = excs.filter((e) => e.status === 'pending').length;
      const overCapExcs = excs.filter(isOverCap);
      const overCapDelta = overCapExcs.reduce((sum, e) => sum + (e.requested_amount - e.cap_amount), 0);
      const currency = excs.find((e) => e.currency)?.currency ?? 'EUR';
      let status: ComplianceStatus = 'Compliant';
      if (pendingCount > 0) status = 'Pending';
      else if (overCapExcs.some((e) => e.status === 'approved')) status = 'Over-budget';
      return {
        caseId: a.caseId,
        name: fullName(a),
        destination: a.case?.host_country ?? '—',
        // AssignmentSummary carries no tier field today; degrade gracefully.
        tier: '—',
        pendingCount,
        overCapDelta,
        currency,
        status,
      };
    });
    rows.sort((x, y) => STATUS_ORDER[x.status] - STATUS_ORDER[y.status] || y.overCapDelta - x.overCapDelta);
    return rows;
  }, [assignments, exceptionsByCase]);

  // ── Derived: pending exception queue (most recent first) ────────────────────
  const pendingQueue = useMemo(
    () =>
      exceptions
        .filter((e) => e.status === 'pending')
        .slice()
        .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? '')),
    [exceptions]
  );

  // ── Derived: category utilisation heatmap ───────────────────────────────────
  const heatCells = useMemo<HeatCell[]>(() => {
    const denom = employeeTotal || assignments.length || 0;
    const byCategory = new Map<string, { cases: Set<string>; overSum: number; overCount: number; currency: string }>();
    for (const e of exceptions) {
      if (!isOverCap(e) && e.status !== 'pending') continue;
      const key = e.category || 'uncategorised';
      const entry = byCategory.get(key) ?? { cases: new Set<string>(), overSum: 0, overCount: 0, currency: e.currency || 'EUR' };
      entry.cases.add(e.case_id);
      if (isOverCap(e)) {
        entry.overSum += e.requested_amount - e.cap_amount;
        entry.overCount += 1;
      }
      byCategory.set(key, entry);
    }
    return Array.from(byCategory.entries())
      .map(([category, v]) => ({
        category,
        overEmployees: v.cases.size,
        totalEmployees: denom,
        pct: denom > 0 ? Math.round((v.cases.size / denom) * 100) : 0,
        avgOverage: v.overCount > 0 ? v.overSum / v.overCount : 0,
        currency: v.currency,
      }))
      .sort((a, b) => b.pct - a.pct);
  }, [exceptions, employeeTotal, assignments.length]);

  // ── Approve / reject (real PATCH + optimistic update) ───────────────────────
  const handleDecide = useCallback(
    async (id: string, status: 'approved' | 'rejected') => {
      setDeciding(id);
      try {
        const updated = await resolveExceptionRequest(id, { status });
        setExceptions((rs) => rs.map((r) => (r.id === id ? { ...r, ...updated } : r)));
      } catch {
        // Surface nothing destructive: leave the row pending so HR can retry.
        // The browser console carries the 4xx/5xx for debugging.
      } finally {
        setDeciding(null);
      }
    },
    []
  );

  // ── Active policy tile fields ───────────────────────────────────────────────
  const policyTitle = (policy?.title as string) ?? companyName ?? 'Relocation policy';
  const policyVersion = (policy?.version as string | number | undefined) ?? null;
  const effectiveDate = (policy?.effective_date as string | undefined) ?? null;
  const nextReview = (policy?.next_review_date as string | undefined) ?? null;

  return (
    <AppShell wide>
      {/* Page header */}
      <div className="px-6 py-5 border-b border-slate-100">
        <Breadcrumb section="HR Operations" title="Policy dashboard" className="mb-2" />
        <h1 className="text-xl font-semibold text-slate-900">Policy utilisation &amp; exceptions</h1>
        <p className="mt-1 text-sm text-slate-500">
          A real-time operational view of policy utilisation across your employees, with a fast
          queue to process exception requests.
        </p>
      </div>

      <div className="px-6 py-6 space-y-8">
        {/* 1 — Active policy tile */}
        <section>
          <div className="rounded-xl border border-slate-200 bg-white px-6 py-5">
            <div className="flex flex-wrap items-center gap-x-8 gap-y-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">Active policy</p>
                <div className="flex items-center gap-2">
                  <span className="text-base font-semibold text-slate-900">{policyTitle}</span>
                  {policyVersion != null && (
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 ring-1 ring-blue-200">
                      v{policyVersion}
                    </span>
                  )}
                </div>
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">Effective</p>
                <p className="text-sm font-medium text-slate-700">{effectiveDate ?? '—'}</p>
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">Employees</p>
                <p className="text-sm font-medium text-slate-700">{employeeTotal}</p>
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">Next review</p>
                <p className="text-sm font-medium text-slate-700">{nextReview ?? '—'}</p>
              </div>
              <div className="flex-1" />
              <button className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors">
                Update policy
              </button>
            </div>
          </div>
        </section>

        {loading && (
          <p className="text-sm text-slate-400">Loading live policy data…</p>
        )}

        {/* 2 — Employee compliance table */}
        <section>
          <div className="flex items-baseline gap-2 mb-3">
            <h2 className="text-sm font-semibold text-slate-800">Employee compliance</h2>
            <p className="text-xs text-slate-400">{employeeRows.length} employee{employeeRows.length === 1 ? '' : 's'} — sorted by status (pending first).</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
            <table className="w-full text-sm min-w-[720px]">
              <thead>
                <tr className="border-b border-slate-100 text-left">
                  {['Employee', 'Destination', 'Tier', 'Over-cap delta', 'Exceptions pending', 'Status'].map((h) => (
                    <th key={h} className="px-4 py-3 text-xs font-medium text-slate-400">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {employeeRows.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-sm text-slate-400">
                      No active employees found for your company.
                    </td>
                  </tr>
                ) : (
                  employeeRows.map((r) => (
                    <tr key={r.caseId} className="border-t border-slate-50 hover:bg-slate-50/60 transition-colors">
                      <td className="px-4 py-3 font-medium text-slate-800">{r.name}</td>
                      <td className="px-4 py-3 text-slate-600">{r.destination}</td>
                      <td className="px-4 py-3 text-slate-500">{r.tier}</td>
                      <td className="px-4 py-3 font-mono text-xs">
                        {r.overCapDelta > 0
                          ? <span className="text-rose-600">+{fmtMoney(r.overCapDelta, r.currency)}</span>
                          : <span className="text-slate-300">—</span>}
                      </td>
                      <td className="px-4 py-3">
                        {r.pendingCount > 0
                          ? <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 ring-1 ring-amber-200">{r.pendingCount}</span>
                          : <span className="text-slate-300 text-xs">0</span>}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusBadge(r.status)}`}>{r.status}</span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* 3 — Exception queue */}
        <section>
          <div className="flex items-baseline gap-2 mb-3">
            <h2 className="text-sm font-semibold text-slate-800">Exception queue</h2>
            <p className="text-xs text-slate-400">{pendingQueue.length} pending — most recent first. One-click decisions, no reload.</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
            <table className="w-full text-sm min-w-[820px]">
              <thead>
                <tr className="border-b border-slate-100 text-left">
                  {['Employee', 'Category', 'Policy cap', 'Requested', 'Justification', 'Decision'].map((h) => (
                    <th key={h} className="px-4 py-3 text-xs font-medium text-slate-400">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pendingQueue.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-sm text-slate-400">
                      No pending exception requests — the queue is clear.
                    </td>
                  </tr>
                ) : (
                  pendingQueue.map((e) => (
                    <tr key={e.id} className="border-t border-slate-50 align-top">
                      <td className="px-4 py-3 font-medium text-slate-800">{e.requested_by_name ?? 'Employee'}</td>
                      <td className="px-4 py-3 text-slate-600">{titleCase(e.category || 'uncategorised')}</td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">{fmtMoney(e.cap_amount, e.currency)}</td>
                      <td className="px-4 py-3 font-mono text-xs">
                        <span className={isOverCap(e) ? 'text-rose-600 font-semibold' : 'text-slate-600'}>
                          {fmtMoney(e.requested_amount, e.currency)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-500 max-w-xs">
                        <span className="line-clamp-2">{e.reason || '—'}</span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <button
                            disabled={deciding === e.id}
                            onClick={() => handleDecide(e.id, 'approved')}
                            className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-40 transition-colors"
                          >
                            Approve
                          </button>
                          <button
                            disabled={deciding === e.id}
                            onClick={() => handleDecide(e.id, 'rejected')}
                            className="px-2.5 py-1 rounded-lg text-xs font-semibold border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40 transition-colors"
                          >
                            Reject
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* 4 — Category utilisation heatmap */}
        <section>
          <div className="flex items-baseline gap-2 mb-3">
            <h2 className="text-sm font-semibold text-slate-800">Category utilisation</h2>
            <p className="text-xs text-slate-400">Share of employees over-cap per category. Hover a cell for detail.</p>
          </div>

          {/* Legend */}
          <div className="flex flex-wrap items-center gap-4 mb-3">
            {[
              { label: '0%', pct: 0 },
              { label: '1–25%', pct: 25 },
              { label: '26–50%', pct: 50 },
              { label: '51–75%', pct: 75 },
              { label: '76–100%', pct: 100 },
            ].map((b) => (
              <div key={b.label} className="flex items-center gap-1.5">
                <span className={`w-5 h-5 rounded ${heatStyle(b.pct)}`} />
                <span className="text-xs text-slate-400">{b.label}</span>
              </div>
            ))}
          </div>

          {heatCells.length === 0 ? (
            <div className="rounded-xl border border-slate-200 bg-white px-6 py-8 text-center text-sm text-slate-400">
              All employees are within their policy caps — no over-cap categories.
            </div>
          ) : (
            <div className="flex flex-wrap gap-3">
              {heatCells.map((c) => (
                <div
                  key={c.category}
                  title={`${titleCase(c.category)}: ${c.overEmployees} of ${c.totalEmployees} employees over-cap${c.avgOverage > 0 ? ` by avg ${fmtMoney(c.avgOverage, c.currency)}/month` : ''}`}
                  className={`w-36 rounded-xl px-4 py-3 ${heatStyle(c.pct)}`}
                >
                  <p className="text-xs font-semibold truncate">{titleCase(c.category)}</p>
                  <p className="text-2xl font-semibold mt-1">{c.pct}<span className="text-sm ml-0.5">%</span></p>
                  <p className="text-[11px] opacity-80 mt-0.5">{c.overEmployees}/{c.totalEmployees} over-cap</p>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
