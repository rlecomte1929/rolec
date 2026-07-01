import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { ListChecks, LineChart, Shuffle, FileText, Target, Activity, Link2, Building2, DollarSign, Info } from 'lucide-react';
import {
  adminAPI,
  suppliersAPI,
  adminReviewQueueAPI,
  adminOpsAnalyticsAPI,
  adminResourcesAPI,
  adminProspectsAPI,
} from '../../api/client';
import { getRagEvalMetrics, type RagEvalDashboard } from '../../api/ragEval';
import { getAiUnitEconomics } from '../../api/aiUnitEconomics';
import { StatCard } from '../../components/admin/overview/StatCard';
import { ModuleCard } from '../../components/admin/overview/ModuleCard';
import { Button } from '../../components/antigravity/Button';
import { buildRoute } from '../../navigation/routes';
import { getAuthItem, normalizeStoredRole } from '../../utils/demo';
import { AdminLayout } from './AdminLayout';

// ── Page ──────────────────────────────────────────────────────────────────────

type OverviewStats = {
  companies: number | null;
  hrUsers: number | null;
  employees: number | null;
  assignments: number | null;
  activeSuppliers: number | null;
  reviewOpen: number | null;
  reviewUnassigned: number | null;
  // Module-card aggregates (AIQ-1329) — lightweight counts from each section's
  // existing endpoint so the cards show live numbers instead of 'Unavailable'.
  opsOpen: number | null;
  opsBreached: number | null;
  workflowCases: number | null;
  workflowRfqs: number | null;
  resourcesPublished: number | null;
  resourcesDraft: number | null;
  prospectsTotal: number | null;
  ragHealthy: number | null;
  ragTotal: number | null;
  aiSpendUsd: number | null;
  aiCalls: number | null;
  aiCo2eGrams: number | null;
};

const EMPTY_STATS: OverviewStats = {
  companies: null,
  hrUsers: null,
  employees: null,
  assignments: null,
  activeSuppliers: null,
  reviewOpen: null,
  reviewUnassigned: null,
  opsOpen: null,
  opsBreached: null,
  workflowCases: null,
  workflowRfqs: null,
  resourcesPublished: null,
  resourcesDraft: null,
  prospectsTotal: null,
  ragHealthy: null,
  ragTotal: null,
  aiSpendUsd: null,
  aiCalls: null,
  aiCo2eGrams: null,
};

function settledArrayCount<T>(
  result: PromiseSettledResult<T>,
  select: (value: T) => unknown,
): number | null {
  if (result.status !== 'fulfilled') return null;
  const rows = select(result.value);
  return Array.isArray(rows) ? rows.length : null;
}

