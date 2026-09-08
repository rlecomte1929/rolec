/**
 * ReloPass Case Command — Case Intelligence layer (Deliverable 4).
 *
 * Thin UI-side resolver over the Rule DSL engine output (Deliverable 3).
 * The engine instantiates CaseObligations per case in WorkspaceDB
 * (case_obligations + obligations + obligation_types + obligation_dependencies).
 * This module joins those rows client-side into render-ready view models and
 * carries the deterministic engine snapshot used for the Sarah Chen demo case.
 * No rule evaluation happens here — statuses, due dates, and flag messages
 * come from the engine's data layer as-is.
 */

import { isoToEpochDays } from './rule-engine';

export type ObligationStatus =
  | 'pending'
  | 'in_progress'
  | 'blocked'
  | 'completed'
  | 'waived'
  | 'not_applicable';

export type DependencyEdgeType = 'blocks' | 'informs' | 'parallel';

// ─── Raw row shapes — mirror the WorkspaceDB tables written by the engine ───

export interface CaseObligationRow {
  id: number;
  case_id: number;
  obligation_id: number;
  obligation_type_id: number;
  status: string;
  due_date: string | null;
  completed_at: string | null;
  waived_reason?: string | null;
  assigned_to: string | null;
  notes: string | null;
}

export interface ObligationDefRow {
  id: number;
  obligation_type_id: number;
  name_override: string | null;
  description_override: string | null;
  deadline_notes?: string | null;
}

export interface ObligationTypeRow {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  is_non_obvious: boolean;
  flag_message: string | null;
  obligation_category: string | null;
}

export interface DependencyRow {
  id: number;
  obligation_id: number;
  depends_on_obligation_id: number;
  edge_type: string;
  notes?: string | null;
}

// ─── Resolved view models ────────────────────────────────────────────────────

/** Upstream dependency resolved against the same case's obligation instances. */
export interface ResolvedDependency {
  edgeType: DependencyEdgeType;
  upstreamName: string;
  /** Live status of the upstream obligation on this case; null when the engine did not instantiate it. */
  upstreamStatus: ObligationStatus | null;
  note: string | null;
}

export interface ResolvedObligation {
  key: string;
  name: string;
  description: string;
  status: ObligationStatus;
  dueDate: string | null;
  completedAt: string | null;
  assignedTo: string | null;
  notes: string | null;
  category: string;
  isNonObvious: boolean;
  flagMessage: string | null;
  /** All DAG edges leaving this obligation (what it depends on). */
  dependencies: ResolvedDependency[];
  /** Hard `blocks` edges whose upstream obligation is not yet completed/waived. */
  blockedBy: ResolvedDependency[];
}

const KNOWN_STATUSES: ObligationStatus[] = [
  'pending', 'in_progress', 'blocked', 'completed', 'waived', 'not_applicable',
];

function normalizeStatus(raw: string): ObligationStatus {
  return (KNOWN_STATUSES as string[]).includes(raw) ? (raw as ObligationStatus) : 'pending';
}

function normalizeEdge(raw: string): DependencyEdgeType {
  return raw === 'blocks' || raw === 'parallel' ? raw : 'informs';
}

/** Normalize a DB date/timestamp value to 'YYYY-MM-DD' (or null). */
export function isoDay(value: string | null | undefined): string | null {
  if (!value) return null;
  const s = String(value).slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(s) ? s : null;
}

const SATISFIED: ObligationStatus[] = ['completed', 'waived', 'not_applicable'];

/**
 * Join engine rows into render-ready obligations. Pure function — the same
 * rows always produce the same list in the same order (due date ascending,
 * undated items last, ties broken by instance id).
 */
export function resolveObligations(
  rows: CaseObligationRow[],
  defs: ObligationDefRow[],
  types: ObligationTypeRow[],
  deps: DependencyRow[],
): ResolvedObligation[] {
  const defById = new Map(defs.map((d) => [d.id, d]));
  const typeById = new Map(types.map((t) => [t.id, t]));
  const instanceByDefId = new Map(rows.map((r) => [r.obligation_id, r]));

  const nameForDef = (defId: number): string => {
    const def = defById.get(defId);
    const type = def ? typeById.get(def.obligation_type_id) : undefined;
    return def?.name_override || type?.name || `Obligation #${defId}`;
  };

  return rows
    .map((row) => {
      const def = defById.get(row.obligation_id);
      const type =
        typeById.get(row.obligation_type_id) ||
        (def ? typeById.get(def.obligation_type_id) : undefined);

      const dependencies: ResolvedDependency[] = deps
        .filter((e) => e.obligation_id === row.obligation_id)
        .map((e) => {
          const upstream = instanceByDefId.get(e.depends_on_obligation_id);
          return {
            edgeType: normalizeEdge(e.edge_type),
            upstreamName: nameForDef(e.depends_on_obligation_id),
            upstreamStatus: upstream ? normalizeStatus(upstream.status) : null,
            note: e.notes ?? null,
          };
        });

      return {
        key: `ob-${row.id}`,
        name: def?.name_override || type?.name || `Obligation #${row.obligation_id}`,
        description: def?.description_override || type?.description || '',
        status: normalizeStatus(row.status),
        dueDate: isoDay(row.due_date),
        completedAt: isoDay(row.completed_at),
        assignedTo: row.assigned_to,
        notes: row.notes,
        category: type?.obligation_category || 'general',
        isNonObvious: Boolean(type?.is_non_obvious),
        flagMessage: type?.flag_message ?? null,
        dependencies,
        blockedBy: dependencies.filter(
          (d) => d.edgeType === 'blocks' && (d.upstreamStatus === null || !SATISFIED.includes(d.upstreamStatus)),
        ),
        _sortDays: row.due_date ? isoToEpochDays(String(row.due_date).slice(0, 10)) : Number.MAX_SAFE_INTEGER,
        _id: row.id,
      };
    })
    .sort((a, b) => a._sortDays - b._sortDays || a._id - b._id)
    .map(({ _sortDays, _id, ...ob }) => ob);
}

