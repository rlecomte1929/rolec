import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { PanelLeftClose, PanelLeftOpen, ChevronRight } from 'lucide-react';
import { NavIcon } from '../features/platform-v2/sidebar/navIcons';
import { ROUTE_DEFS, buildRoute } from '../navigation/routes';
import { getHrNotificationCounts, type HrNotificationCounts } from '../api/hrCatalog';
import { getAdminNotificationCounts, type AdminNotificationCounts } from '../api/adminCatalog';
import { useSelectedCase } from '../contexts/SelectedCaseContext';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';
import { Button } from './antigravity/Button';
import { swallow } from '../lib/errorTracking';
import { INTAKE_TOTAL_STEPS } from '../features/platform-v2/intake/intakeSteps';
import { isIntakeComplete } from '../features/employee-journey/caseStage';
import type { EmployeeLinkedOverviewRow } from '../types/employeeAssignmentOverview';

// ── Types ──────────────────────────────────────────────────────────────────────

export type SidebarRole = 'EMPLOYEE' | 'HR' | 'ADMIN';

type BadgeVariant = 'count' | 'new' | 'live';
type BadgeSpec =
  | { kind: 'static'; variant: 'new' | 'live' }
  | { kind: 'static-count'; count: number }
  | { kind: 'dynamic'; getCount: (ctx: NotifContext) => number };

interface SidebarVisibilityCtx {
  role: SidebarRole;
  linkedCount: number;
  /** True while the employee's assignments are still loading — used to keep
   *  case-dependent items stable (don't hide-then-show) during load (E3). */
  assignmentsLoading: boolean;
}

interface SectionItem {
  id: string;
  label: string;
  /** Optional one-line hint shown below the label (not shown when collapsed). */
  hint?: string;
  to: string;
  /** Optional override per role (e.g. employee Inbox vs HR Inbox). */
  toByRole?: Partial<Record<SidebarRole, string>>;
  /** Exact route match — useful when path is the index of a section. */
  exact?: boolean;
  badge?: BadgeSpec;
  /** Hide this item conditionally (e.g. wizard tab is meaningless without a case). */
  hidden?: (ctx: SidebarVisibilityCtx) => boolean;
  /** Optional sub-items shown indented below the parent while the parent route
   *  is active (e.g. the Policy tabs deep-linking to /hr/policy?tab=…). NAV-POL-1. */
  children?: { id: string; label: string; to: string }[];
}

interface NavSection {
  label: string;
  minRole: SidebarRole;
  items: SectionItem[];
}

interface NotifContext {
  hr: HrNotificationCounts | null;
  admin: AdminNotificationCounts | null;
}

const ROLE_RANK: Record<SidebarRole, number> = { EMPLOYEE: 0, HR: 1, ADMIN: 2 };

// ── Section definitions ───────────────────────────────────────────────────────
// Single source of truth. Routes pulled from ROUTE_DEFS so renames cascade.

