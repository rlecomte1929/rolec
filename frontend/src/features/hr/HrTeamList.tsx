import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Checkbox } from '../../components/antigravity/Checkbox';
import { Input } from '../../components/antigravity/Input';
import { Button } from '../../components/antigravity';
import { hrAPI } from '../../api/client';
import type { HrCompanyEmployee } from '../../types';
import { buildRoute } from '../../navigation/routes';
import {
  POLICY_EMPLOYEE_LEVEL_OPTIONS,
  normalizeEmployeeLevel,
} from '../policy-config/policyTargeting';

// ─── constants ───────────────────────────────────────────────────────────────

const ASSIGNMENT_TYPE_OPTIONS = [
  { value: 'Long-Term', label: 'Long-term' },
  { value: 'Short-Term', label: 'Short-term' },
  { value: 'Permanent', label: 'Permanent' },
  { value: 'international', label: 'International' },
];

const STATUS_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'on_assignment', label: 'On assignment' },
  { value: 'inactive', label: 'Inactive' },
];

const AVATAR_PALETTE = [
  { bg: '#E1F5EE', color: '#0F6E56' },
  { bg: '#E6F1FB', color: '#185FA5' },
  { bg: '#FAEEDA', color: '#854F0B' },
  { bg: '#EEEDFE', color: '#3C3489' },
  { bg: '#FAECE7', color: '#993C1D' },
  { bg: '#FBEAF0', color: '#72243E' },
];

// Default column widths in px
const DEFAULT_COL_WIDTHS = [40, 260, 180, 150, 120, 130, 80];
const COL_MIN = 60;
const PAGE_SIZE = 12;

// ─── helpers ─────────────────────────────────────────────────────────────────

function initials(name: string): string {
  return name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

function avatarColor(idx: number) {
  // idx is a non-negative row index and AVATAR_PALETTE is non-empty, so the modulo index is always in bounds
  return AVATAR_PALETTE[idx % AVATAR_PALETTE.length]!;
}

/** Display name: full_name → email → null (show placeholder) */
function displayName(emp: HrCompanyEmployee): string | null {
  return emp.full_name || emp.email || null;
}


// ─── column resize hook ───────────────────────────────────────────────────────

function useColumnResize(initial: number[]) {
  const [widths, setWidths] = useState<number[]>(initial);
  const dragging = useRef<{ colIdx: number; startX: number; startW: number } | null>(null);

  const onMouseDown = useCallback(
    (colIdx: number) => (e: React.MouseEvent) => {
      e.preventDefault();
      dragging.current = { colIdx, startX: e.clientX, startW: widths[colIdx] ?? COL_MIN };

      const onMove = (mv: MouseEvent) => {
        if (!dragging.current) return;
        const delta = mv.clientX - dragging.current.startX;
        const newW = Math.max(COL_MIN, dragging.current.startW + delta);
        setWidths((prev) => {
          const next = [...prev];
          next[dragging.current!.colIdx] = newW;
          return next;
        });
      };

      const onUp = () => {
        dragging.current = null;
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup', onUp);
      };

      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);
    },
    [widths]
  );

  return { widths, onMouseDown };
}

// ─── inline edit cell ────────────────────────────────────────────────────────

interface InlineSelectProps {
  value: string;
  options: { value: string; label: string }[];
  onSave: (val: string) => Promise<void>;
  placeholder?: string;
}

const InlineSelect: React.FC<InlineSelectProps> = ({ value, options, onSave, placeholder }) => {
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const selectRef = useRef<HTMLSelectElement>(null);
  const label = options.find((o) => o.value.toLowerCase() === value?.toLowerCase())?.label ?? value;

  useEffect(() => {
    if (editing) selectRef.current?.focus();
  }, [editing]);

  if (!editing) {
    return (
      <span
        className="group flex items-center gap-1 cursor-pointer"
        role="button"
        tabIndex={0}
        onClick={() => setEditing(true)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setEditing(true); } }}
      >
        <span className={value ? 'text-[#374151]' : 'text-gray-500'}>
          {value ? label : (placeholder ?? '—')}
        </span>
        <svg className="opacity-0 group-hover:opacity-100 text-gray-500 flex-shrink-0" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
      </span>
    );
  }

  return (
    <select
      ref={selectRef}
      className="text-xs border border-[#1D9E75] rounded px-1 py-0.5 bg-white text-[#0b2b43] outline-none"
      defaultValue={value || ''}
      disabled={saving}
      onClick={(e) => e.stopPropagation()}
      onChange={async (e) => {
        setSaving(true);
        try { await onSave(e.target.value); } finally { setSaving(false); setEditing(false); }
      }}
      onBlur={() => setEditing(false)}
    >
      <option value="">— clear —</option>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
};

