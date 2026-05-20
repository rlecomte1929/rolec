import { useMemo, useState } from 'react';
import { DataTable, ResetColumnsLink, type DataTableColumn } from './DataTable';

/**
 * Standalone demo of <DataTable> — hardcoded mock data, no API.
 *
 * Mounted at `/dev/data-table-demo` (admin-only route) so you can:
 *   - Drag headers to reorder columns
 *   - Drag the right edge of each header to resize
 *   - Click a header to toggle sort
 *   - Reload the page → layout (order + widths + sort) is persisted
 *     in localStorage under `dataTable:demo.companies:v1`
 *   - Click "Reset column layout" → wipes and reloads
 *
 * This page is the proof we point at before migrating any real table.
 */

interface DemoRow {
  id: string;
  name: string;
  plan: 'low' | 'medium' | 'premium';
  status: 'active' | 'inactive' | 'archived';
  country: string;
  size_band: string;
  hr_users: number;
  hr_limit: number | null;
  employees: number;
  employee_limit: number | null;
  cases: number;
  contact: string;
  created: string;
}

const PLAN_PILL: Record<DemoRow['plan'], string> = {
  premium: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  medium: 'bg-amber-50 text-amber-700 ring-amber-200',
  low: 'bg-slate-100 text-slate-600 ring-slate-200',
};

const STATUS_PILL: Record<DemoRow['status'], string> = {
  active: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  inactive: 'bg-amber-50 text-amber-700 ring-amber-200',
  archived: 'bg-slate-100 text-slate-500 ring-slate-200',
};

const STATUS_DOT: Record<DemoRow['status'], string> = {
  active: 'bg-emerald-500',
  inactive: 'bg-amber-500',
  archived: 'bg-slate-400',
};

const MOCK_ROWS: DemoRow[] = [
  { id: 'a', name: 'Aurora Energy',     plan: 'premium', status: 'active',   country: 'France',         size_band: '201–500',  hr_users: 5, hr_limit: 8,   employees: 142, employee_limit: 500,  cases: 12, contact: 'Helena Müller',  created: '8 mo ago' },
  { id: 'b', name: 'Helix Bio',         plan: 'premium', status: 'active',   country: 'Germany',        size_band: '1001–5000',hr_users: 8, hr_limit: 12,  employees: 387, employee_limit: 1500, cases: 28, contact: 'Stefan Wolff',    created: '14 mo ago' },
  { id: 'c', name: 'Northpeak Capital', plan: 'medium',  status: 'active',   country: 'United Kingdom', size_band: '201–500',  hr_users: 4, hr_limit: 6,   employees: 78,  employee_limit: 300,  cases: 6,  contact: 'James Holt',      created: '6 mo ago' },
  { id: 'd', name: 'Meridian Logistics',plan: 'medium',  status: 'active',   country: 'Netherlands',    size_band: '201–500',  hr_users: 3, hr_limit: 5,   employees: 95,  employee_limit: 250,  cases: 9,  contact: 'Olivia Janssen',  created: '4 mo ago' },
  { id: 'e', name: 'Cobalt Robotics',   plan: 'premium', status: 'active',   country: 'United States',  size_band: '51–200',   hr_users: 2, hr_limit: 4,   employees: 47,  employee_limit: 100,  cases: 4,  contact: 'Sarah Kim',       created: '3 mo ago' },
  { id: 'f', name: 'Verdant AgriTech',  plan: 'low',     status: 'active',   country: 'Italy',          size_band: '51–200',   hr_users: 1, hr_limit: 3,   employees: 12,  employee_limit: 50,   cases: 1,  contact: 'Elena Morelli',   created: '9 mo ago' },
  { id: 'g', name: 'Nimbus Cloud',      plan: 'medium',  status: 'inactive', country: 'Ireland',        size_band: '201–500',  hr_users: 0, hr_limit: 5,   employees: 0,   employee_limit: 300,  cases: 0,  contact: 'Aoife Brennan',   created: '7 mo ago' },
  { id: 'h', name: 'Sable Maritime',    plan: 'low',     status: 'archived', country: 'Norway',         size_band: '201–500',  hr_users: 0, hr_limit: 3,   employees: 0,   employee_limit: 100,  cases: 0,  contact: 'Magnus Berg',     created: '2 yr ago' },
  { id: 'i', name: 'Aether Pharma',     plan: 'premium', status: 'active',   country: 'Switzerland',    size_band: '1001–5000',hr_users: 6, hr_limit: 10,  employees: 246, employee_limit: 800,  cases: 18, contact: 'Anya Petrov',     created: '11 mo ago' },
  { id: 'j', name: 'Lattice Networks',  plan: 'medium',  status: 'active',   country: 'Singapore',      size_band: '201–500',  hr_users: 3, hr_limit: 5,   employees: 64,  employee_limit: 300,  cases: 7,  contact: 'Saanvi Mehra',    created: '5 mo ago' },
];