const SECTIONS: NavSection[] = [
  {
    label: 'Employee',
    minRole: 'EMPLOYEE',
    items: [
      { id: 'intake', label: 'My cases', to: ROUTE_DEFS.employeeDashboard.path, exact: true },
      {
        id: 'detailed-intake',
        label: 'Intake form',
        hint: 'Answer questions that shape your relocation case',
        to: ROUTE_DEFS.employeeIntake.path,
        // Wizard is meaningless without a linked case — hide until the user has one.
        // Admins keep it visible so they can preview the form.
        hidden: ({ linkedCount, role, assignmentsLoading }) =>
          role !== 'ADMIN' && !assignmentsLoading && linkedCount === 0,
      },
      // No badge: the roadmap item count isn't wired into the sidebar's
      // NotifContext, and the hard-coded '3' showed even when the roadmap was
      // empty (buttons disabled, no items) — the same distrust-training problem
      // AIQ-914 fixed for the other items. Re-add a `dynamic` badge once a real
      // roadmap-item count is exposed to the sidebar. (AIQ-979)
      { id: 'roadmap', label: 'Roadmap', to: ROUTE_DEFS.employeeDashboard.path },
      { id: 'documents', label: 'Tasks', hint: 'Documents and actions requested by your HR team', to: ROUTE_DEFS.employeeTaskPage.path },
      { id: 'dossier', label: 'Dossier & forms', to: ROUTE_DEFS.employeeDashboard.path },
      { id: 'service-providers', label: 'Services', hint: 'Choose services and see recommended providers for your move', to: ROUTE_DEFS.services.path },
      { id: 'benefit-comparison', label: 'Benefit comparison', to: ROUTE_DEFS.employeeBenefitsComparison.path },
      { id: 'immigration-qa', label: 'Immigration Q&A', hint: 'Grounded, cited answers to immigration questions for your corridor', to: ROUTE_DEFS.employeeImmigrationAssistant.path },
      // NAV-002: 'Resources' = the destination lifestyle guide (housing, events,
      // local services) for the employee's assignment. No badge (the old 'LIVE'
      // badge was misleading).
      { id: 'resources-guide', label: 'Resources', to: ROUTE_DEFS.resources.path },
      {
        id: 'inbox',
        label: 'Inbox',
        to: ROUTE_DEFS.messages.path,
        toByRole: { HR: ROUTE_DEFS.hrMessages.path, ADMIN: ROUTE_DEFS.hrMessages.path },
        // No badge: there is no thread-count source wired yet, and a hard-coded
        // '3' (vs 0 real threads) trained users to distrust the badge (AIQ-914).
      },
    ],
  },
  {
    label: 'HR Operations',
    minRole: 'HR',
    items: [
      { id: 'company-profile', label: 'Company profile', to: ROUTE_DEFS.hrCompanyProfile.path, exact: true },
      {
        id: 'mobility-control',
        label: 'Mobility command center',
        to: ROUTE_DEFS.hrCommandCenter.path,
        exact: true,
        // No badge: the hard-coded '12' never matched the real case count
        // (116 in prod). No active-case count is exposed by the notification
        // endpoints, so show nothing rather than a misleading number (AIQ-914).
      },
      // NAV-POL-1: surface the existing HrPolicy ?tab= tabs as sidebar sub-items
      // (shown indented while on /hr/policy). Each deep-links to a bookmarkable tab.
      {
        id: 'policy-benefits',
        label: 'Policy',
        to: ROUTE_DEFS.hrPolicy.path,
        children: [
          { id: 'policy-published', label: 'Published policy', to: `${ROUTE_DEFS.hrPolicy.path}?tab=policy` },
          { id: 'policy-builder', label: 'Policy builder', to: `${ROUTE_DEFS.hrPolicy.path}?tab=builder` },
          { id: 'policy-summary', label: 'Benefits summary', to: `${ROUTE_DEFS.hrPolicy.path}?tab=summary` },
          { id: 'policy-exceptions', label: 'Policy exceptions', to: `${ROUTE_DEFS.hrPolicy.path}?tab=exceptions` },
        ],
      },
      // NAV-SP-1: the former two flat entries (vendor-curation + provider-grid)
      // are re-homed under one grouped 'Service providers' surface with Dashboard /
      // Vendor Management / Provider Status sub-tabs (/hr/service-providers).
      // RECS-CATALOG-2/AIQ-1080: badge the count of employees stuck on the "HR is
      // finalizing" empty state (catalog_employee_demand, un-curated only) so HR is
      // nudged to curate from anywhere — not just once they're already on the page.
      { id: 'service-providers', label: 'Service providers', hint: 'Manage vendors and track provider status', to: ROUTE_DEFS.hrServiceProviders.path, badge: { kind: 'dynamic', getCount: (c) => c.hr?.employees_waiting ?? 0 } },
      { id: 'ai-decisions', label: 'AI decisions', to: ROUTE_DEFS.hrAiDecisions.path },
      // NAV-001: 'Requirements' now points to the corridor immigration-compliance
      // page (/hr/requirements) — document checklist, risk flags, milestones, intake
      // progress — NOT the old /resources lifestyle destination guide.
      { id: 'requirements', label: 'Requirements', to: ROUTE_DEFS.hrRequirements.path },
      // NAV-002: HR 'Resources' opens the destination-preview at /hr/resources
      // (pick any destination, no case needed) — the lifestyle guide employees see.
      { id: 'hr-resources-preview', label: 'Resources', to: ROUTE_DEFS.hrResources.path },
    ],
  },
  {
    label: 'Admin · ReloPass',
    minRole: 'ADMIN',
    items: [
      { id: 'admin-overview', label: 'Admin overview', to: ROUTE_DEFS.adminOverview.path, exact: true },
      { id: 'data-rights', label: 'Data-rights desk', to: ROUTE_DEFS.adminDsar.path },
      { id: 'policy-versions', label: 'Policy versions', to: ROUTE_DEFS.adminPolicyVersions.path },
      { id: 'feature-flags', label: 'Feature flags', to: ROUTE_DEFS.adminFeatureFlags.path },
      { id: 'permissions', label: 'Permissions', to: ROUTE_DEFS.adminPermissions.path },
      { id: 'executive', label: 'Executive', to: ROUTE_DEFS.adminExecutive.path, badge: { kind: 'static', variant: 'new' } },
      { id: 'mission-control', label: 'Mission Control', to: ROUTE_DEFS.adminMissionControl.path, badge: { kind: 'static', variant: 'new' } },
      { id: 'admin-companies', label: 'Companies', to: ROUTE_DEFS.adminCompanies.path },
      {
        id: 'review-queue',
        label: 'Review queue',
        // AIQ-914: no badge — it was wired to admin.pending_tickets (HR-opened
        // destination requests = the Catalog queue metric, not review-queue items)
        // and carried a stale '24' fallback, so it never matched /admin/review-queue.
        // No review-queue-item count is exposed to the sidebar; show nothing until
        // one is (don't add a new endpoint per task scope).
        to: ROUTE_DEFS.adminReviewQueue.path,
      },
      // 'Ops analytics' lands on /admin/ops; the former 'Workflow analytics'
      // entry was a second sidebar link to the Queue *tab* of the same page
      // (reachable via the Ops page tab strip), removed to end the false split.
      { id: 'ops-analytics', label: 'Ops analytics', to: ROUTE_DEFS.adminOps.path },
      { id: 'resources-cms', label: 'Resources CMS', to: ROUTE_DEFS.adminResources.path },
      { id: 'auth-page-design', label: 'Auth page design', to: ROUTE_DEFS.adminAuthPageDesign.path },
      { id: 'form-templates', label: 'Form templates', to: ROUTE_DEFS.adminFormTemplates.path, badge: { kind: 'static', variant: 'new' } },
      { id: 'prospects', label: 'Prospects', to: ROUTE_DEFS.adminProspects.path },
      {
        id: 'integrations',
        label: 'Catalog queue',
        to: ROUTE_DEFS.adminCatalogQueue.path,
        badge: { kind: 'dynamic', getCount: (c) => c.admin?.pending_tickets ?? 0 },
      },
      { id: 'requirement-facts', label: 'Requirement facts', to: ROUTE_DEFS.adminRequirementFacts.path },
      { id: 'research-requests', label: 'Research requests', to: ROUTE_DEFS.adminResearchRequests.path },
      { id: 'ai-governance', label: 'AI governance', to: ROUTE_DEFS.adminAiControls.path },
      { id: 'feedback-console', label: 'Feedback', to: ROUTE_DEFS.adminFeedback.path },
      { id: 'admin-accounts', label: 'Admin accounts', to: ROUTE_DEFS.adminAdmins.path },
      { id: 'audit-log', label: 'Audit log', to: ROUTE_DEFS.adminAuditLog.path },
    ],
  },
];

