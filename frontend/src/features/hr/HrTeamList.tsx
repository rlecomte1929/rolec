import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge, Button } from '../../components/antigravity';
import type { HrCompanyEmployee } from '../../types';
import { buildRoute } from '../../navigation/routes';

// ─── helpers ────────────────────────────────────────────────────────────────

function initials(name?: string): string {
  if (!name) return '?';
  return name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

const AVATAR_PALETTE = [
  { bg: '#E1F5EE', color: '#0F6E56' },
  { bg: '#E6F1FB', color: '#185FA5' },
  { bg: '#FAEEDA', color: '#854F0B' },
  { bg: '#EEEDFE', color: '#3C3489' },
  { bg: '#FAECE7', color: '#993C1D' },
  { bg: '#FBEAF0', color: '#72243E' },
];

function avatarColor(index: number) {
  return AVATAR_PALETTE[index % AVATAR_PALETTE.length];
}

function statusVariant(status?: string): 'success' | 'warning' | 'neutral' | 'error' {
  switch ((status || '').toLowerCase()) {
    case 'active':
      return 'success';
    case 'pending':
    case 'in_progress':
      return 'warning';
    case 'completed':
      return 'neutral';
    case 'cancelled':
      return 'error';
    default:
      return 'neutral';
  }
}

function statusLabel(status?: string): string {
  if (!status) return 'Unknown';
  return status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

const PAGE_SIZE = 10;

// ─── metric cards ────────────────────────────────────────────────────────────

interface MetricCardProps {
  label: string;
  value: number;
  sub?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ label, value, sub }) => (
  <div className="bg-[#f9fafb] rounded-xl px-4 py-3 border border-[#e5e7eb]">
    <div className="text-xs text-[#6b7280] mb-1">{label}</div>
    <div className="text-2xl font-medium text-[#0b2b43]">{value}</div>
    {sub && <div className="text-xs text-[#9ca3af] mt-1">{sub}</div>}
  </div>
);

// ─── expand row ──────────────────────────────────────────────────────────────

interface ExpandRowProps {
  emp: HrCompanyEmployee;
}

const ExpandRow: React.FC<ExpandRowProps> = ({ emp }) => (
  <tr className="bg-[#f9fafb] border-b border-[#e5e7eb]">
    <td />
    <td colSpan={6} className="px-4 py-4">
      <div className="grid grid-cols-4 gap-4 text-sm">
        <div>
          <div className="text-xs text-[#9ca3af] mb-1">Employee ID</div>
          <div className="font-mono text-xs text-[#374151] truncate">{emp.profile_id}</div>
        </div>
        <div>
          <div className="text-xs text-[#9ca3af] mb-1">Band / level</div>
          <div className="text-[#374151]">{emp.band || '—'}</div>
        </div>
        <div>
          <div className="text-xs text-[#9ca3af] mb-1">Assignment type</div>
          <div className="text-[#374151]">{emp.assignment_type || '—'}</div>
        </div>
        <div>
          <div className="text-xs text-[#9ca3af] mb-1">Member since</div>
          <div className="text-[#374151]">
            {new Date(emp.created_at).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}
          </div>
          {emp.relocation_case_id && (
            <>
              <div className="text-xs text-[#9ca3af] mb-1 mt-3">Active case</div>
              <Link
                to={buildRoute('hrCaseSummary', { caseId: emp.relocation_case_id })}
                className="text-xs text-[#185FA5] hover:underline truncate block"
                onClick={(e) => e.stopPropagation()}
              >
                View case →
              </Link>
            </>
          )}
        </div>
      </div>
    </td>
  </tr>
);

// ─── main component ──────────────────────────────────────────────────────────

interface HrTeamListProps {
  employees: HrCompanyEmployee[];
  isLoading?: boolean;
}

export const HrTeamList: React.FC<HrTeamListProps> = ({ employees, isLoading }) => {
  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(1);

  // ── metrics ───────────────────────────────────────────────────────────────
  const activeCount = employees.filter(
    (e) => (e.status || '').toLowerCase() === 'active'
  ).length;
  const withCaseCount = employees.filter((e) => !!e.relocation_case_id).length;
  const internationalCount = employees.filter(
    (e) => (e.assignment_type || '').toLowerCase().includes('international')
  ).length;

  // ── filter ────────────────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    if (!q) return employees;
    return employees.filter(
      (e) =>
        (e.full_name || '').toLowerCase().includes(q) ||
        (e.email || '').toLowerCase().includes(q) ||
        (e.band || '').toLowerCase().includes(q) ||
        (e.assignment_type || '').toLowerCase().includes(q) ||
        (e.role || '').toLowerCase().includes(q)
    );
  }, [employees, search]);

  // ── pagination ────────────────────────────────────────────────────────────
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const pageRows = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  // ── selection ─────────────────────────────────────────────────────────────
  const allPageSelected =
    pageRows.length > 0 && pageRows.every((e) => selected.has(e.id));

  function toggleAll() {
    setSelected((prev) => {
      const next = new Set(prev);
      if (allPageSelected) {
        pageRows.forEach((e) => next.delete(e.id));
      } else {
        pageRows.forEach((e) => next.add(e.id));
      }
      return next;
    });
  }

  function toggleRow(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (isLoading) {
    return (
      <div className="border border-[#e5e7eb] rounded-xl p-6 text-sm text-[#9ca3af]">
        Loading employees…
      </div>
    );
  }

  return (
    <div>
      {/* metric cards */}
      <div className="grid grid-cols-4 gap-3 mb-5">
        <MetricCard label="Total employees" value={employees.length} />
        <MetricCard
          label="Active"
          value={activeCount}
          sub={`${Math.round((activeCount / Math.max(employees.length, 1)) * 100)}% of team`}
        />
        <MetricCard label="With active case" value={withCaseCount} />
        <MetricCard label="International" value={internationalCount} />
      </div>

      {/* toolbar */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9ca3af]"
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search by name, email, band…"
            className="w-full pl-9 pr-3 py-2 text-sm border border-[#e5e7eb] rounded-lg bg-white placeholder:text-[#9ca3af] text-[#0b2b43] focus:outline-none focus:border-[#1D9E75] focus:ring-1 focus:ring-[#1D9E75]"
          />
        </div>
        {selected.size > 0 && (
          <span className="text-sm text-[#6b7280]">
            {selected.size} selected
          </span>
        )}
      </div>

      {/* table */}
      <div className="border border-[#e5e7eb] rounded-xl overflow-hidden">
        <table className="w-full text-sm" style={{ tableLayout: 'fixed' }}>
          <colgroup>
            <col style={{ width: '36px' }} />
            <col style={{ width: '200px' }} />
            <col style={{ width: '160px' }} />
            <col style={{ width: '160px' }} />
            <col style={{ width: '100px' }} />
            <col style={{ width: '100px' }} />
            <col style={{ width: '60px' }} />
          </colgroup>
          <thead>
            <tr className="bg-[#f3f4f6] border-b border-[#e5e7eb]">
              <th className="px-3 py-2 text-left">
                <input
                  type="checkbox"
                  checked={allPageSelected}
                  onChange={toggleAll}
                  className="w-3.5 h-3.5 accent-[#1D9E75] cursor-pointer"
                />
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wide">
                Name
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wide">
                Email
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wide">
                Assignment
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wide">
                Band
              </th>
              <th className="px-3 py-2 text-left text-xs font-medium text-[#6b7280] uppercase tracking-wide">
                Status
              </th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {pageRows.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-sm text-[#9ca3af]"
                >
                  {search ? 'No employees match your search.' : 'No employees yet.'}
                </td>
              </tr>
            ) : (
              pageRows.map((emp, idx) => {
                const isExpanded = expanded === emp.id;
                const isSelected = selected.has(emp.id);
                const av = avatarColor(idx);
                const displayName = emp.full_name || emp.email || emp.profile_id || '—';

                return (
                  <React.Fragment key={emp.id}>
                    <tr
                      className={`border-b border-[#e5e7eb] cursor-pointer transition-colors ${
                        isSelected
                          ? 'bg-[#E1F5EE]'
                          : 'hover:bg-[#f9fafb]'
                      }`}
                      onClick={() =>
                        setExpanded((prev) => (prev === emp.id ? null : emp.id))
                      }
                    >
                      <td
                        className="px-3 py-2.5"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleRow(emp.id)}
                          className="w-3.5 h-3.5 accent-[#1D9E75] cursor-pointer"
                        />
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-2 min-w-0">
                          <svg
                            className={`flex-shrink-0 text-[#9ca3af] transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                            width="12"
                            height="12"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            aria-hidden="true"
                          >
                            <polyline points="6 9 12 15 18 9" />
                          </svg>
                          <div
                            className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-medium"
                            style={{ background: av.bg, color: av.color }}
                          >
                            {initials(emp.full_name)}
                          </div>
                          <span className="truncate font-medium text-[#0b2b43]">
                            {displayName}
                          </span>
                        </div>
                      </td>
                      <td className="px-3 py-2.5 text-[#6b7280] truncate">
                        {emp.email || '—'}
                      </td>
                      <td className="px-3 py-2.5 text-[#374151] truncate">
                        {emp.assignment_type || '—'}
                      </td>
                      <td className="px-3 py-2.5 text-[#374151]">
                        {emp.band || '—'}
                      </td>
                      <td className="px-3 py-2.5">
                        <Badge variant={statusVariant(emp.status)} size="sm">
                          {statusLabel(emp.status)}
                        </Badge>
                      </td>
                      <td
                        className="px-3 py-2.5 text-right"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Link
                          to={buildRoute('hrEmployeeDetail', { id: emp.id })}
                          className="text-[#9ca3af] hover:text-[#0b2b43] transition-colors text-xs"
                          title="View employee"
                        >
                          →
                        </Link>
                      </td>
                    </tr>
                    {isExpanded && <ExpandRow emp={emp} />}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>

        {/* pagination */}
        {pageCount > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-[#e5e7eb] bg-white">
            <span className="text-xs text-[#9ca3af]">
              {(safePage - 1) * PAGE_SIZE + 1}–
              {Math.min(safePage * PAGE_SIZE, filtered.length)} of{' '}
              {filtered.length} employees
            </span>
            <div className="flex gap-1">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={safePage === 1}
              >
                ←
              </Button>
              {Array.from({ length: pageCount }, (_, i) => i + 1).map((p) => (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`w-7 h-7 rounded-md text-xs border transition-colors ${
                    p === safePage
                      ? 'bg-[#1D9E75] border-[#1D9E75] text-white font-medium'
                      : 'border-[#e5e7eb] text-[#374151] hover:bg-[#f3f4f6]'
                  }`}
                >
                  {p}
                </button>
              ))}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
                disabled={safePage === pageCount}
              >
                →
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* empty / total count footer */}
      {pageCount <= 1 && filtered.length > 0 && (
        <div className="text-xs text-[#9ca3af] mt-3 text-right">
          {filtered.length} employee{filtered.length !== 1 ? 's' : ''}
        </div>
      )}
    </div>
  );
};
