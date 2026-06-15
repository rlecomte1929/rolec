/**
 * ProviderStatusGrid
 *
 * Matrix table: rows = active cases, columns = provider type.
 * Each cell shows a colour-coded status badge via ProviderStatusCell.
 *
 * Features:
 *  - Sortable by employee name, destination, move date, or overall coordination status
 *  - 60-second auto-refresh
 *  - Manual refresh button
 *  - Empty state when no cases
 *  - Horizontally scrollable on narrow viewports (≥ 768 px reads clean)
 */
import React, { useState, useCallback } from 'react';
import { Button } from '../antigravity/Button';
import { Link } from 'react-router-dom';
import { ProviderStatusCell } from './ProviderStatusCell';
import type { ProviderGridRow, CoordinationStatus } from '../../api/client';
import { ROUTE_DEFS } from '../../navigation/routes';

const PROVIDER_COLUMNS: Array<{ key: keyof ProviderGridRow['cells']; label: string }> = [
  { key: 'housing',      label: 'Housing' },
  { key: 'immigration',  label: 'Immigration' },
  { key: 'shipping',     label: 'Shipping' },
  { key: 'other',        label: 'Other' },
];

type SortKey = 'employee_name' | 'dest_country' | 'move_date' | 'coordination_status';

const COORD_ORDER: Record<CoordinationStatus, number> = {
  'at-risk':     0,
  'in-progress': 1,
  'not-started': 2,
  complete:      3,
};

const COORD_BADGE: Record<CoordinationStatus, { bg: string; text: string; label: string }> = {
  'not-started': { bg: '#f3f4f6', text: '#6b7280', label: 'Not started' },
  'in-progress': { bg: '#e0f2fe', text: '#0369a1', label: 'In progress' },
  'at-risk':     { bg: '#fef3c7', text: '#92400e', label: 'At risk' },
  complete:      { bg: '#d1fae5', text: '#065f46', label: 'Complete' },
};

interface ProviderStatusGridProps {
  rows: ProviderGridRow[];
  loading: boolean;
  lastRefreshed: Date | null;
  onRefresh: () => void;
}

