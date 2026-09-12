import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { PanelLeftClose, PanelLeftOpen, ChevronRight, ChevronDown, LogOut, Pencil, Check, RotateCcw } from 'lucide-react';
import { NavIcon, type NavIconId } from '../features/platform-v2/sidebar/navIcons';
import { ROUTE_DEFS, buildRoute } from '../navigation/routes';
import { authAPI } from '../api/client';
import { getHrNotificationCounts, type HrNotificationCounts } from '../api/hrCatalog';
import { getAdminNotificationCounts, type AdminNotificationCounts } from '../api/adminCatalog';
import { getUnreadMessageCount } from '../api/messageNotifications';
import { useSelectedCase } from '../contexts/SelectedCaseContext';
import { useEmployeeAssignment } from '../contexts/EmployeeAssignmentContext';
import { ownedEmployeeCaseId } from '../utils/employeeAssignmentScope';
import { swallow } from '../lib/errorTracking';
import { INTAKE_TOTAL_STEPS } from '../features/platform-v2/intake/intakeSteps';
import { isIntakeComplete } from '../features/employee-journey/caseStage';
import type { EmployeeLinkedOverviewRow } from '../types/employeeAssignmentOverview';
import { Button } from './antigravity/Button';
// Lazy-loaded: the editor pulls in @dnd-kit, which is only needed once the user opens
// "Edit layout". Keeping it out of the eager app-shell chunk holds the bundle budget.
const SidebarLayoutEditor = React.lazy(() =>
  import('./SidebarLayoutEditor').then((m) => ({ default: m.SidebarLayoutEditor })),
);
import {
  filterSectionsForAdminPath,
  adminPersonaFromPath,
  adminPreviewLinks,
} from './adminNavScope';
import {
  readSidebarLayouts,
  writeSectionLayout,
  clearSidebarLayouts,
  reconcileAdminLayout,
  applyAdminLayout,
  type AdminLayoutEntry,
} from './adminSidebarLayout';

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
  // NavIconId (not string) so a nav item whose id has no NAV_ICONS entry fails
  // tsc rather than silently rendering without an icon. `children[].id` below
  // stays `string` — child links render as text only.
  id: NavIconId;
  label: string;
  /** Optional themed sub-group within a section (Admin only today). A small sub-group
   *  label renders at each group boundary; items without a group render flat. */
  group?: string;
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
//
// Section ORDER matters: it's the render order in the sidebar. Admin · ReloPass is
// first so an admin lands on their own surfaces (Home at the top of Usage) rather
// than the borrowed Employee/HR persona-preview sections, which sit below. A lower
// persona never sees the Admin section (rank filter), so their order is unchanged.