function Pill({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${className}`}>
      {children}
    </span>
  );
}

function SeatCell({ count, limit }: { count: number; limit: number | null }) {
  if (limit == null) {
    return <div className="text-[12.5px] tabular-nums text-slate-700">{count} <span className="text-slate-400">/ —</span></div>;
  }
  const pct = limit > 0 ? Math.min(100, Math.round((count / limit) * 100)) : 0;
  const barColor = pct > 90 ? 'bg-rose-500' : pct > 75 ? 'bg-amber-500' : 'bg-emerald-500';
  return (
    <div className="min-w-[6rem] space-y-1">
      <div className="text-[12.5px] tabular-nums text-slate-700">{count} <span className="text-slate-400">/ {limit}</span></div>
      <div className="h-1 w-full overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full ${barColor} transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function DataTableDemo() {
  const [clickedRow, setClickedRow] = useState<string | null>(null);

  const columns = useMemo<DataTableColumn<DemoRow>[]>(() => [
    {
      id: 'name',
      header: 'Company',
      cell: (r) => <span className="font-medium text-slate-900">{r.name}</span>,
      defaultWidth: 220,
      minWidth: 140,
    },
    {
      id: 'plan',
      header: 'Plan',
      cell: (r) => <Pill className={PLAN_PILL[r.plan]}>{r.plan}</Pill>,
      defaultWidth: 100,
      minWidth: 80,
    },
    {
      id: 'status',
      header: 'Status',
      cell: (r) => (
        <Pill className={STATUS_PILL[r.status]}>
          <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[r.status]}`} />
          {r.status}
        </Pill>
      ),
      defaultWidth: 120,
      minWidth: 90,
    },
    { id: 'country', header: 'Country', cell: (r) => <span className="text-slate-700">{r.country}</span>, defaultWidth: 160 },
    { id: 'size_band', header: 'Size', cell: (r) => <span className="text-slate-700">{r.size_band}</span>, defaultWidth: 110 },
    {
      id: 'hr_seats',
      header: 'HR seats',
      cell: (r) => <SeatCell count={r.hr_users} limit={r.hr_limit} />,
      defaultWidth: 130,
      minWidth: 110,
    },
    {
      id: 'employee_seats',
      header: 'Employee seats',
      cell: (r) => <SeatCell count={r.employees} limit={r.employee_limit} />,
      defaultWidth: 150,
      minWidth: 120,
    },
    {
      id: 'cases',
      header: 'Cases',
      cell: (r) => <span className="font-semibold tabular-nums text-slate-700">{r.cases}</span>,
      defaultWidth: 80,
      minWidth: 60,
      cellClassName: 'text-right',
    },
    { id: 'contact', header: 'Contact', cell: (r) => <span className="text-slate-700">{r.contact}</span>, defaultWidth: 160 },
    { id: 'created', header: 'Created', cell: (r) => <span className="text-xs text-slate-500">{r.created}</span>, defaultWidth: 110 },
  ], []);

  return (
    <div className="px-6 py-8">
      <div className="mb-6">
        <div className="text-[11px] font-medium uppercase tracking-widest text-slate-400">
          ReloPass · /dev/data-table-demo
        </div>
        <div className="mt-1.5 flex items-baseline gap-3">
          <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">DataTable primitive — demo</h1>
          <Pill className="bg-amber-50 text-amber-700 ring-amber-200">dev only · mock data</Pill>
        </div>
        <p className="mt-1 max-w-3xl text-[13px] text-slate-500">
          Standalone demo for the <code>&lt;DataTable&gt;</code> primitive. Drag any header to reorder columns,
          drag the right edge of a header to resize, click a header to sort. Reload the page — your layout
          persists per <code>tableId</code> in localStorage. No real data is touched on this page.
        </p>
      </div>

      <div className="mb-3 flex items-center gap-2 text-[12.5px] text-slate-500">
        <span>Last clicked row:</span>
        <span className="font-medium text-slate-700">{clickedRow ?? '—'}</span>
      </div>

      <DataTable
        tableId="demo.companies"
        columns={columns}
        rows={MOCK_ROWS}
        rowKey={(r) => r.id}
        onRowClick={(r) => setClickedRow(r.name)}
        isRowActive={(r) => r.name === clickedRow}
        ariaLabel="Demo companies table"
        footerSlot={
          <div className="flex items-center justify-between px-4 py-2 text-[11.5px] text-slate-500">
            <span>{MOCK_ROWS.length} rows · mock data</span>
            <ResetColumnsLink tableId="demo.companies" />
          </div>
        }
      />

      <div className="mt-6 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-[12.5px] text-slate-600">
        <strong className="text-slate-800">Try this:</strong>
        <ol className="ml-5 mt-1 list-decimal space-y-0.5">
          <li>Drag the <em>Plan</em> header to swap it with <em>Status</em></li>
          <li>Resize <em>Company</em> wider by dragging its right edge</li>
          <li>Click <em>Cases</em> twice to sort descending</li>
          <li>Reload the page — your layout sticks</li>
          <li>Click <em>Reset column layout</em> in the footer → defaults restored</li>
        </ol>
      </div>
    </div>
  );
}

export default DataTableDemo;
