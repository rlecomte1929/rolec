/**
 * GlobeIQ Relocation Tasks — demo task data for mobility coordinators.
 * Tasks link to active relocation cases across immigration, compliance, and logistics.
 */

export type TaskPriority = 'High' | 'Medium' | 'Low';
export type TaskStatus = 'To Do' | 'In Progress' | 'Done';
export type TaskCategory = 'immigration' | 'compliance' | 'logistics';

export interface RelocationTaskSeed {
  task_name: string;
  assigned_owner: string;
  due_date: string;
  priority: TaskPriority;
  status: TaskStatus;
  case_id: string;
  case_reference: string;
  category: TaskCategory;
}

export interface RelocationTask extends RelocationTaskSeed {
  id: number;
  created_at?: string;
  updated_at?: string;
}

export const TASK_STATUSES: TaskStatus[] = ['To Do', 'In Progress', 'Done'];
export const TASK_PRIORITIES: TaskPriority[] = ['High', 'Medium', 'Low'];
export const TASK_CATEGORIES: TaskCategory[] = ['immigration', 'compliance', 'logistics'];

/** Pre-loaded tasks spanning active GlobeIQ relocation corridors */
export const SAMPLE_TASKS: RelocationTaskSeed[] = [
  // Immigration
  {
    task_name: 'Submit dependent MVV applications',
    assigned_owner: 'Amara Diallo',
    due_date: '2026-07-18',
    priority: 'High',
    status: 'In Progress',
    case_id: 'case-marcus-obi',
    case_reference: 'Marcus Obi — Lagos → Amsterdam',
    category: 'immigration',
  },
  {
    task_name: 'Chase apostille for dependant birth certificates',
    assigned_owner: 'Employee + Local agent',
    due_date: '2026-07-05',
    priority: 'High',
    status: 'In Progress',
    case_id: 'case-marcus-obi',
    case_reference: 'Marcus Obi — Lagos → Amsterdam',
    category: 'immigration',
  },
  {
    task_name: 'File Blue Card EU application',
    assigned_owner: 'Thomas Keller',
    due_date: '2026-07-20',
    priority: 'Medium',
    status: 'To Do',
    case_id: 'case-priya-sharma',
    case_reference: 'Priya Sharma — Mumbai → Berlin',
    category: 'immigration',
  },
  {
    task_name: 'Follow up VETASSESS skills assessment outcome',
    assigned_owner: 'Siobhan Murphy',
    due_date: '2026-07-10',
    priority: 'High',
    status: 'In Progress',
    case_id: 'case-yuki-tanaka',
    case_reference: 'Yuki Tanaka — Tokyo → Sydney',
    category: 'immigration',
  },
  {
    task_name: 'Lodge LMIA-backed work permit application',
    assigned_owner: 'Amara Diallo',
    due_date: '2026-08-01',
    priority: 'Medium',
    status: 'To Do',
    case_id: 'case-james-okafor',
    case_reference: 'James Okafor — Nairobi → Toronto',
    category: 'immigration',
  },
  {
    task_name: 'Apply for UK Global Talent visa',
    assigned_owner: 'Thomas Keller',
    due_date: '2026-07-15',
    priority: 'High',
    status: 'To Do',
    case_id: 'case-sarah-chen',
    case_reference: 'Sarah Chen — Singapore → London',
    category: 'immigration',
  },
  // Compliance
  {
    task_name: 'Complete FIRS tax clearance certificate',
    assigned_owner: 'Deloitte Mobility',
    due_date: '2026-08-01',
    priority: 'Medium',
    status: 'To Do',
    case_id: 'case-marcus-obi',
    case_reference: 'Marcus Obi — Lagos → Amsterdam',
    category: 'compliance',
  },
  {
    task_name: 'Prepare 30% ruling eligibility dossier',
    assigned_owner: 'Fragomen',
    due_date: '2026-12-15',
    priority: 'Low',
    status: 'To Do',
    case_id: 'case-marcus-obi',
    case_reference: 'Marcus Obi — Lagos → Amsterdam',
    category: 'compliance',
  },
  {
    task_name: 'Submit GDPR data transfer impact assessment',
    assigned_owner: 'HR Compliance',
    due_date: '2026-07-08',
    priority: 'Medium',
    status: 'In Progress',
    case_id: 'case-elena-novak',
    case_reference: 'Elena Novak — Warsaw → Dublin',
    category: 'compliance',
  },
  {
    task_name: 'Escalate housing budget exception to CFO',
    assigned_owner: 'Siobhan Murphy',
    due_date: '2026-07-05',
    priority: 'High',
    status: 'In Progress',
    case_id: 'case-elena-novak',
    case_reference: 'Elena Novak — Warsaw → Dublin',
    category: 'compliance',
  },
  {
    task_name: 'Complete UK right-to-work documentation check',
    assigned_owner: 'Immigration counsel',
    due_date: '2026-07-22',
    priority: 'High',
    status: 'To Do',
    case_id: 'case-sarah-chen',
    case_reference: 'Sarah Chen — Singapore → London',
    category: 'compliance',
  },
  {
    task_name: 'Verify IND recognised sponsor status',
    assigned_owner: 'Fragomen',
    due_date: '2026-05-28',
    priority: 'Medium',
    status: 'Done',
    case_id: 'case-marcus-obi',
    case_reference: 'Marcus Obi — Lagos → Amsterdam',
    category: 'compliance',
  },
  // Logistics
  {
    task_name: 'Schedule household goods survey — Lagos',
    assigned_owner: 'Sirva',
    due_date: '2026-07-25',
    priority: 'Medium',
    status: 'To Do',
    case_id: 'case-marcus-obi',
    case_reference: 'Marcus Obi — Lagos → Amsterdam',
    category: 'logistics',
  },
  {
    task_name: 'Book temporary housing — Amsterdam Zuid',
    assigned_owner: 'Sirva',
    due_date: '2026-08-01',
    priority: 'Medium',
    status: 'To Do',
    case_id: 'case-marcus-obi',
    case_reference: 'Marcus Obi — Lagos → Amsterdam',
    category: 'logistics',
  },
  {
    task_name: 'Confirm International School of Amsterdam placement',
    assigned_owner: 'Relocate Global',
    due_date: '2026-08-05',
    priority: 'High',
    status: 'In Progress',
    case_id: 'case-marcus-obi',
    case_reference: 'Marcus Obi — Lagos → Amsterdam',
    category: 'logistics',
  },
  {
    task_name: 'Arrange HHG shipment — Mumbai to Berlin',
    assigned_owner: 'Cartus',
    due_date: '2026-08-15',
    priority: 'Medium',
    status: 'To Do',
    case_id: 'case-priya-sharma',
    case_reference: 'Priya Sharma — Mumbai → Berlin',
    category: 'logistics',
  },
  {
    task_name: 'Book corporate relocation flight — Nairobi to Toronto',
    assigned_owner: 'BCD Travel',
    due_date: '2026-09-28',
    priority: 'Low',
    status: 'To Do',
    case_id: 'case-james-okafor',
    case_reference: 'James Okafor — Nairobi → Toronto',
    category: 'logistics',
  },
  {
    task_name: 'Coordinate pet quarantine booking — Sydney',
    assigned_owner: 'Pet Express',
    due_date: '2026-08-20',
    priority: 'Medium',
    status: 'To Do',
    case_id: 'case-yuki-tanaka',
    case_reference: 'Yuki Tanaka — Tokyo → Sydney',
    category: 'logistics',
  },
  {
    task_name: 'Arrange London temporary accommodation — 30 days',
    assigned_owner: 'Crown Relocations',
    due_date: '2026-07-30',
    priority: 'Medium',
    status: 'In Progress',
    case_id: 'case-sarah-chen',
    case_reference: 'Sarah Chen — Singapore → London',
    category: 'logistics',
  },
  {
    task_name: 'Confirm Executive policy tier approval',
    assigned_owner: 'Thomas Keller',
    due_date: '2026-05-10',
    priority: 'Low',
    status: 'Done',
    case_id: 'case-sofia-lindstrom',
    case_reference: 'Sofia Lindström — Stockholm → Singapore',
    category: 'compliance',
  },
];

