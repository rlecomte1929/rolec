/**
 * AIQ-1349 — Admin queue for customer research requests (the moat's curation desk).
 * Approve/reject pending requests; mark in_progress requests complete (records the
 * invoice line + notifies the requester). Mirrors AdminCatalogQueuePage.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Card, Badge } from '../../components/antigravity';
import {
  listResearchRequests,
  resolveResearchRequest,
  completeResearchRequest,
  type ResearchRequest,
} from '../../api/researchRequests';
import { AdminLayout } from './AdminLayout';

const STATUS_TABS: { value: ResearchRequest['status']; label: string }[] = [
  { value: 'pending', label: 'Pending' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'rejected', label: 'Rejected' },
];

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export const AdminResearchRequestsPage: React.FC = () => {
  const [tab, setTab] = useState<ResearchRequest['status']>('pending');
  const [rows, setRows] = useState<ResearchRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRows(await listResearchRequests(tab));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load research requests.');
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const resolve = async (id: string, status: 'approved' | 'rejected') => {
    setBusyId(id);
    setError(null);
    try {
      const updated = await resolveResearchRequest(id, status);
      setInfo(`${status === 'approved' ? 'Approved' : 'Rejected'} ${updated.corridor}.`);
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Action failed.');
    } finally {
      setBusyId(null);
    }
  };

  const complete = async (r: ResearchRequest) => {
    const summary = window.prompt(`Publish summary for ${r.corridor} (what was researched + published):`);
    if (!summary) return;
    const costStr = window.prompt('Actual cost (optional, number):', String(r.estimated_cost ?? ''));
    const actualCost = costStr && !Number.isNaN(Number(costStr)) ? Number(costStr) : undefined;
    setBusyId(r.id);
    setError(null);
    try {
      await completeResearchRequest(r.id, summary, actualCost);
      setInfo(`Published ${r.corridor} and notified the requester.`);
      await loadAll();
    } catch (err: unknown) {
      // 409 = curation review not resolved yet
      setError(err instanceof Error ? err.message : 'Complete failed — is the curation review resolved?');
    } finally {
      setBusyId(null);
    }
  };

  const statusVariant = (s: ResearchRequest['status']) =>
    s === 'completed' ? 'success' : s === 'rejected' ? 'error' : s === 'in_progress' ? 'info' : 'warning';

  return (
    <AdminLayout>
      <div className="space-y-4">
        <h1 className="text-lg font-semibold text-[#0b2b43]">Research requests</h1>
        <p className="text-sm text-[#64748b]">
          Customer-requested immigration research. Approve to start curation; complete (after the
          curation review is resolved) to publish and notify the requester.
        </p>

        {error && <Alert variant="error">{error}</Alert>}
        {info && <Alert variant="success">{info}</Alert>}

        <div className="flex flex-wrap gap-2">
          {STATUS_TABS.map((t) => (
            <Button
              key={t.value}
              variant={tab === t.value ? 'primary' : 'outline'}
              size="sm"
              onClick={() => setTab(t.value)}
            >
              {t.label}
            </Button>
          ))}
        </div>

        {loading ? (
          <p className="py-6 text-center text-sm text-slate-500">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-500">No {tab.replace('_', ' ')} requests.</p>
        ) : (
          <Card padding="md">
            <ul className="divide-y divide-[#e2e8f0]">
              {rows.map((r) => (
                <li key={r.id} className="flex items-center justify-between gap-4 py-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-[#0b2b43]">{r.corridor}</span>
                      <Badge variant={statusVariant(r.status)} size="sm">{r.status}</Badge>
                    </div>
                    <div className="text-xs text-[#6b7280] mt-1">
                      {r.purpose || '—'} · est. {r.estimated_cost ?? '—'}
                      {r.actual_cost != null ? ` · actual ${r.actual_cost}` : ''} · {formatDate(r.created_at)}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {r.status === 'pending' && (
                      <>
                        <Button size="sm" disabled={busyId === r.id} onClick={() => void resolve(r.id, 'approved')}>
                          Approve
                        </Button>
                        <Button variant="outline" size="sm" disabled={busyId === r.id} onClick={() => void resolve(r.id, 'rejected')}>
                          Reject
                        </Button>
                      </>
                    )}
                    {r.status === 'in_progress' && (
                      <Button size="sm" disabled={busyId === r.id} onClick={() => void complete(r)}>
                        Mark complete
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </AdminLayout>
  );
};