export function isObligationOpen(status: ObligationStatus): boolean {
  return !SATISFIED.includes(status);
}

export function isOverdue(ob: ResolvedObligation, todayIso: string): boolean {
  return Boolean(ob.dueDate && ob.dueDate < todayIso && isObligationOpen(ob.status));
}

export function daysOverdue(dueDate: string, todayIso: string): number {
  return isoToEpochDays(todayIso) - isoToEpochDays(dueDate);
}

export interface ObligationCounts {
  total: number;
  completed: number;
  inProgress: number;
  pending: number;
  blocked: number;
  overdue: number;
}

export function countObligations(list: ResolvedObligation[], todayIso: string): ObligationCounts {
  return {
    total: list.length,
    completed: list.filter((o) => o.status === 'completed').length,
    inProgress: list.filter((o) => o.status === 'in_progress').length,
    pending: list.filter((o) => o.status === 'pending').length,
    blocked: list.filter((o) => o.status === 'blocked').length,
    overdue: list.filter((o) => isOverdue(o, todayIso)).length,
  };
}

// ─── Sarah Chen (Singapore → London) — deterministic engine snapshot ─────────
//
// The live rule catalog covers the France → Norway corridor. For the primary
// showcase case the same engine output shape is authored as a fixed snapshot:
// identical row structures, resolved through the exact same joiner above, so
// the UI renders both sources through one code path.

const SC_TYPES: ObligationTypeRow[] = [
  {
    id: 101,
    code: 'cos_assignment',
    name: 'Certificate of Sponsorship (CoS)',
    is_non_obvious: false,
    flag_message: null,
    obligation_category: 'document',
  },
  {
    id: 102,
    code: 'sg_tax_clearance_ir21',
    name: 'Singapore Tax Clearance (IR21)',
    is_non_obvious: true,
    flag_message:
      'Employer must withhold ALL final salary until IRAS issues clearance — file at least one month before departure. Most HR teams only discover this at final payroll.',
    obligation_category: 'tax',
  },
  {
    id: 103,
    code: 'skilled_worker_visa',
    name: 'Skilled Worker Visa Application',
    is_non_obvious: false,
    flag_message:
      'Priority service gives a 5-working-day decision target after biometrics. Standard processing can exceed 3 weeks and push the move date.',
    obligation_category: 'immigration',
  },
  {
    id: 104,
    code: 'dependant_visas',
    name: 'Dependant Visa Applications',
    is_non_obvious: true,
    flag_message:
      'Dependant applications cannot be decided before the main applicant\u2019s grant — book family travel only after ALL visas are in hand.',
    obligation_category: 'immigration',
  },
  {
    id: 105,
    code: 'right_to_work_check',
    name: 'UK Right-to-Work Check',
    is_non_obvious: false,
    flag_message: null,
    obligation_category: 'compliance',
  },
  {
    id: 106,
    code: 'brp_collection',
    name: 'BRP Collection (10-Day Window)',
    is_non_obvious: true,
    flag_message:
      'Statutory 10-day window after UK entry — missing it is a civil penalty risk and can complicate future visa renewals.',
    obligation_category: 'compliance',
  },
];

