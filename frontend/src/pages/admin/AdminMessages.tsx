import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AdminLayout } from './AdminLayout';
import { Card, Button, Badge, Alert } from '../../components/antigravity';
import { adminAPI, adminCollaborationAPI } from '../../api/client';
import { ROUTE_DEFS } from '../../navigation/routes';
import type { AdminSupportCase } from '../../types';

type Thread = {
  thread_id: string;
  thread_type: 'hr_employee' | 'collaboration';
  assignment_id?: string;
  company_id?: string;
  company_name?: string;
  employee_name?: string;
  hr_name?: string;
  participant_id?: string | null;
  participant_name?: string | null;
  participant_role?: string | null;
  participants?: string[];
  last_message_preview?: string;
  last_message_at?: string;
  message_count?: number;
  unread_count?: number;
  has_unread?: boolean;
  status?: string;
  target_type?: string;
  target_id?: string;
  title?: string;
};

type GroupBy = 'thread' | 'person' | 'role';

type HrThreadDetail = {
  thread_type: 'hr_employee';
  assignment_id: string;
  company_id?: string;
  company_name?: string;
  employee_name?: string;
  hr_name?: string;
  participants?: string[];
  messages: Array<{
    id: string;
    body: string;
    created_at: string;
    sender_display_name?: string;
    hr_user_id?: string;
    sender_user_id?: string;
    recipient_user_id?: string;
  }>;
  status?: string;
};