export const ProviderStatusGrid: React.FC<ProviderStatusGridProps> = ({
  rows,
  loading,
  lastRefreshed,
  onRefresh,
}) => {
  const [sortKey, setSortKey]     = useState<SortKey>('coordination_status');
  const [sortAsc, setSortAsc]     = useState(true);

  const handleSort = useCallback((key: SortKey) => {
    setSortKey(prev => {
      if (prev === key) {
        setSortAsc(a => !a);
        return prev;
      }
      setSortAsc(true);
      return key;
    });
  }, []);

  const sorted = [...rows].sort((a, b) => {
    let cmp = 0;
    if (sortKey === 'employee_name') {
      cmp = (a.employee_name || '').localeCompare(b.employee_name || '');
    } else if (sortKey === 'dest_country') {
      cmp = (a.dest_country || '').localeCompare(b.dest_country || '');
    } else if (sortKey === 'move_date') {
      cmp = (a.move_date || '').localeCompare(b.move_date || '');
    } else {
      const ao = COORD_ORDER[a.coordination_status as CoordinationStatus] ?? 99;
      const bo = COORD_ORDER[b.coordination_status as CoordinationStatus] ?? 99;
      cmp = ao - bo;
    }
    return sortAsc ? cmp : -cmp;
  });

  const SortIcon: React.FC<{ col: SortKey }> = ({ col }) => {
    if (sortKey !== col) return <span style={{ opacity: 0.3, marginLeft: 4 }}>↕</span>;
    return <span style={{ marginLeft: 4 }}>{sortAsc ? '↑' : '↓'}</span>;
  };

  const thStyle: React.CSSProperties = {
    padding: '10px 14px',
    textAlign: 'left',
    fontSize: 12,
    fontWeight: 600,
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    borderBottom: '1px solid #e5e7eb',
    whiteSpace: 'nowrap',
    background: '#f9fafb',
    cursor: 'pointer',
    userSelect: 'none',
  };

  const tdStyle: React.CSSProperties = {
    padding: '10px 14px',
    fontSize: 13,
    borderBottom: '1px solid #f3f4f6',
    verticalAlign: 'middle',
    whiteSpace: 'nowrap',
  };

  const refreshedStr = lastRefreshed
    ? lastRefreshed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null;

  return (
    <div>
      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <p style={{ margin: 0, fontSize: 13, color: '#6b7280' }}>
          {rows.length === 0 && !loading
            ? 'No active cases'
            : `${rows.length} case${rows.length !== 1 ? 's' : ''}`}
          {refreshedStr && <span> · Updated {refreshedStr}</span>}
        </p>
        <Button unstyled
          onClick={onRefresh}
          disabled={loading}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '6px 12px',
            borderRadius: 6,
            border: '1px solid #d1d5db',
            background: '#fff',
            fontSize: 13,
            fontWeight: 500,
            color: '#374151',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1,
          }}
        >
          <span style={{ display: 'inline-block', animation: loading ? 'spin 1s linear infinite' : 'none' }}>
            ↻
          </span>
          Refresh
        </Button>
      </div>

      {/* Empty state */}
      {rows.length === 0 && !loading && (
        <div
          style={{
            border: '2px dashed #e5e7eb',
            borderRadius: 10,
            padding: '48px 24px',
            textAlign: 'center',
            color: '#9ca3af',
          }}
        >
          <p style={{ margin: 0, fontWeight: 500, fontSize: 15 }}>No providers assigned.</p>
          <p style={{ margin: '6px 0 0', fontSize: 13 }}>
            Assign providers in the{' '}
            <Link to={ROUTE_DEFS.hrCommandCenter.path} style={{ color: '#1f8e8b', textDecoration: 'underline' }}>
              Mobility command center
            </Link>{' '}
            to track their status here.
          </p>
        </div>
      )}

      {/* Grid table */}
      {rows.length > 0 && (
        <div style={{ overflowX: 'auto', borderRadius: 10, border: '1px solid #e5e7eb' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff' }}>
            <thead>
              <tr>
                <th style={{ ...thStyle, minWidth: 180 }} onClick={() => handleSort('employee_name')}>
                  Employee <SortIcon col="employee_name" />
                </th>
                <th style={{ ...thStyle, minWidth: 130 }} onClick={() => handleSort('dest_country')}>
                  Destination <SortIcon col="dest_country" />
                </th>
                <th style={{ ...thStyle, minWidth: 110 }} onClick={() => handleSort('move_date')}>
                  Move date <SortIcon col="move_date" />
                </th>
                <th style={{ ...thStyle, minWidth: 130 }} onClick={() => handleSort('coordination_status')}>
                  Overall <SortIcon col="coordination_status" />
                </th>
                {PROVIDER_COLUMNS.map(col => (
                  <th key={col.key} style={{ ...thStyle, minWidth: 130 }}>
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map(row => {
                const coord = row.coordination_status as CoordinationStatus;
                const badge = COORD_BADGE[coord] ?? COORD_BADGE['not-started'];
                return (
                  <tr
                    key={row.case_id}
                    style={{ transition: 'background 0.1s' }}
                    onMouseEnter={e => ((e.currentTarget as HTMLTableRowElement).style.background = '#f9fafb')}
                    onMouseLeave={e => ((e.currentTarget as HTMLTableRowElement).style.background = '')}
                  >
                    <td style={tdStyle}>
                      <div style={{ fontWeight: 500, color: '#111827' }}>{row.employee_name}</div>
                      {row.employee_identifier && row.employee_identifier !== row.employee_name && (
                        <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>
                          {row.employee_identifier}
                        </div>
                      )}
                    </td>
                    <td style={{ ...tdStyle, color: '#374151' }}>{row.dest_country ?? '—'}</td>
                    <td style={{ ...tdStyle, color: '#374151' }}>
                      {row.move_date
                        ? new Date(row.move_date).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })
                        : '—'}
                    </td>
                    <td style={tdStyle}>
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '3px 10px',
                          borderRadius: 9999,
                          backgroundColor: badge.bg,
                          color: badge.text,
                          fontSize: 12,
                          fontWeight: 500,
                        }}
                      >
                        {badge.label}
                      </span>
                    </td>
                    {PROVIDER_COLUMNS.map(col => (
                      <td key={col.key} style={tdStyle}>
                        <ProviderStatusCell
                          status={row.cells[col.key]}
                          caseId={row.case_id}
                          providerType={col.label}
                        />
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Loading overlay skeleton */}
      {loading && rows.length === 0 && (
        <div style={{ padding: '40px 0', textAlign: 'center', color: '#9ca3af', fontSize: 14 }}>
          Loading provider grid…
        </div>
      )}

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
};