// ── Sub-pieces ────────────────────────────────────────────────────────────────

const Badge: React.FC<{ count?: number; variant?: BadgeVariant }> = ({ count, variant = 'count' }) => {
  if (variant === 'new') {
    return (
      <span className="ml-auto px-1.5 py-0.5 rounded text-[10px] font-bold bg-accent-50 text-accent-500 border border-accent-100">
        NEW
      </span>
    );
  }
  if (variant === 'live') {
    return (
      <span className="ml-auto px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-600 border border-emerald-100">
        LIVE
      </span>
    );
  }
  if (!count || count <= 0) return null;
  return (
    <span className="ml-auto min-w-[1.25rem] px-1 text-center rounded-full bg-slate-200 text-slate-700 text-[10px] font-semibold leading-5">
      {count > 99 ? '99+' : count}
    </span>
  );
};

const SectionHeading: React.FC<{ label: string; count?: number; collapsed: boolean }> = ({ label, count, collapsed }) => {
  if (collapsed) return <div className="mt-3 mx-2 border-t border-slate-100" aria-hidden="true" />;
  return (
    <div className="flex items-center gap-1.5 px-3 pt-5 pb-1">
      <span className="text-[10px] font-semibold tracking-widest text-slate-400 uppercase">{label}</span>
      {count !== undefined && <span className="text-[10px] text-slate-300 font-medium">{count}</span>}
    </div>
  );
};

