/**
 * ErrorTicketsTab — admin view for error tracking.
 *
 * Shows error_tickets sorted by last_seen desc.
 * Each row is expandable to show recent error_logs for that fingerprint.
 * Status and notes are editable inline.
 */

import { useEffect, useState, useCallback } from 'react';
import { supabase } from '../../api/supabase';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type TicketStatus = 'open' | 'in_progress' | 'resolved';

interface ErrorTicket {
  id: string;
  fingerprint: string;
  message: string;
  first_seen: string;
  last_seen: string;
  event_count: number;
  status: TicketStatus;
  notes: string | null;
  resolved_at: string | null;
}

interface ErrorLog {
  id: string;
  message: string;
  stack: string | null;
  url: string;
  browser: string;
  component_name: string | null;
  breadcrumbs: { type: string; message: string; timestamp: string }[];
  severity: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

const STATUS_STYLES: Record<TicketStatus, string> = {
  open:        'bg-red-100 text-red-700',
  in_progress: 'bg-amber-100 text-amber-700',
  resolved:    'bg-green-100 text-green-700',
};

const STATUS_LABELS: Record<TicketStatus, string> = {
  open:        'Open',
  in_progress: 'In progress',
  resolved:    'Resolved',
};

function StatusBadge({ status }: { status: TicketStatus }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Format helpers
// ---------------------------------------------------------------------------

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) +
    ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

function fmtRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins  = Math.floor(diff / 60_000);
  const hours = Math.floor(diff / 3_600_000);
  const days  = Math.floor(diff / 86_400_000);
  if (mins  < 60)  return `${mins}m ago`;
  if (hours < 24)  return `${hours}h ago`;
  return `${days}d ago`;
}

// ---------------------------------------------------------------------------
// Expanded row — recent logs for a fingerprint
// ---------------------------------------------------------------------------