const SECTIONS: NavSection[] = [
  {
    label: 'Admin · ReloPass',
    minRole: 'ADMIN',
    // Founder cockpit: Catalog → Usage → Pipeline → Machine.
    // Nested `children` stay at their URLs; Permissions / Admin accounts / Auth page
    // design are parked (still mounted in App.tsx, not listed here).
    items: [
      {
        id: 'coverage',
        group: 'Catalog',
        label: 'Coverage',
        to: ROUTE_DEFS.adminCoverage.path,
      },
      {
        id: 'country-requirements',
        group: 'Catalog',
        label: 'Country requirements',
        to: ROUTE_DEFS.adminCountries.path,
        children: [
          { id: 'requirement-facts', label: 'Requirement facts', to: ROUTE_DEFS.adminRequirementFacts.path },
          { id: 'research-requests', label: 'Research requests', to: ROUTE_DEFS.adminResearchRequests.path },
          { id: 'candidate-beam', label: 'Candidate beam', to: ROUTE_DEFS.adminCandidateBeam.path },
          { id: 'staging', label: 'Staging', to: ROUTE_DEFS.adminStagingDashboard.path },
          { id: 'freshness', label: 'Freshness / crawl', to: ROUTE_DEFS.adminFreshness.path },
          { id: 'review-queue', label: 'Review queue', to: ROUTE_DEFS.adminReviewQueue.path },
          { id: 'integrations', label: 'Catalog queue', to: ROUTE_DEFS.adminCatalogQueue.path },
          { id: 'resources-cms', label: 'Resources CMS', to: ROUTE_DEFS.adminResources.path },
          { id: 'form-templates', label: 'Form templates', to: ROUTE_DEFS.adminFormTemplates.path },
        ],
      },
      { id: 'content-review', group: 'Catalog', label: 'Content review', to: ROUTE_DEFS.adminContentReview.path },
      {
        id: 'admin-policies',
        group: 'Catalog',
        label: 'Policy workspace',
        to: ROUTE_DEFS.adminPolicies.path,
        children: [
          { id: 'policy-versions', label: 'Policy versions', to: ROUTE_DEFS.adminPolicyVersions.path },
        ],
      },
      {
        id: 'admin-suppliers',
        group: 'Catalog',
        label: 'Suppliers',
        to: ROUTE_DEFS.adminSuppliers.path,
        badge: { kind: 'dynamic', getCount: (c) => c.admin?.pending_capabilities ?? 0 },
        children: [
          { id: 'supplier-registry', label: 'Registry', to: ROUTE_DEFS.adminSuppliersRegistry.path },
          { id: 'vetting-queue', label: 'Vetting queue', to: ROUTE_DEFS.adminVettingQueue.path },
          { id: 'supplier-submissions', label: 'Supplier submissions', to: ROUTE_DEFS.adminSupplierSubmissions.path },
        ],
      },

      {
        id: 'admin-overview',
        group: 'Usage',
        label: 'Home',
        to: ROUTE_DEFS.adminConsole.path,
        exact: true,
        children: [
          { id: 'executive', label: 'Executive', to: ROUTE_DEFS.adminExecutive.path },
          { id: 'ops-analytics', label: 'Ops analytics', to: ROUTE_DEFS.adminOps.path },
        ],
      },
      { id: 'admin-companies', group: 'Usage', label: 'Companies', to: ROUTE_DEFS.adminCompanies.path },
      { id: 'admin-assignments', group: 'Usage', label: 'Assignments', hint: 'Per-relocation controls', to: ROUTE_DEFS.adminAssignments.path },
      { id: 'admin-people', group: 'Usage', label: 'People', to: ROUTE_DEFS.adminPeople.path },
      { id: 'feedback-console', group: 'Usage', label: 'Feedback', to: ROUTE_DEFS.adminFeedback.path },

      {
        id: 'prospects',
        group: 'Pipeline',
        label: 'Prospects',
        to: ROUTE_DEFS.adminProspects.path,
        children: [
          { id: 'leads', label: 'Leads', to: ROUTE_DEFS.adminLeads.path },
          { id: 'marketing-analytics', label: 'Marketing analytics', to: ROUTE_DEFS.adminMarketingAnalytics.path },
        ],
      },
      { id: 'outreach', group: 'Pipeline', label: 'Outreach', to: ROUTE_DEFS.adminOutreach.path },
      { id: 'test-drive', group: 'Pipeline', label: 'Test Drive', to: ROUTE_DEFS.adminTestDrive.path },

      { id: 'feature-flags', group: 'Machine', label: 'Feature flags', to: ROUTE_DEFS.adminFeatureFlags.path },
      {
        id: 'ai-governance',
        group: 'Machine',
        label: 'AI governance',
        to: ROUTE_DEFS.adminAiControls.path,
        children: [
          { id: 'rag-quality', label: 'RAG quality', to: ROUTE_DEFS.adminRagQuality.path },
          { id: 'ai-economics', label: 'AI economics', to: ROUTE_DEFS.adminAiUnitEconomics.path },
          { id: 'prompts', label: 'Prompts', to: ROUTE_DEFS.adminPrompts.path },
        ],
      },
      { id: 'data-rights', group: 'Machine', label: 'Data-rights desk', to: ROUTE_DEFS.adminDsar.path },
      { id: 'audit-log', group: 'Machine', label: 'Audit log', to: ROUTE_DEFS.adminAuditLog.path },
    ],
  },
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
      {
        id: 'roadmap',
        label: 'Roadmap',
        to: ROUTE_DEFS.employeeDashboard.path,
        // fix: AIQ-2359 — never emit another user's case UUID when this account is unlinked
        hidden: ({ linkedCount, role, assignmentsLoading }) =>
          role !== 'ADMIN' && !assignmentsLoading && linkedCount === 0,
      },
      { id: 'documents', label: 'Tasks', hint: 'Documents and actions requested by your HR team', to: ROUTE_DEFS.employeeTaskPage.path },
      {
        id: 'dossier',
        label: 'Dossier & forms',
        to: ROUTE_DEFS.employeeDashboard.path,
        hidden: ({ linkedCount, role, assignmentsLoading }) =>
          role !== 'ADMIN' && !assignmentsLoading && linkedCount === 0,
      },
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
      // [AIQ-2086] Relocations + Employees were absent from this sidebar entirely.
      //
      // /hr/dashboard is the ONLY surface with the new-case form (HrDashboard's
      // openNewCaseForm), and it was reachable only via the command centre's "Manage
      // cases" button — one page deep, from a control whose label does not suggest
      // "create". /hr/employees was worse: its only inbound links were the command
      // centre's `noCasesYet` empty-state CTA ("Import your team roster") and the
      // back-link on its own detail page, so the roster became unreachable the moment
      // a company had one case and the empty state stopped rendering.
      { id: 'relocations', label: 'Cases', hint: 'Case list and the new-case form', to: ROUTE_DEFS.hrDashboard.path, exact: true },
      { id: 'employees', label: 'Employees', hint: 'Your team roster', to: ROUTE_DEFS.hrEmployees.path, exact: true },
      { id: 'risk', label: 'Risk', to: ROUTE_DEFS.hrRisk.path, exact: true },
      { id: 'duty-of-care', label: 'Duty of care', to: ROUTE_DEFS.hrDutyOfCare.path, exact: true },
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
];