// ── Employee journey-progress mini indicator (NAV-EMP-1) ─────────────────────────
// A compact 3-step progress line shown under the "My cases" header for employees
// with an active case. NOT the antigravity StepRail (that's a large page-card with
// border/shadow/10×10 dots) — this is a tiny inline ●─●─○ + "Step N of 3" line in
// the sidebar's type scale, so it reads as wayfinding rather than a content block.
//
// Model: a linear 3-stage pipeline (Intake → Services & policy → Roadmap). The
// current stage is Intake until intake is submitted, then advances to Services &
// policy. We have intake_step + status per linked case via EmployeeAssignmentContext,
// so this is data-correct. (Roadmap stays "upcoming" until the services stage is
// done — the sidebar has no services/roadmap completion signal to advance further.)

type MiniStepStatus = 'done' | 'current' | 'upcoming';
const JOURNEY_STEP_LABELS = ['Intake', 'Services & policy', 'Roadmap'] as const;

function deriveJourneySteps(row: EmployeeLinkedOverviewRow): MiniStepStatus[] {
  const step = row.intake_step ?? 0;
  const submitted = isIntakeComplete(row.status) || (INTAKE_TOTAL_STEPS > 0 && step >= INTAKE_TOTAL_STEPS);
  // Intake: done once submitted; otherwise it's the current focus (covers step 0
  // and partial progress). Services becomes current once intake is submitted.
  return submitted
    ? ['done', 'current', 'upcoming']
    : ['current', 'upcoming', 'upcoming'];
}

const JourneyProgressMini: React.FC<{ row: EmployeeLinkedOverviewRow }> = ({ row }) => {
  const steps = deriveJourneySteps(row);
  const currentIndex = steps.findIndex((s) => s === 'current');
  const labelIndex = currentIndex === -1 ? steps.length - 1 : currentIndex;
  return (
    <div className="ml-7 mb-1 mt-0.5 flex flex-col gap-1">
      <div className="flex items-center gap-1" aria-hidden="true">
        {steps.map((status, i) => (
          <React.Fragment key={JOURNEY_STEP_LABELS[i]}>
            <span
              className={`h-2 w-2 shrink-0 rounded-full border ${
                status === 'upcoming'
                  ? 'border-slate-300 bg-white'
                  : status === 'current'
                    ? 'border-[#0b2b43] bg-[#0b2b43] ring-2 ring-[#0b2b43]/20'
                    : 'border-[#0b2b43] bg-[#0b2b43]'
              }`}
            />
            {i < steps.length - 1 && (
              <span className={`h-px w-2.5 shrink-0 ${steps[i + 1] === 'upcoming' ? 'bg-slate-200' : 'bg-[#0b2b43]/40'}`} />
            )}
          </React.Fragment>
        ))}
      </div>
      <span className="text-[11px] leading-tight text-slate-500">
        Phase {labelIndex + 1} of {JOURNEY_STEP_LABELS.length} · {JOURNEY_STEP_LABELS[labelIndex]}
      </span>
    </div>
  );
};

// ── Props ─────────────────────────────────────────────────────────────────────

export interface PlatformShellSidebarProps {
  role: SidebarRole;
  /** Optional slot for the company widget under the brand (CompanySwitcher / CompanyBrand). */
  companySlot?: React.ReactNode;
  /** Footer identity. Defaults to a sensible placeholder if absent. */
  user?: { initials: string; name: string; role: string };
}