function ExpandedLogs({ fingerprint }: { fingerprint: string }) {
  const [logs, setLogs] = useState<ErrorLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase
      .from('error_logs')
      .select('id, message, stack, url, browser, component_name, breadcrumbs, severity, created_at')
      .eq('fingerprint', fingerprint)
      .order('created_at', { ascending: false })
      .limit(10)
      .then(({ data }) => {
        setLogs((data as ErrorLog[]) ?? []);
        setLoading(false);
      });
  }, [fingerprint]);

  if (loading) {
    return <p className="text-xs text-gray-400 py-4 px-6">Loading events...</p>;
  }
  if (logs.length === 0) {
    return <p className="text-xs text-gray-400 py-4 px-6">No events found.</p>;
  }

  return (
    <div className="px-6 py-4 space-y-4 bg-gray-50 border-t border-gray-100">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
        Recent events (last {logs.length})
      </p>
      {logs.map((log) => (
        <div key={log.id} className="rounded border border-gray-200 bg-white p-4 text-sm space-y-2">
          <div className="flex items-center justify-between gap-4">
            <span className="text-gray-500 text-xs">{fmtDate(log.created_at)}</span>
            {log.component_name && (
              <span className="text-xs text-gray-400">in {log.component_name}</span>
            )}
          </div>
          <p className="text-gray-800 font-medium break-words">{log.message}</p>
          {log.url && (
            <p className="text-xs text-gray-400 break-all">{log.url}</p>
          )}
          {log.stack && (
            <pre className="text-xs text-gray-500 bg-gray-50 rounded p-3 overflow-x-auto whitespace-pre-wrap max-h-40">
              {log.stack}
            </pre>
          )}
          {Array.isArray(log.breadcrumbs) && log.breadcrumbs.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1">Breadcrumbs</p>
              <ol className="space-y-0.5">
                {log.breadcrumbs.map((b, i) => (
                  <li key={i} className="text-xs text-gray-400">
                    {b.type === 'navigation' ? '→' : '!'} {b.message}
                    <span className="ml-2 text-gray-300">{fmtRelative(b.timestamp)}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main tab component
// ---------------------------------------------------------------------------

export function ErrorTicketsTab() {
  const [tickets, setTickets]         = useState<ErrorTicket[]>([]);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState<string | null>(null);
  const [expandedId, setExpandedId]   = useState<string | null>(null);
  const [filter, setFilter]           = useState<TicketStatus | 'all'>('all');
  const [savingId, setSavingId]       = useState<string | null>(null);
  const [editingNotes, setEditingNotes] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const { data, error: err } = await supabase
      .from('error_tickets')
      .select('id, fingerprint, message, first_seen, last_seen, event_count, status, notes, resolved_at')
      .order('last_seen', { ascending: false })
      .limit(200);

    if (err) {
      setError('Failed to load error tickets.');
    } else {
      setTickets((data as ErrorTicket[]) ?? []);
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const updateStatus = async (ticket: ErrorTicket, newStatus: TicketStatus) => {
    setSavingId(ticket.id);
    const update: Partial<ErrorTicket> = {
      status:      newStatus,
      resolved_at: newStatus === 'resolved' ? new Date().toISOString() : null,
    };
    const { error: err } = await supabase
      .from('error_tickets')
      .update(update)
      .eq('id', ticket.id);

    if (!err) {
      setTickets((prev) =>
        prev.map((t) => (t.id === ticket.id ? { ...t, ...update } : t))
      );
    }
    setSavingId(null);
  };

  const saveNotes = async (ticket: ErrorTicket) => {
    const notes = editingNotes[ticket.id] ?? ticket.notes ?? '';
    if (notes === (ticket.notes ?? '')) return; // no change
    setSavingId(ticket.id);
    const { error: err } = await supabase
      .from('error_tickets')
      .update({ notes })
      .eq('id', ticket.id);

    if (!err) {
      setTickets((prev) =>
        prev.map((t) => (t.id === ticket.id ? { ...t, notes } : t))
      );
    }
    setSavingId(null);
  };

  const displayed = filter === 'all'
    ? tickets
    : tickets.filter((t) => t.status === filter);

  const counts: Record<string, number> = {
    all:         tickets.length,
    open:        tickets.filter((t) => t.status === 'open').length,
    in_progress: tickets.filter((t) => t.status === 'in_progress').length,
    resolved:    tickets.filter((t) => t.status === 'resolved').length,
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-sm text-gray-400">Loading error tickets...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <p className="text-sm text-red-600">{error}</p>
        <button
          onClick={load}
          className="text-sm text-gray-500 underline"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-900">Error Tickets</h2>
          <p className="text-sm text-gray-500">
            Grouped by fingerprint — {counts.open} open, {counts.in_progress} in progress
          </p>
        </div>
        <button
          onClick={load}
          className="text-xs text-gray-400 hover:text-gray-600 underline"
        >
          Refresh
        </button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 border-b border-gray-200 pb-2">
        {(['all', 'open', 'in_progress', 'resolved'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`text-xs px-3 py-1.5 rounded font-medium transition-colors ${
              filter === f
                ? 'bg-gray-900 text-white'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
            }`}
          >
            {f === 'all' ? 'All' : STATUS_LABELS[f as TicketStatus]}
            <span className="ml-1.5 opacity-60">{counts[f]}</span>
          </button>
        ))}
      </div>

      {/* Empty state */}
      {displayed.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <p className="text-sm font-medium text-gray-600 mb-1">
            {filter === 'all' ? 'No errors recorded yet.' : `No ${STATUS_LABELS[filter as TicketStatus].toLowerCase()} tickets.`}
          </p>
          <p className="text-xs text-gray-400">
            {filter === 'all' ? 'The capture layer is active — errors will appear here when they occur.' : ''}
          </p>
        </div>
      )}

      {/* Ticket list */}
      {displayed.length > 0 && (
        <div className="divide-y divide-gray-100 rounded-lg border border-gray-200 overflow-hidden">
          {displayed.map((ticket) => {
            const isExpanded = expandedId === ticket.id;
            const isSaving   = savingId === ticket.id;

            return (
              <div key={ticket.id} className="bg-white">
                {/* Row */}
                <div className="flex items-start gap-4 px-4 py-4">
                  {/* Expand toggle */}
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : ticket.id)}
                    className="mt-0.5 text-gray-300 hover:text-gray-500 flex-shrink-0"
                    aria-label={isExpanded ? 'Collapse' : 'Expand'}
                  >
                    <svg
                      className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                      fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                    </svg>
                  </button>

                  {/* Content */}
                  <div className="flex-1 min-w-0 space-y-2">
                    {/* Message + badge */}
                    <div className="flex items-start gap-3 flex-wrap">
                      <p className="text-sm font-medium text-gray-900 break-words flex-1 min-w-0">
                        {ticket.message}
                      </p>
                      <StatusBadge status={ticket.status} />
                    </div>

                    {/* Meta */}
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-400">
                      <span>
                        <span className="font-medium text-gray-500">{ticket.event_count}</span> events
                      </span>
                      <span>First: {fmtDate(ticket.first_seen)}</span>
                      <span>Last: {fmtRelative(ticket.last_seen)}</span>
                      <span className="font-mono text-gray-300">{ticket.fingerprint.slice(0, 8)}</span>
                    </div>

                    {/* Status controls */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs text-gray-400">Status:</span>
                      {(['open', 'in_progress', 'resolved'] as TicketStatus[]).map((s) => (
                        <button
                          key={s}
                          onClick={() => updateStatus(ticket, s)}
                          disabled={ticket.status === s || isSaving}
                          className={`text-xs px-2 py-0.5 rounded border transition-colors ${
                            ticket.status === s
                              ? `${STATUS_STYLES[s]} border-transparent cursor-default`
                              : 'border-gray-200 text-gray-400 hover:text-gray-600 hover:border-gray-300'
                          }`}
                        >
                          {STATUS_LABELS[s]}
                        </button>
                      ))}
                      {isSaving && (
                        <span className="text-xs text-gray-300">Saving...</span>
                      )}
                    </div>

                    {/* Notes */}
                    <div>
                      <textarea
                        rows={2}
                        placeholder="Add notes (fix applied, root cause, PR link...)"
                        className="w-full text-xs border border-gray-200 rounded px-3 py-2 text-gray-600 placeholder-gray-300 resize-none focus:outline-none focus:ring-1 focus:ring-gray-400"
                        value={editingNotes[ticket.id] ?? ticket.notes ?? ''}
                        onChange={(e) =>
                          setEditingNotes((prev) => ({ ...prev, [ticket.id]: e.target.value }))
                        }
                        onBlur={() => saveNotes(ticket)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                            (e.target as HTMLTextAreaElement).blur();
                          }
                        }}
                      />
                      <p className="text-xs text-gray-300 mt-0.5">⌘ Enter to save</p>
                    </div>
                  </div>
                </div>

                {/* Expanded logs */}
                {isExpanded && <ExpandedLogs fingerprint={ticket.fingerprint} />}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