// Items pinned to the very top of the sidebar, above every section (so the Inbox sits
// above Admin · ReloPass, independent of any section). They're rendered standalone and
// filtered out of their section so they never appear twice or inside the layout editor.
const PINNED_TOP_IDS = new Set<string>(['inbox']);
const INBOX_ITEM = SECTIONS.flatMap((s) => s.items).find((i) => i.id === 'inbox');

// ── Sub-pieces ────────────────────────────────────────────────────────────────

const Badge: React.FC<{ count?: number; variant?: BadgeVariant }> = ({ count, variant = 'count' }) => {
  if (variant === 'new') {
    return (
      <span className="ml-auto px-1.5 py-0.5 rounded text-xs font-bold bg-accent-50 text-accent-700 border border-accent-100">
        NEW
      </span>
    );
  }
  if (variant === 'live') {
    return (
      <span className="ml-auto px-1.5 py-0.5 rounded text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-100">
        LIVE
      </span>
    );
  }
  if (!count || count <= 0) return null;
  return (
    <span className="ml-auto min-w-[1.25rem] px-1 text-center rounded-full bg-slate-200 text-slate-700 text-xs font-semibold leading-5">
      {count > 99 ? '99+' : count}
    </span>
  );
};

const InboxCount: React.FC<{ count: number }> = ({ count }) => (
  <span className="ml-auto min-w-[1.25rem] px-1 text-center rounded-full bg-accent-50 text-accent-700 text-xs font-semibold leading-5">
    {count > 99 ? '99+' : count}
  </span>
);

const SectionHeading: React.FC<{
  label: string;
  count?: number;
  collapsed: boolean;
  folded?: boolean;
  onToggle?: () => void;
}> = ({ label, count, collapsed, folded, onToggle }) => {
  // Icon-collapsed sidebar: no fold affordance, just a divider between sections (as before).
  if (collapsed) return <div className="mt-3 mx-2 border-t border-slate-100" aria-hidden="true" />;
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={!folded}
      className="group w-full flex items-center gap-1.5 px-3 pt-5 pb-1 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43]/30"
    >
      {folded ? (
        <ChevronRight size={12} className="shrink-0 text-slate-500 group-hover:text-slate-700" aria-hidden="true" />
      ) : (
        <ChevronDown size={12} className="shrink-0 text-slate-500 group-hover:text-slate-700" aria-hidden="true" />
      )}
      <span className="text-xs font-semibold tracking-widest uppercase text-slate-600 group-hover:text-slate-700">{label}</span>
      {count !== undefined && <span className="text-xs text-slate-600 font-medium">{count}</span>}
    </button>
  );
};

/** Catalog / Usage / Pipeline / Machine — the small sub-titles inside a section. */
const GroupHeading: React.FC<{
  label: string;
  folded: boolean;
  bordered: boolean;
  onToggle: () => void;
}> = ({ label, folded, bordered, onToggle }) => (
  <button
    type="button"
    onClick={onToggle}
    aria-expanded={!folded}
    className={`group flex min-h-11 w-full items-center gap-1 rounded px-3 mb-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43]/30 ${
      bordered ? 'mt-3 pt-2 border-t border-slate-100' : 'mt-1'
    }`}
  >
    {folded ? (
      <ChevronRight size={11} className="shrink-0 text-slate-500 group-hover:text-slate-700" aria-hidden="true" />
    ) : (
      <ChevronDown size={11} className="shrink-0 text-slate-500 group-hover:text-slate-700" aria-hidden="true" />
    )}
    <span className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-600 group-hover:text-slate-700">
      {label}
    </span>
  </button>
);

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

/** Poll `run` immediately and every `ms`, but skip ticks while the tab is hidden
 *  and fire once when `visibilitychange` returns to visible. */
export function subscribeVisibleInterval(
  run: () => void,
  ms: number,
  onStop?: () => void,
): () => void {
  const tick = () => {
    if (typeof document !== 'undefined' && document.visibilityState !== 'visible') return;
    run();
  };
  tick();
  const intervalId = window.setInterval(tick, ms);
  const onVisibility = () => {
    if (document.visibilityState === 'visible') run();
  };
  document.addEventListener('visibilitychange', onVisibility);
  return () => {
    onStop?.();
    window.clearInterval(intervalId);
    document.removeEventListener('visibilitychange', onVisibility);
  };
}

// ── Props ─────────────────────────────────────────────────────────────────────