export function daysUntil(dateStr: string): number | null {
  try {
    const d = new Date(dateStr + 'T12:00:00');
    if (isNaN(d.getTime())) return null;
    return Math.ceil((d.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
  } catch {
    return null;
  }
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr + 'T12:00:00');
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

export function countTasksByStatus(tasks: RelocationTask[]) {
  return {
    todo: tasks.filter((t) => t.status === 'To Do').length,
    inProgress: tasks.filter((t) => t.status === 'In Progress').length,
    done: tasks.filter((t) => t.status === 'Done').length,
    total: tasks.length,
  };
}

export function uniqueCaseReferences(tasks: RelocationTask[]): string[] {
  return [...new Set(tasks.map((t) => t.case_reference))].sort();
}

/** Active relocation cases — aligned with Case Command & Move Roadmaps corridors */
export interface RelocationCaseRef {
  id: string;
  reference: string;
  employeeName: string;
  originCode: string;
  destinationCode: string;
  coordinator: string;
  status: 'Active' | 'At Risk' | 'Completed';
}

export const RELOCATION_CASES: RelocationCaseRef[] = [
  { id: 'case-marcus-obi', reference: 'Marcus Obi — Lagos → Amsterdam', employeeName: 'Marcus Obi', originCode: 'NG', destinationCode: 'NL', coordinator: 'Amara Diallo', status: 'At Risk' },
  { id: 'case-priya-sharma', reference: 'Priya Sharma — Mumbai → Berlin', employeeName: 'Priya Sharma', originCode: 'IN', destinationCode: 'DE', coordinator: 'Thomas Keller', status: 'Active' },
  { id: 'case-elena-novak', reference: 'Elena Novak — Warsaw → Dublin', employeeName: 'Elena Novak', originCode: 'PL', destinationCode: 'IE', coordinator: 'Siobhan Murphy', status: 'At Risk' },
  { id: 'case-james-okafor', reference: 'James Okafor — Nairobi → Toronto', employeeName: 'James Okafor', originCode: 'KE', destinationCode: 'CA', coordinator: 'Amara Diallo', status: 'Active' },
  { id: 'case-yuki-tanaka', reference: 'Yuki Tanaka — Tokyo → Sydney', employeeName: 'Yuki Tanaka', originCode: 'JP', destinationCode: 'AU', coordinator: 'Siobhan Murphy', status: 'At Risk' },
  { id: 'case-sarah-chen', reference: 'Sarah Chen — Singapore → London', employeeName: 'Sarah Chen', originCode: 'SG', destinationCode: 'GB', coordinator: 'Thomas Keller', status: 'Active' },
  { id: 'case-sofia-lindstrom', reference: 'Sofia Lindström — Stockholm → Singapore', employeeName: 'Sofia Lindström', originCode: 'SE', destinationCode: 'SG', coordinator: 'Thomas Keller', status: 'Completed' },
];

export function countByCategory(tasks: RelocationTask[]) {
  return {
    immigration: tasks.filter((t) => t.category === 'immigration').length,
    compliance: tasks.filter((t) => t.category === 'compliance').length,
    logistics: tasks.filter((t) => t.category === 'logistics').length,
  };
}

export function countOverdue(tasks: RelocationTask[]): number {
  return tasks.filter((t) => {
    if (t.status === 'Done') return false;
    const days = daysUntil(t.due_date);
    return days !== null && days < 0;
  }).length;
}

export function getUrgentTasks(tasks: RelocationTask[]): RelocationTask[] {
  return tasks
    .filter((t) => {
      if (t.status === 'Done') return false;
      const days = daysUntil(t.due_date);
      if (days !== null && days < 0) return true;
      if (t.priority === 'High' && days !== null && days <= 7) return true;
      return false;
    })
    .sort((a, b) => {
      const da = daysUntil(a.due_date) ?? 999;
      const db = daysUntil(b.due_date) ?? 999;
      return da - db;
    });
}

export function tasksForCase(tasks: RelocationTask[], caseRef: string): RelocationTask[] {
  return tasks.filter((t) => t.case_reference === caseRef);
}

export function caseTaskCounts(tasks: RelocationTask[]): Record<string, { total: number; open: number }> {
  const counts: Record<string, { total: number; open: number }> = {};
  for (const t of tasks) {
    if (!counts[t.case_reference]) counts[t.case_reference] = { total: 0, open: 0 };
    counts[t.case_reference].total++;
    if (t.status !== 'Done') counts[t.case_reference].open++;
  }
  return counts;
}