function settledNumber<T>(
  result: PromiseSettledResult<T>,
  select: (value: T) => unknown,
): number | null {
  if (result.status !== 'fulfilled') return null;
  const value = select(result.value);
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

const metricSummary = (value: number | null, suffix: string): string =>
  value === null ? 'Source unavailable' : `${value} ${suffix}`;

export const AdminOverviewPage: React.FC = () => {
  const role = normalizeStoredRole(getAuthItem('relopass_role'));

  const statsQuery = useQuery({
    queryKey: ['admin', 'overview-stats'],
    queryFn: async (): Promise<OverviewStats> => {
      const results = await Promise.allSettled([
        adminAPI.listCompanies(),
        adminAPI.listHrUsers(),
        adminAPI.listEmployees(),
        adminAPI.listAssignments(),
        // Review-queue totals use the same aggregate as /admin/review-queue.
        adminReviewQueueAPI.getStats(),
        suppliersAPI.list({ status: 'active' }),
        // Module-card sources (AIQ-1329) — all lightweight aggregates/counts.
        adminOpsAnalyticsAPI.getSlaOverview({ days: 30 }),
        adminOpsAnalyticsAPI.getWorkflowOverview({ days: 30 }),
        adminResourcesAPI.getCounts(),
        adminProspectsAPI.list({ limit: 1 }), // limit=1: we only read `total`, not rows
        getRagEvalMetrics(),
        getAiUnitEconomics(),
      ]);

      return {
        companies: settledArrayCount(results[0], (value) => value.companies),
        hrUsers: settledArrayCount(results[1], (value) => value.hr_users),
        employees: settledArrayCount(results[2], (value) => value.employees),
        assignments: settledArrayCount(results[3], (value) => value.assignments),
        reviewOpen: settledNumber(results[4], (value) => (value as { open_items_count?: number }).open_items_count),
        reviewUnassigned: settledNumber(results[4], (value) => (value as { unassigned_count?: number }).unassigned_count),
        activeSuppliers: settledArrayCount(results[5], (value) => (value as { suppliers?: unknown[] }).suppliers),
        opsOpen: settledNumber(results[6], (value) => (value as { open_count?: number }).open_count),
        opsBreached: settledNumber(results[6], (value) => (value as { breached_count?: number }).breached_count),
        workflowCases: settledNumber(results[7], (value) => value.events?.case_created),
        workflowRfqs: settledNumber(results[7], (value) => value.events?.rfq_created),
        resourcesPublished: settledNumber(results[8], (value) => value.resources_published),
        resourcesDraft: settledNumber(results[8], (value) => value.resources_draft),
        prospectsTotal: settledNumber(results[9], (value) => value.total),
        ragHealthy: settledNumber(results[10], (value) => (value as RagEvalDashboard).metrics?.filter((m) => !m.alert.firing).length),
        ragTotal: settledNumber(results[10], (value) => (value as RagEvalDashboard).metrics?.length),
        aiSpendUsd: settledNumber(results[11], (value) => value.totals?.total_cost_usd),
        aiCalls: settledNumber(results[11], (value) => value.totals?.n_calls),
        aiCo2eGrams: settledNumber(results[11], (value) => value.totals?.total_co2e_grams),
      };
    },
    enabled: role === 'ADMIN',
  });
  const stats: OverviewStats = statsQuery.data ?? EMPTY_STATS;
  const loading = statsQuery.isLoading;

  // RAG quality has no single count — summarise it as "healthy / total" metrics
  // and surface how many thresholds are currently alerting.
  const ragSummary = stats.ragTotal === null ? null : `${stats.ragHealthy ?? 0}/${stats.ragTotal}`;
  const ragAlerting = stats.ragTotal === null ? null : stats.ragTotal - (stats.ragHealthy ?? 0);

  const aiSpendLabel = stats.aiSpendUsd === null ? null : `$${stats.aiSpendUsd.toFixed(2)}`;
  const aiCo2eLabel = stats.aiCo2eGrams === null ? null : `${stats.aiCo2eGrams.toFixed(1)} g`;

  if (role !== 'ADMIN') {
    return (
      <AdminLayout title="Admin overview">
        <p className="text-sm text-slate-500">You do not have access to the Admin Console.</p>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout
      title="Admin overview"
      subtitle="Everything ReloPass operators see. Tenant data is read-write; tenant-private fields are masked unless you escalate via the review queue."
      headerRight={
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs text-slate-600">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
            admin scope · @relopass.com
          </span>
          <Button unstyled className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-medium text-slate-700 hover:bg-slate-50">
            <svg className="w-3.5 h-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2a1 1 0 01-.293.707L13 13.414V19a1 1 0 01-.553.894l-4 2A1 1 0 017 21v-7.586L3.293 6.707A1 1 0 013 6V4z" />
            </svg>
            All tenants
          </Button>
        </div>
      }
    >
      {/* Scope clarity (AIQ-915): the overview aggregates across every tenant,
          while the detail pages it links to are scoped to a single tenant — so
          their counts are expected to be lower, not contradictory. */}
      <p className="mb-4 text-xs text-slate-500">
        Platform-wide totals across <span className="font-medium text-slate-600">all tenants</span>.
        Detail pages (Companies, Resources CMS, Provider status) are scoped to a single tenant,
        so their counts will be lower.
      </p>

      {/* ── Top stat strip ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <StatCard testId="metric-tenants" label="Tenants" value={stats.companies} sub="All tenant records" loading={loading} />
        <StatCard testId="metric-assignments" label="Assignments" value={stats.assignments} sub="All assignment records" loading={loading} />
        <StatCard
          testId="metric-review-open"
          label="Open Review Items"
          value={stats.reviewOpen}
          sub={metricSummary(stats.reviewUnassigned, 'awaiting assignment')}
          loading={loading}
        />
      </div>

      {/* ── Module grid — row 1 ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5 gap-4 mb-4">
        <ModuleCard
          testId="module-review-queue"
          to={buildRoute('adminReviewQueue')}
          icon={<ListChecks className="h-[18px] w-[18px]" aria-hidden="true" />}
          title="Review queue"
          subtitle={metricSummary(stats.reviewOpen, 'open items')}
          metric={stats.reviewOpen}
          loading={loading}
          rows={[
            { label: 'Open items', value: stats.reviewOpen },
            { label: 'Awaiting assignment', value: stats.reviewUnassigned },
          ]}
        />
        <ModuleCard
          testId="module-ops-analytics"
          to={buildRoute('adminOpsSla')}
          icon={<LineChart className="h-[18px] w-[18px]" aria-hidden="true" />}
          title="Ops analytics"
          subtitle="SLA, bottlenecks, reviewer load"
          metric={stats.opsOpen}
          loading={loading}
          rows={[
            { label: 'Open SLA items', value: stats.opsOpen },
            { label: 'Breached', value: stats.opsBreached },
          ]}
        />
        <ModuleCard
          testId="module-workflow-analytics"
          to={buildRoute('adminOpsQueue')}
          icon={<Shuffle className="h-[18px] w-[18px]" aria-hidden="true" />}
          title="Workflow analytics"
          subtitle="Recommendations, RFQ conversion"
          metric={stats.workflowCases}
          loading={loading}
          rows={[
            { label: 'Cases created (30d)', value: stats.workflowCases },
            { label: 'RFQs created (30d)', value: stats.workflowRfqs },
          ]}
        />
        <ModuleCard
          testId="module-resources"
          to={buildRoute('adminResources')}
          icon={<FileText className="h-[18px] w-[18px]" aria-hidden="true" />}
          title="Resources CMS"
          subtitle="Guides, requirements, taxonomy"
          metric={stats.resourcesPublished}
          loading={loading}
          rows={[
            { label: 'Published', value: stats.resourcesPublished },
            { label: 'Draft', value: stats.resourcesDraft },
          ]}
        />
        <ModuleCard
          testId="module-prospects"
          to={buildRoute('adminProspects')}
          icon={<Target className="h-[18px] w-[18px]" aria-hidden="true" />}
          title="Prospects"
          subtitle="HR pipeline · ICP-scored"
          metric={stats.prospectsTotal}
          loading={loading}
          rows={[{ label: 'Total in pipeline', value: stats.prospectsTotal }]}
        />
        <ModuleCard
          testId="module-rag-quality"
          to={buildRoute('adminRagQuality')}
          icon={<Activity className="h-[18px] w-[18px]" aria-hidden="true" />}
          title="RAG quality"
          subtitle="Retrieval & generation health over time"
          metric={ragSummary}
          loading={loading}
          rows={[{ label: 'Thresholds alerting', value: ragAlerting }]}
        />
        <ModuleCard
          testId="module-ai-unit-economics"
          to={buildRoute('adminAiUnitEconomics')}
          icon={<DollarSign className="h-[18px] w-[18px]" aria-hidden="true" />}
          title="AI economics"
          subtitle="Cost & carbon per feature"
          metric={aiSpendLabel}
          loading={loading}
          rows={[
            { label: 'AI calls', value: stats.aiCalls },
            { label: 'Carbon (CO₂e)', value: aiCo2eLabel },
          ]}
        />
      </div>

      {/* ── Module grid — row 2 ── */}
      {/* Only 2 cards here, so cap at md:grid-cols-2 — the row-1 breakpoints (…2xl:grid-cols-5)
          would strand these two as wide orphans in a 5-column ghost grid at large viewports. */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <ModuleCard
          testId="module-suppliers"
          to={buildRoute('adminSuppliers')}
          icon={<Link2 className="h-[18px] w-[18px]" aria-hidden="true" />}
          title="Suppliers"
          subtitle="Active supplier records"
          metric={stats.activeSuppliers}
          loading={loading}
          rows={[
            { label: 'Active suppliers', value: stats.activeSuppliers },
          ]}
        />
        <ModuleCard
          testId="module-companies"
          to={buildRoute('adminCompanies')}
          icon={<Building2 className="h-[18px] w-[18px]" aria-hidden="true" />}
          title="Companies & users"
          subtitle="Tenants, allowlists, roles"
          metric={stats.companies}
          loading={loading}
          rows={[
            { label: 'Tenants',             value: stats.companies },
            { label: 'HR users',            value: stats.hrUsers },
            { label: 'Employees',            value: stats.employees },
            { label: 'Assignments',          value: stats.assignments },
            { label: 'Admin allowlist',     value: '@relopass.com' },
          ]}
        />
      </div>

      {/* ── Info banner ── */}
      <div className="flex items-start gap-3 rounded-xl bg-slate-50 border border-slate-200 px-5 py-4">
        <div className="w-8 h-8 rounded-lg bg-slate-200 flex items-center justify-center text-slate-600 shrink-0 mt-0.5">
          <Info className="h-4 w-4" aria-hidden="true" />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-800 mb-1">What you see vs. what tenants see</p>
          <p className="text-sm text-slate-600 leading-relaxed">
            Tenants on <strong>Basic</strong> see intake + documents.{' '}
            <strong>Standard</strong> adds roadmap, marketplace, and AI discovery.{' '}
            <strong>Premium</strong> unlocks the full dossier &amp; forms.{' '}
            <strong>HR</strong> tier exposes the mobility control center and the policy engine.
            Switch role in the Tweaks panel to preview what each tier sees.
          </p>
        </div>
      </div>
    </AdminLayout>
  );
};