export interface PlatformShellSidebarProps {
  role: SidebarRole;
  /** Optional slot for the company widget under the brand (CompanySwitcher / CompanyBrand). */
  companySlot?: React.ReactNode;
  /** Same brand, rendered mark-only for the 64px collapsed rail. */
  collapsedCompanySlot?: React.ReactNode;
  /** Footer identity. Defaults to a sensible placeholder if absent. */
  user?: { initials: string; name: string; role: string };
}

// ── Collapse persistence ──────────────────────────────────────────────────────

const COLLAPSE_KEY = 'platform_sidebar_collapsed';
const COLLAPSE_EXPLICIT_KEY = 'platform_sidebar_collapsed_explicit';

function readCollapsed(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    const explicit = window.localStorage.getItem(COLLAPSE_EXPLICIT_KEY) === '1';
    const collapsed = window.localStorage.getItem(COLLAPSE_KEY) === '1';
    if (window.matchMedia('(min-width: 1280px)').matches && !explicit) {
      return false;
    }
    return collapsed;
  } catch {
    return false;
  }
}

// Per-section fold (independent of the whole-sidebar icon-collapse above). Keyed by
// section label → folded?. Default (absent) = expanded. Persisted + cross-tab synced.
const FOLD_KEY = 'platform_sidebar_sections_v1';
const GROUP_FOLD_KEY = 'platform_sidebar_groups_v1';
const CHILD_FOLD_KEY = 'platform_sidebar_item_children_v1';

function groupFoldId(sectionLabel: string, group: string): string {
  return `${sectionLabel}::${group}`;
}

function readFolded(): Record<string, boolean> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(FOLD_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, boolean>) : {};
  } catch {
    return {};
  }
}

// Sidebar scroll position. The whole page tree (incl. this sidebar) remounts on every
// route change, so without this the <aside> resets to scrollTop=0 on each navigation and
// the user loses their place in a long nav. sessionStorage (per-tab, ephemeral) is the
// right scope — it should not persist across a full browser restart like the fold state.
const SCROLL_KEY = 'platform_sidebar_scroll';

// ── Component ─────────────────────────────────────────────────────────────────