function ThreadRow({
  thread,
  isSelected,
  onSelect,
  formatTimeAgo,
}: {
  thread: Thread;
  isSelected: boolean;
  onSelect: () => void;
  formatTimeAgo: (s?: string) => string;
}) {
  const participants = thread.participants?.join(', ') || thread.participant_name || thread.company_name || '—';
  const raw = thread.last_message_preview || '—';
  const previewText = raw.length > 60 ? raw.slice(0, 60).trimEnd() + '…' : raw;
  const roleLabel = thread.participant_role === 'employee' ? 'Employee' : thread.thread_type === 'hr_employee' ? 'HR' : 'Collab';
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => e.key === 'Enter' && onSelect()}
      className={`flex flex-col gap-1 px-3 py-2 cursor-pointer min-w-0 ${
        isSelected ? 'bg-[#f0f9ff] border-l-2 border-l-[#0b2b43]' : 'hover:bg-[#f9fafb]'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium text-[#0b2b43] text-sm truncate flex items-center gap-1.5">
          {thread.has_unread && (
            <span className="w-2 h-2 rounded-full bg-[#0b2b43] shrink-0" title="Unread" aria-label="Unread" />
          )}
          {participants}
        </span>
        <span className="text-xs text-[#6b7280] shrink-0">{formatTimeAgo(thread.last_message_at)}</span>
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <Badge variant="neutral" size="sm">{roleLabel}</Badge>
        {thread.status && (
          <span
            className={`inline-block px-1.5 py-0.5 rounded text-xs ${
              thread.status === 'open' || thread.status === 'assigned'
                ? 'bg-amber-100 text-amber-800'
                : 'bg-gray-100 text-gray-700'
            }`}
          >
            {thread.status}
          </span>
        )}
      </div>
      <p className="text-xs text-[#6b5563] truncate" title={thread.last_message_preview}>
        {previewText}
      </p>
    </div>
  );
}

export const AdminMessages: React.FC = () => {
  const navigate = useNavigate();
  const [threads, setThreads] = useState<Thread[]>([]);
  const [companies, setCompanies] = useState<Array<{ id: string; name: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [companyFilter, setCompanyFilter] = useState('');
  const [selectedThread, setSelectedThread] = useState<Thread | null>(null);
  const [threadDetail, setThreadDetail] = useState<HrThreadDetail | null>(null);
  const [collabComments, setCollabComments] = useState<Array<{ id: string; body: string; created_at: string; author_display_name?: string }>>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'conversations' | 'tickets'>('conversations');
  const [supportCases, setSupportCases] = useState<AdminSupportCase[]>([]);
  const [editingTicket, setEditingTicket] = useState<AdminSupportCase | null>(null);
  const [ticketPatchForm, setTicketPatchForm] = useState<{ priority: string; status: string; assignee_id: string; category: string }>({ priority: 'medium', status: 'open', assignee_id: '', category: 'other' });
  const [groupBy, setGroupBy] = useState<GroupBy>('person');
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());

  const loadThreads = useCallback(async () => {
    if (!companyFilter) return;
    setLoading(true);
    setError(null);
    try {
      const res = await adminAPI.listMessageThreads({
        company_id: companyFilter,
        limit: 100,
        offset: 0,
      });
      setThreads(res.threads || []);
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : (err as Error)?.message;
      setError(String(msg || 'Failed to load threads'));
      setThreads([]);
    } finally {
      setLoading(false);
    }
  }, [companyFilter]);

  const loadCompanies = useCallback(async () => {
    try {
      const res = await adminAPI.listCompanies();
      setCompanies((res.companies || []).map((c: { id: string; name: string }) => ({ id: c.id, name: c.name || c.id })));
    } catch {
      setCompanies([]);
    }
  }, []);

  const loadSupportCases = useCallback(async () => {
    try {
      const res = await adminAPI.listSupportCases({
        company_id: companyFilter || undefined,
      });
      setSupportCases(res.support_cases || []);
    } catch {
      setSupportCases([]);
    }
  }, [companyFilter]);

  useEffect(() => {
    if (companyFilter && activeTab === 'conversations') loadThreads();
    else if (activeTab === 'conversations') setThreads([]);
  }, [companyFilter, activeTab, loadThreads]);

  useEffect(() => {
    loadCompanies();
  }, [loadCompanies]);

  useEffect(() => {
    if (activeTab === 'tickets') loadSupportCases();
  }, [activeTab, loadSupportCases]);

  const loadThreadDetail = useCallback(async (t: Thread) => {
    setSelectedThread(t);
    setThreadDetail(null);
    setCollabComments([]);
    setDetailLoading(true);
    try {
      if (t.thread_type === 'hr_employee' && t.assignment_id) {
        const res = await adminAPI.getHrThreadDetail(t.assignment_id);
        setThreadDetail(res);
      } else if (t.thread_type === 'collaboration') {
        const [_thread, commentsRes] = await Promise.all([
          adminCollaborationAPI.getThreadById(t.thread_id),
          adminCollaborationAPI.getComments(t.thread_id),
        ]);
        void _thread;
        setThreadDetail(null);
        setCollabComments((commentsRes?.comments || []).map((c: any) => ({
          id: c.id,
          body: c.body,
          created_at: c.created_at,
          author_display_name: c.author_display_name || c.author_user_id?.slice(0, 8) + '…',
        })));
      }
    } catch (e) {
      setError((e as Error)?.message || 'Failed to load thread');
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const formatDate = (s?: string) => (s ? new Date(s).toLocaleString() : '—');
  const formatTimeAgo = (s?: string) => {
    if (!s) return '—';
    const d = new Date(s);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString();
  };

  // Group threads: map groupKey -> { label, threads }. Keys for person/role are stable for expand/collapse.
  const groups = React.useMemo(() => {
    const map = new Map<string, { label: string; threads: Thread[] }>();
    for (const t of threads) {
      let key: string;
      let label: string;
      if (groupBy === 'thread') {
        key = `${t.thread_type}:${t.thread_id}`;
        label = t.participants?.join(', ') || t.company_name || t.thread_id;
        map.set(key, { label, threads: [t] });
      } else if (groupBy === 'role') {
        const roleLabel =
          t.participant_role === 'employee' ? 'Employee' : t.participant_role === 'collaboration' ? 'Collaboration' : 'Other';
        key = `role:${t.participant_role || 'other'}:${t.participant_id || t.thread_id}`;
        label = `${roleLabel} · ${t.participant_name || t.participants?.join(', ') || '—'}`;
        if (!map.has(key)) map.set(key, { label, threads: [] });
        map.get(key)!.threads.push(t);
      } else {
        key = `person:${t.participant_id || t.thread_id}`;
        label = t.participant_name || t.participants?.join(', ') || t.thread_id;
        if (!map.has(key)) map.set(key, { label, threads: [] });
        map.get(key)!.threads.push(t);
      }
    }
    return map;
  }, [threads, groupBy]);

  const groupKeys = [...groups.keys()];

  const expandAll = () => setExpandedKeys(new Set(groupKeys));
  const collapseAll = () => setExpandedKeys(new Set());
  const toggleGroup = (key: string) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };
  const isGroupExpanded = (key: string) => groupBy === 'thread' || expandedKeys.has(key);

  const openEditTicket = (c: AdminSupportCase) => {
    setEditingTicket(c);
    setTicketPatchForm({
      priority: c.priority || 'medium',
      status: c.status || 'open',
      assignee_id: c.assignee_id || '',
      category: c.category || 'other',
    });
  };

  const saveTicketPatch = async () => {
    if (!editingTicket) return;
    try {
      await adminAPI.patchSupportCase(editingTicket.id, {
        priority: ticketPatchForm.priority,
        status: ticketPatchForm.status,
        assignee_id: ticketPatchForm.assignee_id || undefined,
        category: ticketPatchForm.category,
      });
      setEditingTicket(null);
      loadSupportCases();
    } catch (e) {
      console.error(e);
    }
  };

  const PRIORITY_OPTIONS = ['low', 'medium', 'high', 'urgent'] as const;
  const STATUS_OPTIONS = ['open', 'investigating', 'blocked', 'resolved'] as const;
  const CATEGORY_OPTIONS = ['bug', 'feature request', 'onboarding', 'policy question', 'supplier issue', 'other'] as const;

  return (
    <AdminLayout title="Messages" subtitle="Unified operations inbox — conversations and support tickets">
      {/* Company filter at top (shared) */}
      <Card padding="lg" className="mb-4">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <label className="block text-sm font-medium text-[#374151] mb-1">Company</label>
            <select
              value={companyFilter}
              onChange={(e) => setCompanyFilter(e.target.value)}
              className="border border-[#d1d5db] rounded px-3 py-2 text-sm min-w-[200px]"
            >
              <option value="">Select company</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div className="flex gap-2 pt-6">
            <button
              type="button"
              onClick={() => setActiveTab('conversations')}
              className={`px-3 py-1.5 rounded text-sm font-medium ${activeTab === 'conversations' ? 'bg-[#0b2b43] text-white' : 'bg-[#f1f5f9] text-[#4b5563] hover:bg-[#e2e8f0]'}`}
            >
              Conversations
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('tickets')}
              className={`px-3 py-1.5 rounded text-sm font-medium ${activeTab === 'tickets' ? 'bg-[#0b2b43] text-white' : 'bg-[#f1f5f9] text-[#4b5563] hover:bg-[#e2e8f0]'}`}
            >
              Tickets
            </button>
          </div>
        </div>
      </Card>

      {activeTab === 'tickets' && (
        <Card padding="lg">
          <h2 className="text-lg font-semibold text-[#0b2b43] mb-3">Support tickets</h2>
          <p className="text-sm text-[#6b7280] mb-4">
            {companyFilter ? `Showing tickets for selected company.` : 'Select a company to filter tickets, or view all.'}
          </p>
          <div className="border border-[#e5e7eb] rounded-lg overflow-hidden">
            {supportCases.length === 0 ? (
              <div className="p-8 text-center text-[#6b7280]">No tickets found.</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-[#f9fafb] border-b border-[#e5e7eb]">
                    <th className="text-left py-3 px-4 font-medium text-[#374151]">Summary</th>
                    <th className="text-left py-3 px-4 font-medium text-[#374151]">Priority</th>
                    <th className="text-left py-3 px-4 font-medium text-[#374151]">Status</th>
                    <th className="text-left py-3 px-4 font-medium text-[#374151]">Category</th>
                    <th className="text-left py-3 px-4 font-medium text-[#374151]">Assignee</th>
                    <th className="text-left py-3 px-4 font-medium text-[#374151]">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {supportCases.map((c) => (
                    <tr key={c.id} className="border-b border-[#e5e7eb] hover:bg-[#f9fafb]">
                      <td className="py-3 px-4">
                        <span className="font-medium text-[#0b2b43]">{c.summary || c.id}</span>
                        {c.last_error_code && (
                          <span className="block text-xs text-[#6b7280]">Error: {c.last_error_code}</span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <Badge
                          variant={c.priority === 'urgent' ? 'warning' : c.priority === 'high' ? 'warning' : 'neutral'}
                          size="sm"
                        >
                          {(c.priority || 'medium').toLowerCase()}
                        </Badge>
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant="neutral" size="sm">
                          {(c.status || 'open').toLowerCase()}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-[#4b5563]">{(c.category || '—').replace(/_/g, ' ')}</td>
                      <td className="py-3 px-4 text-[#4b5563]">{c.assignee_id ? String(c.assignee_id).slice(0, 8) + '…' : '—'}</td>
                      <td className="py-3 px-4">
                        <div className="flex flex-wrap gap-1">
                          <Button size="sm" variant="outline" onClick={() => openEditTicket(c)}>
                            Update
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              const note = window.prompt('Internal note:');
                              if (note) {
                                const reason = window.prompt('Reason for note (required):');
                                if (reason) adminAPI.addSupportNote(c.id, { note, reason }).then(loadSupportCases).catch(console.error);
                              }
                            }}
                          >
                            Add note
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              const reason = window.prompt('Reason for export (required):');
                              if (reason) {
                                adminAPI.adminAction('export-support-bundle', { reason, payload: { support_case_id: c.id } }).then(() => alert('Export requested.')).catch(console.error);
                              }
                            }}
                          >
                            Export
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </Card>
      )}

      {/* Update ticket modal */}
      {editingTicket && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setEditingTicket(null)}>
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-[#0b2b43] mb-4">Update ticket</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-[#374151] mb-1">Priority</label>
                <select
                  value={ticketPatchForm.priority}
                  onChange={(e) => setTicketPatchForm((f) => ({ ...f, priority: e.target.value }))}
                  className="border border-[#d1d5db] rounded px-3 py-2 text-sm w-full"
                >
                  {PRIORITY_OPTIONS.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-[#374151] mb-1">Status</label>
                <select
                  value={ticketPatchForm.status}
                  onChange={(e) => setTicketPatchForm((f) => ({ ...f, status: e.target.value }))}
                  className="border border-[#d1d5db] rounded px-3 py-2 text-sm w-full"
                >
                  {STATUS_OPTIONS.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-[#374151] mb-1">Category</label>
                <select
                  value={ticketPatchForm.category}
                  onChange={(e) => setTicketPatchForm((f) => ({ ...f, category: e.target.value }))}
                  className="border border-[#d1d5db] rounded px-3 py-2 text-sm w-full"
                >
                  {CATEGORY_OPTIONS.map((cat) => (
                    <option key={cat} value={cat}>{cat.replace(/_/g, ' ')}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-[#374151] mb-1">Assignee (profile ID)</label>
                <input
                  type="text"
                  value={ticketPatchForm.assignee_id}
                  onChange={(e) => setTicketPatchForm((f) => ({ ...f, assignee_id: e.target.value }))}
                  placeholder="Leave empty to unassign"
                  className="border border-[#d1d5db] rounded px-3 py-2 text-sm w-full"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <Button variant="outline" onClick={() => setEditingTicket(null)}>Cancel</Button>
              <Button onClick={saveTicketPatch}>Save</Button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'conversations' && (
        <>
          {error && (
            <Alert variant="error" className="mb-4">
              {error}
              <Button variant="outline" size="sm" className="ml-2" onClick={() => setError(null)}>Dismiss</Button>
            </Alert>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card padding="lg">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                <h2 className="text-lg font-semibold text-[#0b2b43]">Thread list</h2>
                {companyFilter && threads.length > 0 && (
                  <div className="flex flex-wrap items-center gap-2">
                    <label className="text-sm text-[#6b7280]">Group by</label>
                    <select
                      value={groupBy}
                      onChange={(e) => setGroupBy(e.target.value as GroupBy)}
                      className="border border-[#d1d5db] rounded px-2 py-1 text-sm"
                    >
                      <option value="thread">Thread</option>
                      <option value="person">Person</option>
                      <option value="role">Role</option>
                    </select>
                    {groupBy !== 'thread' && (
                      <>
                        <Button variant="outline" size="sm" onClick={expandAll}>Expand all</Button>
                        <Button variant="outline" size="sm" onClick={collapseAll}>Collapse all</Button>
                      </>
                    )}
                  </div>
                )}
              </div>
              {!companyFilter ? (
                <div className="p-8 text-center text-[#6b7280] border border-dashed border-[#e5e7eb] rounded-lg bg-[#f9fafb]">
                  Select a company above to view conversations.
                </div>
              ) : loading && threads.length === 0 ? (
                <div className="p-8 text-center text-[#6b7280]">Loading…</div>
              ) : threads.length === 0 ? (
                <div className="p-8 text-center text-[#6b7280]">No conversations found for this company.</div>
              ) : (
                <div className="space-y-1 max-h-[480px] overflow-y-auto">
                  {groupBy === 'thread' ? (
                    <div className="rounded-lg border border-[#e5e7eb] divide-y divide-[#e5e7eb]">
                      {threads.map((t) => (
                        <ThreadRow
                          key={`${t.thread_type}-${t.thread_id}`}
                          thread={t}
                          isSelected={
                            selectedThread?.thread_id === t.thread_id &&
                            selectedThread?.thread_type === t.thread_type
                          }
                          onSelect={() => loadThreadDetail(t)}
                          formatTimeAgo={formatTimeAgo}
                        />
                      ))}
                    </div>
                  ) : (
                    groupKeys.map((groupKey) => {
                      const group = groups.get(groupKey)!;
                      const expanded = isGroupExpanded(groupKey);
                      return (
                        <div key={groupKey} className="rounded-lg border border-[#e5e7eb] overflow-hidden">
                          <button
                            type="button"
                            onClick={() => toggleGroup(groupKey)}
                            className="w-full flex items-center justify-between gap-2 px-3 py-2 bg-[#f8fafc] hover:bg-[#f1f5f9] text-left text-sm font-medium text-[#0b2b43]"
                          >
                            <span className="truncate">{group.label}</span>
                            <span className="text-[#6b7280] shrink-0">
                              {group.threads.length} thread{group.threads.length !== 1 ? 's' : ''}
                            </span>
                            <span className="text-[#6b7280] shrink-0">{expanded ? '▼' : '▶'}</span>
                          </button>
                          {expanded && (
                            <div className="divide-y divide-[#e5e7eb]">
                              {group.threads.map((t) => (
                                <ThreadRow
                                  key={`${t.thread_type}-${t.thread_id}`}
                                  thread={t}
                                  isSelected={
                                    selectedThread?.thread_id === t.thread_id &&
                                    selectedThread?.thread_type === t.thread_type
                                  }
                                  onSelect={() => loadThreadDetail(t)}
                                  formatTimeAgo={formatTimeAgo}
                                />
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              )}
            </Card>

            <Card padding="lg">
              <h2 className="text-lg font-semibold text-[#0b2b43] mb-4">Conversation</h2>
              {!selectedThread && (
                <div className="p-8 text-center text-[#6b7280]">Select a conversation to view details.</div>
              )}
              {selectedThread && detailLoading && (
                <div className="p-8 text-center text-[#6b7280]">Loading...</div>
              )}
              {selectedThread && !detailLoading && (
                <div className="space-y-4">
                  <div className="border-b border-[#e5e7eb] pb-3">
                    <div className="text-sm text-[#6b7280]">Company</div>
                    <div className="font-medium">{threadDetail?.company_name ?? selectedThread.company_name ?? '—'}</div>
                    <div className="text-sm text-[#6b7280] mt-1">Participants</div>
                    <div>{(threadDetail?.participants ?? selectedThread.participants ?? []).join(', ')}</div>
                    {selectedThread.thread_type === 'hr_employee' && selectedThread.assignment_id && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-2"
                        onClick={() => navigate(ROUTE_DEFS.hrAssignmentReview.path.replace(':id', selectedThread.assignment_id!))}
                      >
                        Open assignment
                      </Button>
                    )}
                  </div>

                  <div>
                    <div className="text-sm font-medium text-[#374151] mb-2">Conversation</div>
                    <div className="space-y-2 max-h-[280px] overflow-y-auto">
                      {threadDetail?.messages?.map((m) => (
                        <div key={m.id} className="rounded bg-[#f1f5f9] p-2 text-sm">
                          <div className="flex justify-between text-xs text-[#6b7280] mb-1">
                            <span>{m.sender_display_name || 'Unknown'}</span>
                            <span>{formatDate(m.created_at)}</span>
                          </div>
                          <div className="whitespace-pre-wrap break-words">{m.body}</div>
                        </div>
                      ))}
                      {collabComments.map((c) => (
                        <div key={c.id} className="rounded bg-[#f1f5f9] p-2 text-sm">
                          <div className="flex justify-between text-xs text-[#6b7280] mb-1">
                            <span>{c.author_display_name || 'Unknown'}</span>
                            <span>{formatDate(c.created_at)}</span>
                          </div>
                          <div className="whitespace-pre-wrap break-words">{c.body}</div>
                        </div>
                      ))}
                      {threadDetail && !threadDetail.messages?.length && !collabComments.length && (
                        <div className="text-sm text-[#6b7280]">No messages.</div>
                      )}
                    </div>
                  </div>

                  <div className="pt-3 border-t border-[#e5e7eb]">
                    <div className="text-xs text-[#6b7280] mb-1">Admin note / Escalation</div>
                    <p className="text-sm text-[#9ca3af] italic">
                      Direct reply not implemented. Use the assignment or collaboration panel to respond.
                    </p>
                  </div>
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </AdminLayout>
  );
};