// ─── expand row ───────────────────────────────────────────────────────────────

const ExpandRow: React.FC<{ emp: HrCompanyEmployee; colSpan: number }> = ({ emp, colSpan }) => (
  <tr className="bg-[#fafafa] border-b border-[#e5e7eb]">
    <td />
    <td colSpan={colSpan - 1} className="px-4 py-4">
      <div className="grid grid-cols-4 gap-x-8 gap-y-3 text-sm">
        <div>
          <p className="text-xs text-gray-500 mb-1">Employee ID</p>
          <p className="font-mono text-xs text-[#6b7280] truncate">{emp.profile_id}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Email</p>
          <p className="text-[#374151] truncate">{emp.email || '—'}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Member since</p>
          <p className="text-[#374151]">
            {new Date(emp.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
          </p>
        </div>
        <div>
          {emp.relocation_case_id ? (
            <>
              <p className="text-xs text-gray-500 mb-1">Active case</p>
              <Link
                to={buildRoute('hrCaseSummary', { caseId: emp.relocation_case_id })}
                className="text-xs text-[#185FA5] hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                Open case →
              </Link>
            </>
          ) : (
            <>
              <p className="text-xs text-gray-500 mb-1">Relocation case</p>
              <p className="text-xs text-gray-500">No active case</p>
            </>
          )}
        </div>
      </div>
    </td>
  </tr>
);

// ─── confirm delete modal ──────────────────────────────────────────────────────

const ConfirmModal: React.FC<{
  count: number;
  onConfirm: () => void;
  onCancel: () => void;
}> = ({ count, onConfirm, onCancel }) => (
  <div
    className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
    onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
    onKeyDown={(e) => { if (e.key === 'Escape') onCancel(); }}
    role="button"
    tabIndex={-1}
    aria-label="Close dialog"
  >
    <div
      className="bg-white rounded-xl border border-[#e5e7eb] p-6 w-80 shadow-sm"
    >
      <p className="font-medium text-[#0b2b43] mb-2">Remove {count === 1 ? 'employee' : `${count} employees`}?</p>
      <p className="text-sm text-[#6b7280] mb-5">
        This removes {count === 1 ? 'them' : 'them'} from your company roster. It does not delete their ReloPass account or active cases.
      </p>
      <div className="flex gap-2 justify-end">
        <Button variant="outline" size="sm" onClick={onCancel}>Cancel</Button>
        <Button unstyled
          className="px-3 py-1.5 text-sm rounded-lg bg-[#E24B4A] text-white font-medium hover:bg-[#A32D2D] transition-colors"
          onClick={onConfirm}
        >
          Remove
        </Button>
      </div>
    </div>
  </div>
);

// ─── main component ───────────────────────────────────────────────────────────

interface HrTeamListProps {
  employees: HrCompanyEmployee[];
  isLoading?: boolean;
  onReload: () => void;
}

export const HrTeamList: React.FC<HrTeamListProps> = ({ employees, isLoading, onReload }) => {
  const navigate = useNavigate();

  // ── filters ───────────────────────────────────────────────────────────────
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterBand, setFilterBand] = useState('');
  const [filterAssignment, setFilterAssignment] = useState('');
  const [filterHasCase, setFilterHasCase] = useState('');

  // ── table state ───────────────────────────────────────────────────────────
  const [expanded, setExpanded] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(1);
  const [rosterError, setRosterError] = useState('');

  // ── delete state ──────────────────────────────────────────────────────────
  const [pendingDelete, setPendingDelete] = useState<string[] | null>(null);
  const [deleting, setDeleting] = useState(false);

  // ── column resize ─────────────────────────────────────────────────────────
  const { widths, onMouseDown } = useColumnResize(DEFAULT_COL_WIDTHS);

  // ── metrics ───────────────────────────────────────────────────────────────
  const activeCount = employees.filter((e) => (e.status || '').toLowerCase() === 'active').length;
  const onAssignmentCount = employees.filter((e) => (e.status || '').toLowerCase() === 'on_assignment').length;
  const withCaseCount = employees.filter((e) => !!e.relocation_case_id).length;
  const missingProfileCount = employees.filter((e) => !e.full_name && !e.email).length;

  // ── filter ────────────────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return employees.filter((e) => {
      if (q) {
        const name = displayName(e)?.toLowerCase() ?? '';
        const email = (e.email || '').toLowerCase();
        const band = (e.band || '').toLowerCase();
        const at = (e.assignment_type || '').toLowerCase();
        if (!name.includes(q) && !email.includes(q) && !band.includes(q) && !at.includes(q)) return false;
      }
      if (filterStatus && (e.status || '').toLowerCase() !== filterStatus.toLowerCase()) return false;
      if (filterBand && normalizeEmployeeLevel(e.band || '') !== filterBand) return false;
      if (filterAssignment && (e.assignment_type || '').toLowerCase() !== filterAssignment.toLowerCase()) return false;
      if (filterHasCase === 'yes' && !e.relocation_case_id) return false;
      if (filterHasCase === 'no' && !!e.relocation_case_id) return false;
      return true;
    });
  }, [employees, search, filterStatus, filterBand, filterAssignment, filterHasCase]);

  const activeFilters = [filterStatus, filterBand, filterAssignment, filterHasCase].filter(Boolean).length;

  // ── pagination ────────────────────────────────────────────────────────────
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const pageRows = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  // ── selection ─────────────────────────────────────────────────────────────
  const allPageSelected = pageRows.length > 0 && pageRows.every((e) => selected.has(e.id));

  function toggleAll() {
    setSelected((prev) => {
      const next = new Set(prev);
      if (allPageSelected) { pageRows.forEach((e) => next.delete(e.id)); }
      else { pageRows.forEach((e) => next.add(e.id)); }
      return next;
    });
  }

  function toggleRow(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  // ── inline update ─────────────────────────────────────────────────────────
  const handleUpdate = useCallback(
    (empId: string, field: 'band' | 'assignment_type' | 'status') =>
      async (value: string) => {
        setRosterError('');
        try {
          await hrAPI.updateEmployee(empId, { [field]: value || undefined });
          onReload();
        } catch (err) {
          const e = err as { response?: { data?: { detail?: string } } };
          const detail = e.response?.data?.detail;
          setRosterError(typeof detail === 'string' ? detail : 'Could not update this employee.');
        }
      },
    [onReload]
  );

  // ── delete ────────────────────────────────────────────────────────────────
  async function confirmDelete() {
    if (!pendingDelete) return;
    setDeleting(true);
    setRosterError('');
    try {
      await Promise.all(pendingDelete.map((id) => hrAPI.deleteEmployee(id)));
      setSelected((prev) => {
        const next = new Set(prev);
        pendingDelete.forEach((id) => next.delete(id));
        return next;
      });
      onReload();
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      const detail = e.response?.data?.detail;
      setRosterError(typeof detail === 'string' ? detail : 'Could not remove this employee.');
    } finally {
      setDeleting(false);
      setPendingDelete(null);
    }
  }

  function clearFilters() {
    setFilterStatus(''); setFilterBand(''); setFilterAssignment(''); setFilterHasCase('');
  }

  if (isLoading) {
    return <div className="text-sm text-gray-500 p-4">Loading team…</div>;
  }

  const COLS = ['', 'Employee', 'Assignment', 'Level', 'Status', 'Case', ''];

  return (
    <>
      {rosterError && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
          {rosterError}
        </div>
      )}
      {pendingDelete && (
        <ConfirmModal
          count={pendingDelete.length}
          onConfirm={confirmDelete}
          onCancel={() => !deleting && setPendingDelete(null)}
        />
      )}

      {/* metric strip */}
      <div className="grid grid-cols-4 gap-3 mb-5">
        {[
          { label: 'Total employees', value: employees.length, sub: null },
          { label: 'Active', value: activeCount, sub: `${Math.round((activeCount / Math.max(employees.length, 1)) * 100)}% of team` },
          { label: 'On assignment', value: onAssignmentCount, sub: withCaseCount > 0 ? `${withCaseCount} active case${withCaseCount !== 1 ? 's' : ''}` : null },
          { label: 'Profile pending', value: missingProfileCount, sub: missingProfileCount > 0 ? 'Missing name & email' : 'All profiles complete' },
        ].map((m) => (
          <div key={m.label} className="bg-[#f9fafb] border border-[#e5e7eb] rounded-xl px-4 py-3">
            <p className="text-xs text-[#6b7280] mb-1">{m.label}</p>
            <p className="text-2xl font-medium text-[#0b2b43]">{m.value}</p>
            {m.sub && <p className="text-xs text-gray-500 mt-1">{m.sub}</p>}
          </div>
        ))}
      </div>

      {/* toolbar */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        {/* search */}
        <div className="relative flex-1 min-w-[180px]">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <Input unstyled
            type="text"
            value={search}
            onChange={(v) => { setSearch(v); setPage(1); }}
            placeholder="Search by name, email, level…"
            className="w-full pl-8 pr-3 py-2 text-sm border border-[#e5e7eb] rounded-lg bg-white placeholder:text-gray-500 text-[#0b2b43] focus:outline-none focus:border-[#1D9E75] focus:ring-1 focus:ring-[#1D9E75]"
          />
        </div>

        {/* filter dropdowns */}
        {([
          {
            value: filterStatus, setter: setFilterStatus,
            placeholder: 'Status', options: STATUS_OPTIONS,
          },
          {
            value: filterBand, setter: setFilterBand,
            placeholder: 'Level', options: POLICY_EMPLOYEE_LEVEL_OPTIONS.map((o) => ({ value: o.value, label: o.label })),
          },
          {
            value: filterAssignment, setter: setFilterAssignment,
            placeholder: 'Assignment', options: ASSIGNMENT_TYPE_OPTIONS,
          },
          {
            value: filterHasCase, setter: setFilterHasCase,
            placeholder: 'Case', options: [{ value: 'yes', label: 'Has case' }, { value: 'no', label: 'No case' }],
          },
        ] as { value: string; setter: (v: string) => void; placeholder: string; options: { value: string; label: string }[] }[]).map((f) => (
          <select
            key={f.placeholder}
            value={f.value}
            onChange={(e) => { f.setter(e.target.value); setPage(1); }}
            className={`text-sm border rounded-lg px-2.5 py-2 bg-white focus:outline-none focus:border-[#1D9E75] focus:ring-1 focus:ring-[#1D9E75] ${f.value ? 'border-[#1D9E75] text-[#0F6E56] font-medium' : 'border-[#e5e7eb] text-[#6b7280]'}`}
          >
            <option value="">{f.placeholder}</option>
            {f.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        ))}

        {activeFilters > 0 && (
          <Button unstyled onClick={clearFilters} className="text-xs text-gray-500 hover:text-[#374151] underline-offset-2 hover:underline transition-colors">
            Clear {activeFilters} filter{activeFilters > 1 ? 's' : ''}
          </Button>
        )}

        <div className="ml-auto flex items-center gap-2">
          {selected.size > 0 && (
            <Button unstyled
              onClick={() => setPendingDelete(Array.from(selected))}
              className="flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg border border-[#F09595] text-[#A32D2D] hover:bg-[#FCEBEB] transition-colors"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>
              Remove {selected.size}
            </Button>
          )}
          <Button unstyled
            onClick={() => navigate(buildRoute('hrCommandCenter'))}
            className="flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg bg-[#1D9E75] text-white font-medium hover:bg-[#0F6E56] transition-colors"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            Assign employee
          </Button>
        </div>
      </div>

      {/* results count */}
      {(search || activeFilters > 0) && (
        <p className="text-xs text-gray-500 mb-2">
          {filtered.length} result{filtered.length !== 1 ? 's' : ''} · {employees.length} total
        </p>
      )}

      {/* table */}
      <div className="border border-[#e5e7eb] rounded-xl overflow-hidden select-none">
        <div style={{ overflowX: 'auto' }}>
          <table style={{ tableLayout: 'fixed', width: widths.reduce((a, b) => a + b, 0), minWidth: '100%', borderCollapse: 'collapse' }}>
            <colgroup>
              {widths.map((w, i) => <col key={i} style={{ width: w }} />)}
            </colgroup>
            <thead>
              <tr className="bg-[#f3f4f6] border-b border-[#e5e7eb]">
                {COLS.map((col, i) => (
                  <th
                    key={i}
                    className="relative px-3 py-2.5 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wide"
                    style={{ userSelect: 'none' }}
                  >
                    {i === 0 ? (
                      <Checkbox
                        checked={allPageSelected}
                        onChange={toggleAll}
                        className="w-3.5 h-3.5 accent-[#1D9E75] cursor-pointer"
                      />
                    ) : col}
                    {/* resize handle — not on last col */}
                    {i < COLS.length - 1 && (
                      <div
                        onMouseDown={onMouseDown(i)}
                        role="button"
                        tabIndex={-1}
                        aria-label="Resize column"
                        className="absolute right-0 top-0 h-full w-3 cursor-col-resize flex items-center justify-center group"
                        style={{ zIndex: 1 }}
                      >
                        <div className="w-px h-3/5 bg-[#d1d5db] group-hover:bg-[#1D9E75] transition-colors" />
                      </div>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pageRows.length === 0 ? (
                <tr>
                  <td colSpan={COLS.length} className="px-4 py-10 text-center text-sm text-gray-500">
                    {search || activeFilters > 0 ? 'No employees match your filters.' : 'No employees yet.'}
                  </td>
                </tr>
              ) : (
                pageRows.map((emp, idx) => {
                  const isExpanded = expanded === emp.id;
                  const isSelected = selected.has(emp.id);
                  const name = displayName(emp);
                  const hasProfile = !!name;
                  const av = avatarColor(idx);

                  return (
                    <React.Fragment key={emp.id}>
                      <tr
                        className={`border-b border-[#e5e7eb] cursor-pointer transition-colors ${isSelected ? 'bg-[#E1F5EE]' : 'hover:bg-[#f9fafb]'}`}
                        onClick={(e) => {
                          if ((e.target as HTMLElement).closest('button,a,input,select,label,[role="button"]')) return;
                          setExpanded((p) => (p === emp.id ? null : emp.id));
                        }}
                        role="button"
                        tabIndex={0}
                        aria-expanded={isExpanded}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            setExpanded((p) => (p === emp.id ? null : emp.id));
                          }
                        }}
                      >
                        {/* checkbox */}
                        <td className="px-3 py-2.5">
                          <Checkbox
                            checked={isSelected}
                            onChange={() => toggleRow(emp.id)}
                            className="w-3.5 h-3.5 accent-[#1D9E75] cursor-pointer"
                          />
                        </td>

                        {/* name */}
                        <td className="px-3 py-2.5">
                          <div className="flex items-center gap-2 min-w-0">
                            <svg className={`flex-shrink-0 text-gray-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`} width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>
                            <div
                              className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-medium"
                              style={hasProfile ? { background: av.bg, color: av.color } : { background: '#f3f4f6', color: '#9ca3af' }}
                            >
                              {hasProfile ? initials(name) : '?'}
                            </div>
                            <div className="min-w-0">
                              {hasProfile ? (
                                <>
                                  <p className="text-sm font-medium text-[#0b2b43] truncate">{name}</p>
                                  {emp.email && emp.full_name && (
                                    <p className="text-xs text-gray-500 truncate">{emp.email}</p>
                                  )}
                                </>
                              ) : (
                                <>
                                  <p className="text-xs font-mono text-gray-500 truncate">{emp.profile_id.slice(0, 20)}…</p>
                                  <span className="inline-block mt-0.5 px-1.5 py-0.5 text-[10px] rounded bg-[#FAEEDA] text-[#854F0B]">Profile pending</span>
                                </>
                              )}
                            </div>
                          </div>
                        </td>

                        {/* assignment type — inline editable */}
                        <td className="px-3 py-2.5 text-sm">
                          <InlineSelect
                            value={emp.assignment_type || ''}
                            options={ASSIGNMENT_TYPE_OPTIONS}
                            onSave={handleUpdate(emp.id, 'assignment_type')}
                            placeholder="—"
                          />
                        </td>

                        {/* band — inline editable */}
                        <td className="px-3 py-2.5 text-sm">
                          <InlineSelect
                            value={normalizeEmployeeLevel(emp.band || '') ?? ''}
                            options={POLICY_EMPLOYEE_LEVEL_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
                            onSave={handleUpdate(emp.id, 'band')}
                            placeholder="—"
                          />
                        </td>

                        {/* status — inline editable */}
                        <td className="px-3 py-2.5 text-sm">
                          <InlineSelect
                            value={emp.status || ''}
                            options={STATUS_OPTIONS}
                            onSave={handleUpdate(emp.id, 'status')}
                            placeholder="Unknown"
                          />
                        </td>

                        {/* case indicator */}
                        <td className="px-3 py-2.5">
                          {emp.relocation_case_id ? (
                            <Link
                              to={buildRoute('hrCaseSummary', { caseId: emp.relocation_case_id })}
                              className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-[#E6F1FB] text-[#185FA5] hover:bg-[#B5D4F4] transition-colors font-medium"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                              Active
                            </Link>
                          ) : (
                            <span className="text-xs text-gray-500">—</span>
                          )}
                        </td>

                        {/* actions */}
                        <td className="px-3 py-2.5">
                          <div className="flex items-center gap-1 justify-end">
                            <Link
                              to={buildRoute('hrEmployeeDetail', { id: emp.id })}
                              className="p-1 rounded text-gray-500 hover:text-[#185FA5] hover:bg-[#E6F1FB] transition-colors"
                              title="Edit employee"
                            >
                              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                            </Link>
                            <Button unstyled
                              onClick={() => setPendingDelete([emp.id])}
                              className="p-1 rounded text-gray-500 hover:text-[#A32D2D] hover:bg-[#FCEBEB] transition-colors"
                              title="Remove employee"
                            >
                              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>
                            </Button>
                          </div>
                        </td>
                      </tr>

                      {isExpanded && <ExpandRow emp={emp} colSpan={COLS.length} />}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* pagination footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-[#e5e7eb] bg-white">
          <span className="text-xs text-gray-500">
            {filtered.length === 0
              ? '0 employees'
              : `${(safePage - 1) * PAGE_SIZE + 1}–${Math.min(safePage * PAGE_SIZE, filtered.length)} of ${filtered.length}`}
            {selected.size > 0 && (
              <span className="ml-2 text-[#0F6E56] font-medium">· {selected.size} selected</span>
            )}
          </span>
          {pageCount > 1 && (
            <div className="flex gap-1">
              <Button unstyled onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={safePage === 1} className="w-7 h-7 rounded-md border border-[#e5e7eb] text-[#374151] hover:bg-[#f3f4f6] disabled:opacity-40 text-xs">←</Button>
              {Array.from({ length: Math.min(pageCount, 7) }, (_, i) => i + 1).map((p) => (
                <Button unstyled
                  key={p}
                  onClick={() => setPage(p)}
                  className={`w-7 h-7 rounded-md text-xs border transition-colors ${p === safePage ? 'bg-[#1D9E75] border-[#1D9E75] text-white font-medium' : 'border-[#e5e7eb] text-[#374151] hover:bg-[#f3f4f6]'}`}
                >
                  {p}
                </Button>
              ))}
              <Button unstyled onClick={() => setPage((p) => Math.min(pageCount, p + 1))} disabled={safePage === pageCount} className="w-7 h-7 rounded-md border border-[#e5e7eb] text-[#374151] hover:bg-[#f3f4f6] disabled:opacity-40 text-xs">→</Button>
            </div>
          )}
        </div>
      </div>
    </>
  );
};