export const PlatformShellSidebar: React.FC<PlatformShellSidebarProps> = ({
  role,
  companySlot,
  collapsedCompanySlot,
  user,
}) => {
  const location = useLocation();
  const asideRef = useRef<HTMLElement | null>(null);
  const [collapsed, setCollapsed] = useState<boolean>(() => readCollapsed());

  // Restore the sidebar scroll position before paint (the aside remounts on navigation).
  useLayoutEffect(() => {
    const el = asideRef.current;
    if (!el) return;
    try {
      const raw = window.sessionStorage.getItem(SCROLL_KEY);
      const top = raw ? Number(raw) : 0;
      if (Number.isFinite(top) && top > 0) el.scrollTop = top;
    } catch {
      /* ignore */
    }
  }, []);
  const handleSidebarScroll = () => {
    const el = asideRef.current;
    if (!el) return;
    try {
      window.sessionStorage.setItem(SCROLL_KEY, String(el.scrollTop));
    } catch {
      /* ignore */
    }
  };

  // Footer account menu (name / role / sign out). Shared by every persona shell, so this
  // is the single standard sign-out across employee, HR and admin.
  const [accountOpen, setAccountOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const accountRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!accountOpen) return;
    const onDown = (e: MouseEvent) => {
      if (accountRef.current && !accountRef.current.contains(e.target as Node)) setAccountOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [accountOpen]);
  const handleSignOut = async () => {
    if (signingOut) return;
    setSigningOut(true);
    try {
      await authAPI.logout();
      // Mirror AppShell's LogoutButton: land on the login page, not the marketing home.
      window.location.replace(buildRoute('login'));
    } catch {
      setSigningOut(false);
    }
  };

  // Sidebar customisation: reorder tabs, move them between sub-groups, and rename groups
  // — for EVERY section (Admin, Employee, HR), not just Admin. Persisted per browser and
  // per section; reconciled against code so it survives new/removed tabs. No override for
  // a section → its code order is used verbatim.
  const sectionLabels = useMemo(
    () =>
      Object.fromEntries(
        SECTIONS.map((s) => [s.label, Object.fromEntries(s.items.map((i) => [i.id, i.label]))]),
      ) as Record<string, Record<string, string>>,
    [],
  );
  const [layoutOverrides, setLayoutOverrides] = useState<Record<string, AdminLayoutEntry[]>>(
    () => readSidebarLayouts(),
  );
  const [editingLayout, setEditingLayout] = useState(false);
  const updateSectionLayout = (sectionLabel: string, next: AdminLayoutEntry[]) => {
    setLayoutOverrides((prev) => ({ ...prev, [sectionLabel]: next }));
    writeSectionLayout(sectionLabel, next);
  };
  const resetLayout = () => {
    clearSidebarLayouts();
    setLayoutOverrides({});
  };

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

  // Per-section fold state (label → folded?), persisted + cross-tab synced.
  const [folded, setFolded] = useState<Record<string, boolean>>(() => {
    const stored = readFolded();
    if (typeof window === 'undefined') return stored;
    const mobile = window.matchMedia('(max-width: 767px)').matches;
    if (!mobile || role !== 'ADMIN') return stored;
    return {
      Employee: true,
      'HR Operations': true,
      ...stored,
    };
  });
  useEffect(() => {
    try {
      window.localStorage.setItem(FOLD_KEY, JSON.stringify(folded));
    } catch {
      /* ignore */
    }
  }, [folded]);
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === FOLD_KEY) setFolded(readFolded());
      if (e.key === GROUP_FOLD_KEY) {
        try {
          const parsed: unknown = e.newValue ? JSON.parse(e.newValue) : {};
          setFoldedGroups(parsed && typeof parsed === 'object' ? (parsed as Record<string, boolean>) : {});
        } catch {
          /* ignore */
        }
      }
      if (e.key === CHILD_FOLD_KEY) {
        try {
          const parsed: unknown = e.newValue ? JSON.parse(e.newValue) : {};
          setFoldedChildren(parsed && typeof parsed === 'object' ? (parsed as Record<string, boolean>) : {});
        } catch {
          /* ignore */
        }
      }
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);
  const toggleSection = (label: string) => setFolded((f) => ({ ...f, [label]: !f[label] }));

  const [foldedGroups, setFoldedGroups] = useState<Record<string, boolean>>(() => {
    if (typeof window === 'undefined') return {};
    try {
      const raw = window.localStorage.getItem(GROUP_FOLD_KEY);
      if (!raw) return {};
      const parsed: unknown = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? (parsed as Record<string, boolean>) : {};
    } catch {
      return {};
    }
  });
  const [foldedChildren, setFoldedChildren] = useState<Record<string, boolean>>(() => {
    if (typeof window === 'undefined') return {};
    try {
      const raw = window.localStorage.getItem(CHILD_FOLD_KEY);
      if (!raw) return {};
      const parsed: unknown = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? (parsed as Record<string, boolean>) : {};
    } catch {
      return {};
    }
  });
  useEffect(() => {
    try {
      window.localStorage.setItem(GROUP_FOLD_KEY, JSON.stringify(foldedGroups));
    } catch {
      /* ignore */
    }
  }, [foldedGroups]);
  useEffect(() => {
    try {
      window.localStorage.setItem(CHILD_FOLD_KEY, JSON.stringify(foldedChildren));
    } catch {
      /* ignore */
    }
  }, [foldedChildren]);
  const toggleGroup = (sectionLabel: string, group: string) => {
    const id = groupFoldId(sectionLabel, group);
    setFoldedGroups((f) => ({ ...f, [id]: !f[id] }));
  };
  const toggleItemChildren = (itemId: string) =>
    setFoldedChildren((f) => ({ ...f, [itemId]: f[itemId] === false }));

  // Notification polling — only what the visible sections need
  const [hrNotif, setHrNotif] = useState<HrNotificationCounts | null>(null);
  const [adminNotif, setAdminNotif] = useState<AdminNotificationCounts | null>(null);
  const [inboxUnread, setInboxUnread] = useState<number | null>(null);
  const rank = ROLE_RANK[role];

  useEffect(() => {
    if (rank < ROLE_RANK.HR) return;
    let cancelled = false;
    const fetchHr = () => {
      void getHrNotificationCounts()
        .then((c) => { if (!cancelled) setHrNotif(c); })
        .catch((e) => swallow(e, 'PlatformShellSidebar: HR notification poll'));
    };
    return subscribeVisibleInterval(fetchHr, 60_000, () => { cancelled = true; });
  }, [rank]);

  useEffect(() => {
    if (rank < ROLE_RANK.ADMIN) return;
    let cancelled = false;
    const fetchAdmin = () => {
      void getAdminNotificationCounts()
        .then((c) => { if (!cancelled) setAdminNotif(c); })
        .catch((e) => swallow(e, 'PlatformShellSidebar: admin notification poll'));
    };
    return subscribeVisibleInterval(fetchAdmin, 60_000, () => { cancelled = true; });
  }, [rank]);

  useEffect(() => {
    let cancelled = false;
    const fetchInbox = () => {
      void getUnreadMessageCount()
        .then((n) => { if (!cancelled) setInboxUnread(n); })
        .catch((e) => swallow(e, 'PlatformShellSidebar: inbox unread poll'));
    };
    fetchInbox();
    const id = window.setInterval(fetchInbox, 60_000);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);

  const notifCtx: NotifContext = { hr: hrNotif, admin: adminNotif };

  // Extract caseId from the URL when on a case-scoped employee route
  // e.g. /employee/case/43556892-2f33-4ab1-8533-9c11095e5565/wizard/1 → caseId
  const urlCaseId = location.pathname.match(/\/employee\/case\/([^/]+)/)?.[1] ?? null;

  // Fall back to the last-known caseId (SelectedCaseContext / localStorage), then to the
  // employee's primary linked case, so sidebar links resolve to the case-scoped roadmap/dossier
  // even from /employee/dashboard where there is no case in the URL and nothing was selected yet.
  const { selectedCaseId } = useSelectedCase();
  const { linkedCount, primaryCaseId, linkedSummaries, isLoading: assignmentsLoading } = useEmployeeAssignment();
  // Only a case the employee owns. localStorage / URL UUIDs from an HR session must
  // not become Roadmap/Dossier hrefs for an unlinked account (AIQ-2359).
  const effectiveCaseId = ownedEmployeeCaseId(linkedSummaries, [urlCaseId, selectedCaseId, primaryCaseId]);

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
    if (!childQuery) {
      return location.pathname === childPath || location.pathname.startsWith(`${childPath}/`);
    }
    if (location.pathname !== childPath) return false;
    const childTab = new URLSearchParams(childQuery).get('tab') ?? 'policy';
    const currentTab = new URLSearchParams(location.search).get('tab') ?? 'policy';
    return childTab === currentTab;
  };

  const visibilityCtx: SidebarVisibilityCtx = { role, linkedCount, assignmentsLoading };
  // Apply each section's custom layout (order / group / rename) to the live nav.
  const effectiveSections = SECTIONS.map((s) => ({
    ...s,
    items: applyAdminLayout(s.items, reconcileAdminLayout(s.items, layoutOverrides[s.label] ?? null)),
  }));
  const rankedByRole = effectiveSections
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
          if (PINNED_TOP_IDS.has(item.id)) return false; // rendered standalone at the top
          if (item.hidden?.(visibilityCtx)) return false;
          if (borrowed) return Boolean(item.toByRole?.[role]);
          return true;
        }),
      };
    })
    .filter((s) => s.items.length > 0);
  const visibleSections = filterSectionsForAdminPath(rankedByRole, location.pathname, role);

  return (
    <aside
      ref={asideRef}
      onScroll={handleSidebarScroll}
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
            <span className="text-slate-500 text-sm">/ Platform</span>
            <Button unstyled
              type="button"
              onClick={() => {
                try { window.localStorage.setItem(COLLAPSE_EXPLICIT_KEY, '1'); } catch { /* ignore */ }
                setCollapsed(true);
              }}
              aria-label="Collapse sidebar"
              title="Collapse sidebar"
              className="ml-auto grid h-11 w-11 place-items-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors"
            >
              <PanelLeftClose size={14} />
            </Button>
          </>
        )}
        {collapsed && (
          <Button unstyled
            type="button"
            onClick={() => {
              try { window.localStorage.setItem(COLLAPSE_EXPLICIT_KEY, '1'); } catch { /* ignore */ }
              setCollapsed(false);
            }}
            aria-label="Expand sidebar"
            title="Expand sidebar"
            className="grid h-11 w-11 place-items-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors"
          >
            <PanelLeftOpen size={15} />
          </Button>
        )}
      </div>

      {/* Company switcher / brand */}
      {companySlot && (
        <div className={`${collapsed ? 'px-2 py-2 flex justify-center' : 'px-3 py-2'} border-b border-slate-100`}>
          {collapsed ? collapsedCompanySlot ?? companySlot : companySlot}
        </div>
      )}

      {/* AIQ-1453: removed the decorative non-functional "Search cases and providers"
          box (a static span + ⌘K kbd with no input/handler) — it read as a dead-end. */}

      {/* Nav */}
      <nav className="flex-1 px-2 pb-4">
        {/* Inbox pinned above every section (incl. Admin · ReloPass), independent of any
            section and of the layout editor. */}
        {INBOX_ITEM && (
          <div className="pt-2">
            <Link
              to={resolveItemTo(INBOX_ITEM)}
              title="Inbox"
              aria-current={isActive(INBOX_ITEM) ? 'page' : undefined}
              aria-label={inboxUnread && inboxUnread > 0 ? `Inbox (${inboxUnread} unread)` : 'Inbox'}
              className={`group relative flex items-center gap-2.5 rounded-lg text-sm transition-colors min-h-11 ${
                collapsed ? 'justify-center px-2 py-2' : 'px-3 py-1.5'
              } ${
                isActive(INBOX_ITEM)
                  ? 'bg-[#0b2b43]/8 text-[#0b2b43] font-medium'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
              }`}
            >
              <NavIcon
                id="inbox"
                size={15}
                className={`shrink-0 ${isActive(INBOX_ITEM) ? 'opacity-100' : 'opacity-75 group-hover:opacity-100'}`}
              />
              {!collapsed && <span className="min-w-0 flex-1 truncate">Inbox</span>}
              {!collapsed && inboxUnread !== null && inboxUnread > 0 && <InboxCount count={inboxUnread} />}
              {collapsed && inboxUnread !== null && inboxUnread > 0 && (
                <span aria-hidden="true" className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-accent-500" />
              )}
              {collapsed && (
                <span className="pointer-events-none absolute left-full top-1/2 z-40 ml-2 -translate-y-1/2 translate-x-[-4px] whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-[11.5px] font-medium text-white opacity-0 shadow-lg transition-all group-hover:translate-x-0 group-hover:opacity-100">
                  Inbox
                </span>
              )}
            </Link>
            {!collapsed && <div className="mt-2 mx-1 border-t border-slate-100" aria-hidden="true" />}
          </div>
        )}
        {role === 'ADMIN' && !collapsed && editingLayout ? (
          <div className="pb-2">
            {/* One Done/Reset header for the whole sidebar; every visible section below
                becomes independently draggable. Admin sees all three sections here, so
                "all sections" is covered from the one place that renders them. */}
            <div className="flex items-center justify-between px-2 pt-3 pb-1">
              <span className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">Edit layout</span>
              <div className="flex items-center gap-1">
                <Button
                  unstyled
                  type="button"
                  onClick={resetLayout}
                  title="Reset all sections to default"
                  className="flex items-center gap-1 rounded px-1.5 py-1 text-[11px] text-slate-500 hover:bg-slate-100 hover:text-slate-700"
                >
                  <RotateCcw size={12} /> Reset
                </Button>
                <Button
                  unstyled
                  type="button"
                  onClick={() => setEditingLayout(false)}
                  title="Done editing"
                  className="flex items-center gap-1 rounded bg-[#0b2b43] px-2 py-1 text-[11px] font-medium text-white hover:bg-[#0d3456]"
                >
                  <Check size={12} /> Done
                </Button>
              </div>
            </div>
            <p className="px-2 pb-1 text-[11px] leading-tight text-slate-500">
              Drag tabs to reorder or move them between sub-groups. Click a group name to rename it.
            </p>
            <React.Suspense fallback={<p className="px-2 py-2 text-[11px] text-slate-500">Loading editor…</p>}>
              {visibleSections
                .filter((section) => !section.borrowed)
                .map((section) => {
                  const codeItems =
                    SECTIONS.find((s) => s.label === section.label)?.items.filter(
                      (i) => !PINNED_TOP_IDS.has(i.id),
                    ) ?? [];
                  const layout = reconcileAdminLayout(codeItems, layoutOverrides[section.label] ?? null);
                  return (
                    <SidebarLayoutEditor
                      key={section.label}
                      sectionTitle={section.label}
                      layout={layout}
                      labels={sectionLabels[section.label] ?? {}}
                      onChange={(next) => updateSectionLayout(section.label, next)}
                    />
                  );
                })}
            </React.Suspense>
          </div>
        ) : (
          <>
            {role === 'ADMIN' && !collapsed && (
              <div className="flex justify-end px-1 pt-2">
                <Button
                  unstyled
                  type="button"
                  onClick={() => setEditingLayout(true)}
                  title="Customise the sidebar"
                  className="flex min-h-11 items-center gap-1 rounded px-2 py-1 text-[11px] font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-600"
                >
                  <Pencil size={11} /> Edit layout
                </Button>
              </div>
            )}
            {visibleSections.map((section) => {
          const isFolded = !collapsed && !section.borrowed && Boolean(folded[section.label]);
          return (
          <React.Fragment key={section.label}>
            {!section.borrowed && (
              <SectionHeading
                label={
                  role === 'ADMIN' && section.minRole !== 'ADMIN'
                    ? `Preview · ${section.label}`
                    : section.label
                }
                count={section.items.length}
                collapsed={collapsed}
                folded={Boolean(folded[section.label])}
                onToggle={() => toggleSection(section.label)}
              />
            )}
            {!isFolded && section.items.map((item, idx) => {
              const anyChildActive = Boolean(item.children?.some((c) => isChildActive(c.to)));
              const active = isActive(item) || anyChildActive;
              const to = resolveItemTo(item);
              const showGroupLabel = !collapsed && !!item.group && item.group !== section.items[idx - 1]?.group;
              const groupFolded =
                !collapsed &&
                !!item.group &&
                Boolean(foldedGroups[groupFoldId(section.label, item.group)]);
              const childrenFolded = foldedChildren[item.id] !== false && !anyChildActive;

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
                {showGroupLabel && item.group && (
                  <GroupHeading
                    label={item.group}
                    folded={groupFolded}
                    bordered={idx > 0}
                    onToggle={() => toggleGroup(section.label, item.group!)}
                  />
                )}
                {!groupFolded && (
                <>
                <div className={`group relative flex items-center ${collapsed ? '' : 'gap-0.5'}`}>
                <Link
                  to={to}
                  title={item.hint ?? item.label}
                  aria-current={isActive(item) ? 'page' : undefined}
                  className={`relative flex min-w-0 flex-1 items-center gap-2.5 rounded-lg text-sm transition-colors min-h-11 ${
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
                      <span className="flex-1 min-w-0 text-pretty">{item.label}</span>
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
                  {collapsed && (
                    <span className="pointer-events-none absolute left-full top-1/2 z-40 ml-2 -translate-y-1/2 translate-x-[-4px] whitespace-nowrap rounded-md bg-slate-900 px-2 py-1 text-[11.5px] font-medium text-white opacity-0 shadow-lg transition-all group-hover:translate-x-0 group-hover:opacity-100">
                      {item.label}
                    </span>
                  )}
                </Link>
                {!collapsed && item.children && item.children.length > 0 && (
                  <Button
                    unstyled
                    type="button"
                    aria-label={childrenFolded ? `Show ${item.label} pages` : `Hide ${item.label} pages`}
                    aria-expanded={!childrenFolded}
                    title={childrenFolded ? 'Show sub-pages' : 'Hide sub-pages'}
                    onClick={() => toggleItemChildren(item.id)}
                    className="grid h-11 w-11 shrink-0 place-items-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                  >
                    {childrenFolded ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
                  </Button>
                )}
                </div>

                {item.id === 'intake' && role === 'EMPLOYEE' && !collapsed && activeJourneyRow && (
                  <JourneyProgressMini row={activeJourneyRow} />
                )}

                {!collapsed && item.children && !childrenFolded && (
                  <div className="ml-7 mb-1 mt-0.5 flex flex-col gap-0.5 border-l border-slate-200 pl-2">
                    {item.children.map((child) => {
                      const childActive = isChildActive(child.to);
                      return (
                        <Link
                          key={child.id}
                          to={child.to}
                          title={child.label}
                          className={`block truncate rounded-md px-2 py-1 text-[13px] transition-colors min-h-11 ${
                            childActive
                              ? 'text-[#0b2b43] font-medium bg-[#0b2b43]/8'
                              : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
                          }`}
                          aria-current={childActive ? 'page' : undefined}
                        >
                          {child.label}
                        </Link>
                      );
                    })}
                  </div>
                )}
                </>
                )}
                </React.Fragment>
              );
            })}
          </React.Fragment>
          );
        })}
          </>
        )}
      </nav>

      {role === 'ADMIN' && !collapsed && (
        <div className="px-3 py-2 border-t border-slate-100 space-y-1">
          {adminPreviewLinks(adminPersonaFromPath(location.pathname)).map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className="block rounded-md px-2 py-2 text-[12px] font-medium text-navy-800 hover:bg-navy-50 min-h-11"
            >
              {link.label}
            </Link>
          ))}
        </div>
      )}

      {/* User footer */}
      <div ref={accountRef} className="relative px-3 py-3 border-t border-slate-100">
        {/* Account popover — name / role / sign out. Rendered above the footer since it
            sits at the bottom of the sidebar. */}
        {accountOpen && !collapsed && (
          <div
            role="menu"
            aria-label="Account"
            className="absolute bottom-full left-3 right-3 mb-2 rounded-lg border border-slate-200 bg-white p-1 shadow-lg"
          >
            <div className="px-2 py-1.5">
              <p className="text-xs font-medium text-slate-900 truncate">{user?.name ?? 'ReloPass'}</p>
              <p className="text-xs text-slate-600 truncate">{user?.role ?? role.toLowerCase()}</p>
            </div>
            <div className="my-1 border-t border-slate-100" />
            <Button unstyled
              type="button"
              role="menuitem"
              onClick={handleSignOut}
              disabled={signingOut}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs text-slate-600 hover:bg-slate-100 hover:text-slate-900 disabled:opacity-60"
            >
              <LogOut size={13} className="shrink-0" />
              {signingOut ? 'Signing out…' : 'Sign out'}
            </Button>
          </div>
        )}
        <div className={`flex items-center gap-2 ${collapsed ? 'justify-center' : ''}`}>
          <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center text-xs font-semibold text-slate-600 shrink-0">
            {user?.initials ?? 'RP'}
          </div>
          {!collapsed && (
            <>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-slate-900 truncate">{user?.name ?? 'ReloPass'}</p>
                <p className="text-xs text-slate-600 truncate">{user?.role ?? role.toLowerCase()}</p>
              </div>
              <Button unstyled
                type="button"
                aria-label="Account menu"
                aria-haspopup="menu"
                aria-expanded={accountOpen}
                onClick={() => setAccountOpen((o) => !o)}
                className="grid h-11 w-11 shrink-0 place-items-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-600"
              >
                {accountOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </Button>
            </>
          )}
        </div>
      </div>
    </aside>
  );
};

export default PlatformShellSidebar;
