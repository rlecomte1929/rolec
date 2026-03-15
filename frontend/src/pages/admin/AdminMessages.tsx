import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AdminLayout } from './AdminLayout';
import { Card, Button, Badge, Alert } from '../../components/antigravity';
import { adminAPI, adminCollaborationAPI } from '../../api/client';
import { ROUTE_DEFS } from '../../navigation/routes';

type Thread = {
  thread_id: string;
  thread_type: 'hr_employee' | 'collaboration';
  assignment_id?: string;
  company_id?: string;
  company_name?: string;
  employee_name?: string;
  hr_name?: string;
  participants?: string[];
  last_message_preview?: string;
  last_message_at?: string;
  message_count?: number;
  status?: string;
  target_type?: string;
  target_id?: string;
  title?: string;
};

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

const THREAD_TYPES = [
  { value: '', label: 'All' },
  { value: 'hr_employee', label: 'HR–Employee' },
  { value: 'collaboration', label: 'Internal collaboration' },
];

export const AdminMessages: React.FC = () => {
  const navigate = useNavigate();
  const [threads, setThreads] = useState<Thread[]>([]);
  const [companies, setCompanies] = useState<Array<{ id: string; name: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [companyFilter, setCompanyFilter] = useState('');
  const [userFilter, setUserFilter] = useState('');
  const [threadTypeFilter, setThreadTypeFilter] = useState('');
  const [selectedThread, setSelectedThread] = useState<Thread | null>(null);
  const [threadDetail, setThreadDetail] = useState<HrThreadDetail | null>(null);
  const [collabComments, setCollabComments] = useState<Array<{ id: string; body: string; created_at: string; author_display_name?: string }>>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'threads' | 'support'>('threads');
  const [supportCases, setSupportCases] = useState<any[]>([]);

  const loadThreads = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminAPI.listMessageThreads({
        company_id: companyFilter || undefined,
        user_id: userFilter || undefined,
        thread_type: (threadTypeFilter as 'hr_employee' | 'collaboration') || undefined,
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
  }, [companyFilter, userFilter, threadTypeFilter]);

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
      const res = await adminAPI.listSupportCases();
      setSupportCases(res.support_cases || []);
    } catch {
      setSupportCases([]);
    }
  }, []);

  useEffect(() => {
    if (companyFilter) loadThreads();
    else setThreads([]);
  }, [companyFilter, loadThreads]);

  useEffect(() => {
    loadCompanies();
  }, [loadCompanies]);

  useEffect(() => {
    if (activeTab === 'support') loadSupportCases();
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
        const [, commentsRes] = await Promise.all([
          adminCollaborationAPI.getThreadById(t.thread_id),
          adminCollaborationAPI.getComments(t.thread_id),
        ]);
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

  return (
    <AdminLayout title="Messages" subtitle="Message threads and support cases — select a company to view threads">
      <div className="flex gap-2 mb-4">
        <button
          type="button"
          onClick={() => setActiveTab('threads')}
          className={`px-3 py-1.5 rounded text-sm font-medium ${activeTab === 'threads' ? 'bg-[#0b2b43] text-white' : 'bg-[#f1f5f9] text-[#4b5563] hover:bg-[#e2e8f0]'}`}
        >
          Threads
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('support')}
          className={`px-3 py-1.5 rounded text-sm font-medium ${activeTab === 'support' ? 'bg-[#0b2b43] text-white' : 'bg-[#f1f5f9] text-[#4b5563] hover:bg-[#e2e8f0]'}`}
        >
          Support cases
        </button>
      </div>

      {activeTab === 'support' && (
        <Card padding="lg">
          <div className="text-sm text-[#6b7280] mb-2">Support cases ({supportCases.length})</div>
          <div className="space-y-3">
            {supportCases.map((c) => (
              <div key={c.id} className="flex flex-wrap items-center justify-between border-b border-[#e2e8f0] py-2 gap-3">
                <div>
                  <div className="font-medium text-[#0b2b43]">{c.summary || c.id}</div>
                  <div className="text-xs text-[#6b7280]">
                    {c.category} · {c.severity} · {c.status} · Error: {c.last_error_code || '—'}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="neutral" size="sm">{c.status?.toUpperCase?.()}</Badge>
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
                    onClick={() => {
                      const reason = window.prompt('Reason for export (required):');
                      if (reason) {
                        adminAPI.adminAction('export-support-bundle', { reason, payload: { support_case_id: c.id } }).then(() => alert('Export requested.')).catch(console.error);
                      }
                    }}
                  >
                    Export bundle
                  </Button>
                </div>
              </div>
            ))}
            {supportCases.length === 0 && <div className="text-sm text-[#6b7280]">No support cases found.</div>}
          </div>
        </Card>
      )}

      {activeTab === 'threads' && (
        <>
          <Card padding="lg" className="mb-4">
          <div className="flex flex-wrap gap-4">
            <div>
              <label className="block text-sm font-medium text-[#374151] mb-1">Company</label>
              <select
                value={companyFilter}
                onChange={(e) => setCompanyFilter(e.target.value)}
                className="border border-[#d1d5db] rounded px-3 py-2 text-sm"
              >
                <option value="">Select company</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-[#374151] mb-1">User (HR or Employee ID)</label>
              <input
                type="text"
                value={userFilter}
                onChange={(e) => setUserFilter(e.target.value)}
                placeholder="User ID"
                className="border border-[#d1d5db] rounded px-3 py-2 text-sm w-40"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[#374151] mb-1">Thread type</label>
              <select
                value={threadTypeFilter}
                onChange={(e) => setThreadTypeFilter(e.target.value)}
                className="border border-[#d1d5db] rounded px-3 py-2 text-sm"
              >
                {THREAD_TYPES.map((o) => (
                  <option key={o.value || 'all'} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div className="self-end">
              <Button onClick={loadThreads} disabled={loading}>{loading ? 'Loading…' : 'Apply'}</Button>
            </div>
          </div>
          </Card>

          {error && (
            <Alert variant="error" className="mb-4">
              {error}
              <Button variant="outline" size="sm" className="ml-2" onClick={() => setError(null)}>Dismiss</Button>
            </Alert>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card padding="lg">
              <h2 className="text-lg font-semibold text-[#0b2b43] mb-4">Thread list</h2>
              {!companyFilter ? (
                <div className="p-8 text-center text-[#6b7280] border border-dashed border-[#e5e7eb] rounded-lg bg-[#f9fafb]">
                  Select a company above to view message threads.
                </div>
              ) : loading && threads.length === 0 ? (
                <div className="p-8 text-center text-[#6b7280]">Loading...</div>
              ) : threads.length === 0 ? (
                <div className="p-8 text-center text-[#6b7280]">No threads found for this company.</div>
              ) : (
                <div className="space-y-2 max-h-[480px] overflow-y-auto">
                  {threads.map((t) => (
                    <div
                      key={`${t.thread_type}-${t.thread_id}`}
                      onClick={() => loadThreadDetail(t)}
                      className={`p-3 rounded-lg border cursor-pointer ${
                        selectedThread?.thread_id === t.thread_id && selectedThread?.thread_type === t.thread_type
                          ? 'border-[#0b2b43] bg-[#f0f9ff]'
                          : 'border-[#e5e7eb] hover:bg-[#f9fafb]'
                      }`}
                    >
                      <div className="flex justify-between items-start gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="font-medium text-[#0b2b43] truncate">
                            {t.company_name || t.title || t.thread_id}
                          </div>
                          <div className="text-xs text-[#6b7280]">
                            {(t.participants || []).join(', ')}
                          </div>
                          <div className="text-sm text-[#4b5563] truncate mt-1" title={t.last_message_preview}>
                            {t.last_message_preview || '—'}
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          <Badge variant="neutral" size="sm">{t.thread_type === 'hr_employee' ? 'HR' : 'Collab'}</Badge>
                          <div className="text-xs text-[#6b7280] mt-1">{formatDate(t.last_message_at)}</div>
                          {t.status && (
                            <span className={`inline-block mt-1 px-2 py-0.5 rounded text-xs ${
                              t.status === 'open' ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-700'
                            }`}>
                              {t.status}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card padding="lg">
              <h2 className="text-lg font-semibold text-[#0b2b43] mb-4">Thread detail</h2>
              {!selectedThread && (
                <div className="p-8 text-center text-[#6b7280]">Select a thread to view details.</div>
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