// ── Collapse persistence ──────────────────────────────────────────────────────

const COLLAPSE_KEY = 'platform_sidebar_collapsed';

function readCollapsed(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return window.localStorage.getItem(COLLAPSE_KEY) === '1';
  } catch {
    return false;
  }
}

// ── Component ─────────────────────────────────────────────────────────────────

export const PlatformShellSidebar: React.FC<PlatformShellSidebarProps> = ({ role, companySlot, user }) => {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState<boolean>(() => readCollapsed());

  // Persist + cross-tab sync
  useEffect(() => {
    try {
      window.localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0');
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === COLLAPSE_KEY) setCollapsed(e.newValue === '1');
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  // Notification polling — only what the visible sections need
  const [hrNotif, setHrNotif] = useState<HrNotificationCounts | null>(null);
  const [adminNotif, setAdminNotif] = useState<AdminNotificationCounts | null>(null);
  const rank = ROLE_RANK[role];

  useEffect(() => {
    if (rank < ROLE_RANK.HR) return;
    let cancelled = false;
    const fetchHr = () => {
      void getHrNotificationCounts()
        .then((c) => { if (!cancelled) setHrNotif(c); })
        .catch((e) => swallow(e, 'PlatformShellSidebar: HR notification poll'));
    };
    fetchHr();
    const id = window.setInterval(fetchHr, 60_000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, [rank]);

  useEffect(() => {
    if (rank < ROLE_RANK.ADMIN) return;
    let cancelled = false;
    const fetchAdmin = () => {
      void getAdminNotificationCounts()
        .then((c) => { if (!cancelled) setAdminNotif(c); })
        .catch((e) => swallow(e, 'PlatformShellSidebar: admin notification poll'));
    };
    fetchAdmin();
    const id = window.setInterval(fetchAdmin, 60_000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, [rank]);

  const notifCtx: NotifContext = { hr: hrNotif, admin: adminNotif };

  // Extract caseId from the URL when on a case-scoped employee route
  // e.g. /employee/case/43556892-2f33-4ab1-8533-9c11095e5565/wizard/1 → caseId
  const urlCaseId = location.pathname.match(/\/employee\/case\/([^/]+)/)?.[1] ?? null;

  // Fall back to the last-known caseId (SelectedCaseContext / localStorage), then to the
  // employee's primary linked case, so sidebar links resolve to the case-scoped roadmap/dossier
  // even from /employee/dashboard where there is no case in the URL and nothing was selected yet.
  const { selectedCaseId } = useSelectedCase();
  const { linkedCount, primaryCaseId, linkedSummaries, isLoading: assignmentsLoading } = useEmployeeAssignment();
  const effectiveCaseId = urlCaseId ?? selectedCaseId ?? primaryCaseId;

  // Resolve the active linked case (by case_id or assignment_id) so the employee
  // journey-progress mini indicator can read its intake_step/status. Falls back to
  // the primary linked case. Null when the employee has no linked case yet.
  const activeJourneyRow =
    linkedSummaries.find((r) => r.case_id === effectiveCaseId || r.assignment_id === effectiveCaseId) ??
    linkedSummaries[0] ??
    null;

  // Resolve the effective `to` for an item, allowing case-scoped overrides
  const resolveItemTo = (item: SectionItem): string => {
    if (item.id === 'roadmap' && effectiveCaseId) {
      return buildRoute('employeeCaseRoadmap', { caseId: effectiveCaseId });
    }
    if (item.id === 'dossier' && effectiveCaseId) {
      return buildRoute('employeeCaseDossier', { caseId: effectiveCaseId });
    }
    // AIQ-976: case-scope the intake link so the sidebar opens the active case
    // in the v2 wizard, consistent with roadmap/dossier above.
    if (item.id === 'detailed-intake' && effectiveCaseId) {
      return buildRoute('employeeCaseIntake', { caseId: effectiveCaseId });
    }
    return item.toByRole?.[role] ?? item.to;
  };

  const isActive = (item: SectionItem) => {
    const path = resolveItemTo(item);
    if (item.exact) return location.pathname === path;
    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  // A child sub-item (e.g. a Policy tab) is active when its pathname matches and
  // its ?tab= equals the current tab — defaulting to the first tab when absent,
  // so /hr/policy with no query highlights "Published policy". (NAV-POL-1)
  const isChildActive = (childTo: string) => {
    const [childPath, childQuery = ''] = childTo.split('?');
    if (location.pathname !== childPath) return false;
    const childTab = new URLSearchParams(childQuery).get('tab') ?? 'policy';
    const currentTab = new URLSearchParams(location.search).get('tab') ?? 'policy';
    return childTab === currentTab;
  };

  const visibilityCtx: SidebarVisibilityCtx = { role, linkedCount, assignmentsLoading };
  const visibleSections = SECTIONS
    .filter((s) => ROLE_RANK[s.minRole] <= rank)
    .map((s) => {
      // A higher-role user (e.g. HR) inherits lower-persona sections via the rank
      // model, but should NOT see that persona's exclusive surfaces — only items
      // that explicitly declare a route for their role (e.g. the shared Inbox via
      // toByRole). Admin keeps everything for cross-persona preview.
      const borrowed = ROLE_RANK[s.minRole] < rank && role !== 'ADMIN';
      return {
        ...s,
        // Suppress the persona heading on a borrowed section: its surviving shared
        // items (Inbox) float at the top rather than under a misleading "Employee" label.
        borrowed,
        items: s.items.filter((item) => {
          if (item.hidden?.(visibilityCtx)) return false;
          if (borrowed) return Boolean(item.toByRole?.[role]);
          return true;
        }),
      };
    })
    .filter((s) => s.items.length > 0);

  return (
    <aside
      aria-label="Platform navigation"
      className={`${collapsed ? 'w-[64px]' : 'w-[240px]'} shrink-0 flex flex-col bg-white border-r border-slate-200 overflow-y-auto transition-[width] duration-200 ease-out`}
    >
      {/* Brand + collapse toggle */}
      <div className={`flex items-center border-b border-slate-100 px-3 py-3 ${collapsed ? 'justify-center' : 'gap-2'}`}>
        {!collapsed && (
          <>
            <img
              src="/relopass-logo.png"
              alt="ReloPass"
              className="h-6 w-auto"
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
            <span className="text-sm font-semibold text-slate-900">ReloPass</span>
            <span className="text-slate-400 text-sm">/ Platform</span>
            <Button unstyled
              type="button"
              onClick={() => setCollapsed(true)}
              aria-label="Collapse sidebar"
              title="Collapse sidebar"
              className="ml-auto grid h-6 w-6 place-items-center rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
            >
              <PanelLeftClose size={14} />
            </Button>
          </>
        )}
        {collapsed && (
          <Button unstyled
            type="button"
            onClick={() => setCollapsed(false)}
            aria-label="Expand sidebar"
            title="Expand sidebar"
            className="grid h-7 w-7 place-items-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors"
          >
            <PanelLeftOpen size={15} />
          </Button>
        )}
      </div>

      {/* Company switcher / brand */}
      {!collapsed && companySlot && (
        <div className="px-3 py-2 border-b border-slate-100">{companySlot}</div>
      )}

      {/* Search */}
      {!collapsed && (
        <div className="px-3 py-2 border-b border-slate-100">
          <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-slate-50 border border-slate-200">
            <svg className="w-3.5 h-3.5 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <span className="text-xs text-slate-400 flex-1">Search cases and providers</span>
            <kbd className="text-[10px] text-slate-300 border border-slate-200 rounded px-1">⌘K</kbd>
          </div>
        </div>
      )}

      {/* Nav */}
      <nav className="flex-1 px-2 pb-4">
        {visibleSections.map((section) => (
          <React.Fragment key={section.label}>
            {!section.borrowed && (
              <SectionHeading
                label={section.label}
                count={section.items.length}
                collapsed={collapsed}
              />
            )}
            {section.items.map((item) => {
              const active = isActive(item);
              const to = resolveItemTo(item);

              let badgeVariant: BadgeVariant | undefined;
              let badgeCount: number | undefined;
              if (item.badge) {
                if (item.badge.kind === 'static') {
                  badgeVariant = item.badge.variant;
                } else if (item.badge.kind === 'static-count') {
                  badgeCount = item.badge.count;
                } else {
                  badgeCount = item.badge.getCount(notifCtx);
                }
              }

              return (
                <React.Fragment key={item.id}>
                <Link
                  to={to}
                  title={item.label}
                  className={`group relative flex items-center gap-2.5 rounded-lg text-sm transition-colors ${
                    collapsed ? 'justify-center px-2 py-2' : 'px-3 py-1.5'
                  } ${
                    active
                      ? 'bg-[#0b2b43]/8 text-[#0b2b43] font-medium'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
                >
                  <NavIcon
                    id={item.id}
                    size={15}
                    className={`shrink-0 ${active ? 'opacity-100' : 'opacity-75 group-hover:opacity-100'}`}
                  />
                  {!collapsed && (
                    <>
                      <span className="flex-1 min-w-0">
                        <span className="block truncate">{item.label}</span>
                        {item.hint && (
                          <span className="block truncate text-[10px] leading-tight mt-0.5 font-normal text-slate-400 group-hover:text-slate-500">
                            {item.hint}
                          </span>
                        )}
                      </span>
                      <Badge count={badgeCount} variant={badgeVariant} />
                    </>
                  )}
                  {collapsed && badgeCount !== undefined && badgeCount > 0 && (
                    <span aria-hidden="true" className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-blue-500" />
                  )}
                  {collapsed && badgeVariant === 'new' && (
                    <span aria-hidden="true" className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-accent-500" />
                  )}
                  {collapsed && badgeVariant === 'live' && (
                    <span aria-hidden="true" className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  )}
                  {/* Tooltip when collapsed */}
                  {collapsed && (
                    <span className="pointer-events-none absolute left-full top-1/2 z-40 ml-2 -translate-y-1/2 translate-x-[-4px] whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-[11.5px] font-medium text-white opacity-0 shadow-lg transition-all group-hover:translate-x-0 group-hover:opacity-100">
                      {item.label}
                    </span>
                  )}
                </Link>

                {/* NAV-EMP-1: compact journey-progress indicator under "My cases"
                    for employees with an active linked case. Hidden when collapsed. */}
                {item.id === 'intake' && role === 'EMPLOYEE' && !collapsed && activeJourneyRow && (
                  <JourneyProgressMini row={activeJourneyRow} />
                )}

                {/* NAV-POL-1: indented sub-items deep-linking to the parent's
                    ?tab= variants. Always visible when expanded so every step is
                    reachable directly from the sidebar (hidden when collapsed). */}
                {!collapsed && item.children && (
                  <div className="ml-7 mb-1 mt-0.5 flex flex-col gap-0.5 border-l border-slate-200 pl-2">
                    {item.children.map((child) => {
                      const childActive = isChildActive(child.to);
                      return (
                        <Link
                          key={child.id}
                          to={child.to}
                          title={child.label}
                          className={`block truncate rounded-md px-2 py-1 text-[13px] transition-colors ${
                            childActive
                              ? 'text-[#0b2b43] font-medium bg-[#0b2b43]/8'
                              : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
                          }`}
                        >
                          {child.label}
                        </Link>
                      );
                    })}
                  </div>
                )}
                </React.Fragment>
              );
            })}
          </React.Fragment>
        ))}
      </nav>

      {/* User footer */}
      <div className="px-3 py-3 border-t border-slate-100">
        <div className={`flex items-center gap-2 ${collapsed ? 'justify-center' : ''}`}>
          <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center text-xs font-semibold text-slate-600 shrink-0">
            {user?.initials ?? 'RP'}
          </div>
          {!collapsed && (
            <>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-slate-900 truncate">{user?.name ?? 'ReloPass'}</p>
                <p className="text-[10px] text-slate-400 truncate">{user?.role ?? role.toLowerCase()}</p>
              </div>
              <Button unstyled aria-label="Account menu" className="text-slate-400 hover:text-slate-600 shrink-0">
                <ChevronRight size={14} />
              </Button>
            </>
          )}
        </div>
      </div>
    </aside>
  );
};

export default PlatformShellSidebar;