const SC_DEFS: ObligationDefRow[] = [
  {
    id: 201,
    obligation_type_id: 101,
    name_override: 'Certificate of Sponsorship — UK Sponsor Licence Holder',
    description_override:
      'The UK entity assigns a CoS under its sponsor licence for the Skilled Worker route. The CoS number is a mandatory field on the visa application.',
  },
  {
    id: 202,
    obligation_type_id: 102,
    name_override: 'Singapore Tax Clearance (IR21) — IRAS',
    description_override:
      'File Form IR21 with IRAS for departure tax clearance. The employer is legally required to withhold the final salary until clearance is received — late filing blocks departure payroll.',
  },
  {
    id: 203,
    obligation_type_id: 103,
    name_override: 'Skilled Worker Visa — UKVI Priority Service',
    description_override:
      'Submit the Skilled Worker application with the CoS number and complete biometrics at VFS Singapore. Priority service targets a 5-working-day decision.',
  },
  {
    id: 204,
    obligation_type_id: 104,
    name_override: 'Dependant Visas — Spouse + Child (Same Batch)',
    description_override:
      'Spouse and child applications filed in the same batch as the main applicant. They cannot be decided before the main Skilled Worker grant.',
  },
  {
    id: 205,
    obligation_type_id: 105,
    name_override: 'Right-to-Work Verification — Before UK Start Date',
    description_override:
      'Verify and file the employee\u2019s right to work in the UK (eVisa / vignette share code) before the first working day, per the UK Immigration Act 2016.',
  },
  {
    id: 206,
    obligation_type_id: 106,
    name_override: 'BRP Collection — Designated Post Office',
    description_override:
      'Collect the Biometric Residence Permit within 10 days of UK entry at the designated Post Office branch named in the decision letter.',
  },
];

const SC_DEPS: DependencyRow[] = [
  {
    id: 301,
    obligation_id: 203,
    depends_on_obligation_id: 201,
    edge_type: 'blocks',
    notes: 'The visa application cannot be submitted without a valid, unexpired CoS number. Hard system requirement on the UKVI form.',
  },
  {
    id: 302,
    obligation_id: 204,
    depends_on_obligation_id: 203,
    edge_type: 'blocks',
    notes: 'UKVI will not decide dependant applications before the main applicant\u2019s Skilled Worker grant. Filed together, decided in sequence.',
  },
  {
    id: 303,
    obligation_id: 205,
    depends_on_obligation_id: 203,
    edge_type: 'blocks',
    notes: 'Right-to-work verification requires the granted visa (eVisa or vignette). Cannot be completed while the application is undecided.',
  },
  {
    id: 304,
    obligation_id: 206,
    depends_on_obligation_id: 203,
    edge_type: 'blocks',
    notes: 'The BRP is only produced after the visa is granted; the 10-day collection clock starts at UK entry.',
  },
  {
    id: 305,
    obligation_id: 202,
    depends_on_obligation_id: 201,
    edge_type: 'informs',
    notes: 'IR21 timing is planned against the confirmed move date once the CoS locks the UK start date. No hard block — run in parallel.',
  },
];

const SC_ROWS: CaseObligationRow[] = [
  {
    id: 401,
    case_id: 0,
    obligation_id: 201,
    obligation_type_id: 101,
    status: 'completed',
    due_date: '2026-06-05',
    completed_at: '2026-06-01',
    assigned_to: 'employer',
    notes: 'CoS assigned under the active sponsor licence. CoS number on file for the visa application.',
  },
  {
    id: 402,
    case_id: 0,
    obligation_id: 202,
    obligation_type_id: 102,
    status: 'in_progress',
    due_date: '2026-07-08',
    completed_at: null,
    assigned_to: 'employer',
    notes: 'Form IR21 filed with IRAS; clearance pending. Escalated to Deloitte engagement partner — must land before the 14 Aug departure payroll.',
  },
  {
    id: 403,
    case_id: 0,
    obligation_id: 203,
    obligation_type_id: 103,
    status: 'in_progress',
    due_date: '2026-07-28',
    completed_at: null,
    assigned_to: 'applicant',
    notes: 'Biometrics completed at VFS Singapore. Priority-service decision expected by 28 Jul.',
  },
  {
    id: 404,
    case_id: 0,
    obligation_id: 204,
    obligation_type_id: 104,
    status: 'blocked',
    due_date: '2026-08-10',
    completed_at: null,
    assigned_to: 'applicant',
    notes: 'Filed in the same batch. Family travel booking held until all dependant grants are issued.',
  },
  {
    id: 405,
    case_id: 0,
    obligation_id: 205,
    obligation_type_id: 105,
    status: 'pending',
    due_date: '2026-08-16',
    completed_at: null,
    assigned_to: 'employer',
    notes: 'Share-code check scheduled against the UK start date.',
  },
  {
    id: 406,
    case_id: 0,
    obligation_id: 206,
    obligation_type_id: 106,
    status: 'pending',
    due_date: '2026-08-25',
    completed_at: null,
    assigned_to: 'applicant',
    notes: 'Designated Post Office: Canary Wharf branch. 10-day window opens at UK entry on 15 Aug.',
  },
];

/** Deterministic snapshot for the primary demo case — same resolver, same shape. */
export const SARAH_CHEN_OBLIGATIONS: ResolvedObligation[] = resolveObligations(
  SC_ROWS,
  SC_DEFS,
  SC_TYPES,
  SC_DEPS,
);
