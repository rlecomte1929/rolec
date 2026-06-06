import React, { useEffect, useState } from 'react';
import { Button } from '../../components/antigravity/Button';
import { Link } from 'react-router-dom';
import { AdminLayout } from './AdminLayout';
import { adminAPI, suppliersAPI, adminReviewQueueAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { getAuthItem, normalizeStoredRole } from '../../utils/demo';

// ── Stat card ─────────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  loading?: boolean;
}

const StatCard: React.FC<StatCardProps> = ({ label, value, sub, loading }) => (
  <div className="bg-white rounded-xl border border-slate-200 px-5 py-4">
    <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">{label}</p>
    <p className="text-3xl font-semibold text-slate-900">{loading ? '…' : value}</p>
    {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
  </div>
);

// ── Module card ───────────────────────────────────────────────────────────────

interface ModuleRow { label: string; value: string | number }

interface ModuleCardProps {
  to: string;
  icon: string;
  title: string;
  subtitle: string;
  metric: string | number;
  rows: ModuleRow[];
  loading?: boolean;
}

const ModuleCard: React.FC<ModuleCardProps> = ({ to, icon, title, subtitle, metric, rows, loading }) => (
  <Link to={to} className="block bg-white rounded-xl border border-slate-200 p-5 hover:border-slate-300 hover:shadow-sm transition-all">
    <div className="flex items-start justify-between mb-4">
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-base shrink-0">
          {icon}
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-900">{title}</p>
          <p className="text-xs text-slate-400">{subtitle}</p>
        </div>
      </div>
      <span className="text-2xl font-semibold text-slate-900">{loading ? '…' : metric}</span>
    </div>
    <div className="space-y-1.5">
      {rows.map((row) => (
        <div key={row.label} className="flex items-center justify-between">
          <span className="text-xs text-slate-500">{row.label}</span>
          <span className="text-xs font-medium text-slate-700">{loading ? '…' : row.value}</span>
        </div>
      ))}
    </div>
  </Link>
);

// ── Page ──────────────────────────────────────────────────────────────────────

type OverviewStats = {
  companies: number;
  hrUsers: number;
  employees: number;
  assignments: number;
  companiesWithPolicy: number;
  activeSuppliers: number;
  reviewOpen: number;
  reviewUnassigned: number;
  relocationsBlocked: number;
};

export const AdminOverviewPage: React.FC = () => {
  const role = normalizeStoredRole(getAuthItem('relopass_role'));
  const [stats, setStats] = useState<OverviewStats>({
    companies: 42, hrUsers: 168, employees: 1204, assignments: 1204,
    companiesWithPolicy: 38, activeSuppliers: 7, reviewOpen: 0, reviewUnassigned: 0, relocationsBlocked: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (role !== 'ADMIN') return;
    const load = async () => {
      setLoading(true);
      try {
        const results = await Promise.allSettled([
          adminAPI.listCompanies(),
          adminAPI.listHrUsers(),
          adminAPI.listEmployees(),
          adminAPI.listAssignments(),
          adminAPI.listPolicyOverview(),
          // Review-queue tile must read the SAME source as /admin/review-queue
          // (the review_queue_items table via getStats), not support cases.
          adminReviewQueueAPI.getStats(),
          adminAPI.listRelocations({ status: 'blocked' }),
          suppliersAPI.list({ status: 'active' }),
        ]);
        const val = <T,>(r: PromiseSettledResult<T>): T | null =>
          r.status === 'fulfilled' ? r.value : null;

        const companiesRes   = val(results[0]) as { companies?: unknown[] } | null;
        const hrUsersRes     = val(results[1]) as { hr_users?: unknown[] } | null;
        const employeesRes   = val(results[2]) as { employees?: unknown[] } | null;
        const assignmentsRes = val(results[3]) as { assignments?: unknown[] } | null;
        const policyRes      = val(results[4]) as { companies?: { policy_status?: string }[] } | null;
        const reviewStatsRes = val(results[5]) as { open_items_count?: number; unassigned_count?: number } | null;
        const relocationsRes = val(results[6]) as { relocations?: unknown[] } | null;
        const suppliersRes   = val(results[7]) as { suppliers?: unknown[] } | null;

        const companiesWithPolicy = (policyRes?.companies ?? []).filter(
          (c) => c.policy_status === 'published'
        ).length;

        setStats({
          companies:          (companiesRes?.companies ?? []).length || 42,
          hrUsers:            (hrUsersRes?.hr_users ?? []).length || 168,
          employees:          (employeesRes?.employees ?? []).length || 1204,
          assignments:        (assignmentsRes?.assignments ?? []).length || 1204,
          companiesWithPolicy: companiesWithPolicy || 38,
          activeSuppliers:    (suppliersRes?.suppliers ?? []).length || 7,
          // No `|| fallback`: 0 is a valid count and must match /admin/review-queue.
          // Use the aggregate `open_items_count` (whole open universe), NOT
          // `by_status.open` — `by_status` is keyed by granular status and has
          // no aggregate "open" bucket (it only counts literal status=="open"
          // synthetic invites), which is why this tile disagreed with the
          // review-queue page. `open_items_count` == that page's items.length.
          reviewOpen:         reviewStatsRes?.open_items_count ?? 0,
          reviewUnassigned:   reviewStatsRes?.unassigned_count ?? 0,
          relocationsBlocked: (relocationsRes?.relocations ?? []).length || 0,
        });
      } catch { /* keep defaults */ }
      finally { setLoading(false); }
    };
    void load();
  }, [role]);

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
      {/* ── Top stat strip ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard label="Active Tenants"    value={stats.companies}   sub="+3 this quarter"               loading={loading} />
        <StatCard label="Cases in Flight"   value={stats.assignments} sub="across 4 corridors top"        loading={loading} />
        <StatCard label="Open Review Items" value={stats.reviewOpen} sub={`${stats.reviewUnassigned} awaiting assignment`} loading={loading} />
        <StatCard label="System SLA (30D)"  value="96%"               sub="target 95%"                    loading={loading} />
      </div>

      {/* ── Module grid — row 1 ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5 gap-4 mb-4">
        <ModuleCard
          to={buildRoute('adminReviewQueue')}
          icon="🔁"
          title="Review queue"
          subtitle={`${stats.reviewOpen} items · ${stats.reviewUnassigned} awaiting assignment`}
          metric={stats.reviewOpen}
          loading={loading}
          rows={[
            { label: 'Vendor approvals',   value: 9 },
            { label: 'Policy exceptions',  value: 6 },
            { label: 'Form templates',     value: 4 },
            { label: 'Source refreshes',   value: 3 },
            { label: 'Tenant onboarding',  value: 2 },
          ]}
        />
        <ModuleCard
          to={buildRoute('adminOpsSla')}
          icon="📈"
          title="Ops analytics"
          subtitle="SLA, bottlenecks, reviewer load"
          metric="96%"
          loading={loading}
          rows={[
            { label: 'SLA met (last 30d)',    value: '96%' },
            { label: 'Reviewer load avg',     value: '14/wk' },
            { label: 'p95 ack',               value: '38m' },
            { label: 'Bottleneck',            value: 'apostille intake' },
          ]}
        />
        <ModuleCard
          to={buildRoute('adminOpsQueue')}
          icon="🔀"
          title="Workflow analytics"
          subtitle="Recommendations, RFQ conversion"
          metric="4127"
          loading={loading}
          rows={[
            { label: 'Recommendations served', value: '4,127' },
            { label: 'RFQ conversion',          value: '32%' },
            { label: 'Supplier engagement',     value: '78%' },
            { label: 'Drop-off · S1→S3',        value: '6%' },
          ]}
        />
        <ModuleCard
          to={buildRoute('adminResources')}
          icon="📋"
          title="Resources CMS"
          subtitle="Guides, requirements, taxonomy"
          metric="318"
          loading={loading}
          rows={[
            { label: 'Published resources', value: 248 },
            { label: 'Drafts',              value: 42 },
            { label: 'Categories',          value: 18 },
            { label: 'Tags',                value: 124 },
          ]}
        />
        <ModuleCard
          to={buildRoute('adminProspects')}
          icon="🎯"
          title="Prospects"
          subtitle="HR pipeline · ICP-scored"
          metric="184"
          loading={loading}
          rows={[
            { label: 'ICP A-tier',         value: 28 },
            { label: 'ICP B-tier',         value: 64 },
            { label: 'Discovery booked',   value: 12 },
            { label: 'Won this quarter',   value: 4 },
          ]}
        />
        <ModuleCard
          to={buildRoute('adminRagQuality')}
          icon="📈"
          title="RAG quality"
          subtitle="Retrieval & generation health over time"
          metric="3 metrics"
          loading={loading}
          rows={[
            { label: 'Context precision',   value: '≥ 85%' },
            { label: 'Factual consistency', value: '≥ 95%' },
            { label: 'Outcome accuracy',    value: '≥ 90%' },
            { label: 'Alerts',              value: 'threshold + trend' },
          ]}
        />
      </div>

      {/* ── Module grid — row 2 ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5 gap-4 mb-6">
        <ModuleCard
          to={buildRoute('adminCatalogQueue')}
          icon="🔗"
          title="Integrations"
          subtitle="Personio, BambooHR, Supabase auth"
          metric={stats.activeSuppliers}
          loading={loading}
          rows={[
            { label: 'Personio webhooks',  value: '12k/day' },
            { label: 'BambooHR · live',    value: 'OK' },
            { label: 'Supabase auth p95',  value: '180ms' },
            { label: 'Last incident',      value: '14d ago' },
          ]}
        />
        <ModuleCard
          to={buildRoute('adminCompanies')}
          icon="🏢"
          title="Companies & users"
          subtitle="Tenants, allowlists, roles"
          metric={stats.companies}
          loading={loading}
          rows={[
            { label: 'Tenants',             value: stats.companies },
            { label: 'HR users',            value: stats.hrUsers },
            { label: 'Employees · active',  value: stats.assignments },
            { label: 'Admin allowlist',     value: '@relopass.com' },
          ]}
        />
      </div>

      {/* ── Info banner ── */}
      <div className="flex items-start gap-3 rounded-xl bg-slate-50 border border-slate-200 px-5 py-4">
        <div className="w-8 h-8 rounded-lg bg-slate-200 flex items-center justify-center text-sm shrink-0 mt-0.5">
          ℹ️
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
