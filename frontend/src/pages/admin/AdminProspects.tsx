import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Checkbox } from '../../components/antigravity/Checkbox';
import { Alert, Badge, Button, Card } from '../../components/antigravity';
import { RefreshButton } from '../../components/RefreshButton';
import {
  adminProspectsAPI,
  API_BASE_URL,
  type ProspectRow,
  type ProspectSeedItem,
} from '../../api/client';
import { getAuthItem } from '../../utils/demo';
import { AdminLayout } from './AdminLayout';

const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'pending_enrichment', label: 'Enriching' },
  { value: 'enriched', label: 'Needs review' },
  { value: 'enrichment_failed', label: 'Failed' },
  { value: 'approved', label: 'Approved' },
  { value: 'maybe', label: 'Maybe' },
  { value: 'rejected', label: 'Rejected' },
];

const BAND_COLORS: Record<string, 'info' | 'success' | 'warning' | 'error'> = {
  hot: 'success',
  warm: 'info',
  nurture: 'warning',
  not_icp: 'error',
};

function parseSeedText(raw: string): ProspectSeedItem[] {
  const out: ProspectSeedItem[] = [];
  const lines = raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  for (const line of lines) {
    const parts = line.split(',').map((p) => p.trim());
    const [company_name, company_domain, company_linkedin_url, ...noteParts] = parts;
    if (!company_name) continue;
    out.push({
      company_name,
      company_domain: company_domain || undefined,
      company_linkedin_url: company_linkedin_url || undefined,
      notes: noteParts.length ? noteParts.join(', ') : undefined,
    });
  }
  return out;
}

function bandBadge(row: ProspectRow): React.ReactElement {
  const band = row.qualification_band || 'unknown';
  const variant = BAND_COLORS[band] || 'info';
  const label = band === 'not_icp' ? 'not ICP' : band;
  return <Badge variant={variant}>{label}</Badge>;
}

function statusBadge(status: string): React.ReactElement {
  if (status === 'pending_enrichment') return <Badge variant="info">enriching</Badge>;
  if (status === 'enriched') return <Badge variant="warning">needs review</Badge>;
  if (status === 'approved') return <Badge variant="success">approved</Badge>;
  if (status === 'maybe') return <Badge variant="info">maybe</Badge>;
  if (status === 'rejected') return <Badge variant="error">rejected</Badge>;
  if (status === 'enrichment_failed') return <Badge variant="error">failed</Badge>;
  return <Badge variant="info">{status}</Badge>;
}

export const AdminProspects: React.FC = () => {
  const [rows, setRows] = useState<ProspectRow[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Import form state
  const [seedText, setSeedText] = useState<string>('');
  const [enableWebSearch, setEnableWebSearch] = useState(false);
  const [importing, setImporting] = useState(false);
  const [lastBatchMsg, setLastBatchMsg] = useState<string | null>(null);
  const [costEstimateUsd, setCostEstimateUsd] = useState<number | null>(null);

  // Detail drawer state
  const [selected, setSelected] = useState<ProspectRow | null>(null);
  const [bulkReenriching, setBulkReenriching] = useState(false);
  const [detailBusy, setDetailBusy] = useState(false);

  // Onboard-as-company modal (Track B)
  const [onboardOpen, setOnboardOpen] = useState(false);
  const [onboardEmail, setOnboardEmail] = useState('');
  const [onboardName, setOnboardName] = useState('');
  const [onboardWelcome, setOnboardWelcome] = useState(true);
  const [onboardBusy, setOnboardBusy] = useState(false);
  const [onboardMsg, setOnboardMsg] = useState<string | null>(null);

  const parsedSeeds = useMemo(() => parseSeedText(seedText), [seedText]);
  const failedCount = useMemo(
    () => rows.filter((r) => r.status === 'enrichment_failed').length,
    [rows],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { status?: string; limit: number } = { limit: 200 };
      if (statusFilter) params.status = statusFilter;
      const res = await adminProspectsAPI.list(params);
      setRows(res.prospects ?? []);
      setTotal(res.total ?? 0);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      setError(String(msg || 'Failed to load prospects'));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  // Auto-refresh while anything is still enriching so the list animates
  // towards 'needs review' without a manual reload.
  useEffect(() => {
    const anyPending = rows.some((r) => r.status === 'pending_enrichment');
    if (!anyPending) return;
    const t = setTimeout(() => void load(), 8_000);
    return () => clearTimeout(t);
  }, [rows, load]);

  // Recompute cost estimate when enabling web search or seed list changes
  useEffect(() => {
    if (!enableWebSearch || parsedSeeds.length === 0) {
      setCostEstimateUsd(null);
      return;
    }
    let cancelled = false;
    adminProspectsAPI
      .costEstimate(parsedSeeds.length)
      .then((r) => {
        if (!cancelled) setCostEstimateUsd(r.estimated_web_search_cost_usd);
      })
      .catch(() => {
        if (!cancelled) setCostEstimateUsd(null);
      });
    return () => {
      cancelled = true;
    };
  }, [enableWebSearch, parsedSeeds.length]);

  const submitBatch = async () => {
    if (parsedSeeds.length === 0) {
      setError('Paste at least one row in format: company_name, domain, linkedin, notes');
      return;
    }
    setImporting(true);
    setError(null);
    setLastBatchMsg(null);
    try {
      const res = await adminProspectsAPI.ingestBatch({
        prospects: parsedSeeds,
        enable_web_search: enableWebSearch,
      });
      const costNote = res.enable_web_search
        ? ` (web search on, est. ~$${res.estimated_web_search_cost_usd.toFixed(2)})`
        : '';
      const dupeNote = res.skipped_duplicates > 0
        ? ` Skipped ${res.skipped_duplicates} duplicate${res.skipped_duplicates === 1 ? '' : 's'} (${res.duplicate_domains.slice(0, 5).join(', ')}${res.duplicate_domains.length > 5 ? '…' : ''}).`
        : '';
      setLastBatchMsg(
        `Queued ${res.queued} prospects for enrichment${costNote}.${dupeNote} Batch ${res.batch_id.slice(0, 8)}…`,
      );
      setSeedText('');
      await load();
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      setError(String(msg || 'Failed to ingest batch'));
    } finally {
      setImporting(false);
    }
  };

  const openDetail = async (row: ProspectRow) => {
    setSelected(row);
    try {
      const full = await adminProspectsAPI.get(row.id);
      setSelected(full);
    } catch {
      /* keep the row-lite view */
    }
  };

  const triage = async (decision: 'approved' | 'maybe' | 'rejected') => {
    if (!selected) return;
    setDetailBusy(true);
    try {
      const updated = await adminProspectsAPI.triage(selected.id, decision);
      setSelected(updated);
      await load();
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      setError(String(msg || 'Triage failed'));
    } finally {
      setDetailBusy(false);
    }
  };

  const openOnboard = () => {
    setOnboardEmail('');
    setOnboardName('');
    setOnboardWelcome(true);
    setOnboardMsg(null);
    setOnboardOpen(true);
  };

  const doOnboard = async () => {
    if (!selected) return;
    const email = onboardEmail.trim().toLowerCase();
    if (!email || !email.includes('@')) { setOnboardMsg('Enter a valid HR contact email.'); return; }
    setOnboardBusy(true);
    setOnboardMsg(null);
    try {
      const res = await adminProspectsAPI.onboard(selected.id, {
        hr_email: email,
        hr_name: onboardName.trim() || undefined,
        send_welcome: onboardWelcome,
      });
      if (res.already_onboarded) {
        setOnboardMsg('This prospect was already onboarded.');
      } else {
        setOnboardMsg(`Onboarded "${res.company_name}" — HR ${res.hr_email}${res.invite_sent ? ' (welcome invite sent)' : ''}.`);
      }
      await load();
      const refreshed = await adminProspectsAPI.get(selected.id);
      setSelected(refreshed);
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : (err as Error)?.message;
      setOnboardMsg(String(msg || 'Onboarding failed.'));
    } finally {
      setOnboardBusy(false);
    }
  };

  const removeSelected = async () => {
    if (!selected) return;
    if (!window.confirm(`Delete ${selected.company_name} from the list? This is permanent.`)) return;
    setDetailBusy(true);
    try {
      await adminProspectsAPI.remove(selected.id);
      setSelected(null);
      await load();
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      setError(String(msg || 'Delete failed'));
    } finally {
      setDetailBusy(false);
    }
  };

  const reenrich = async () => {
    if (!selected) return;
    setDetailBusy(true);
    try {
      const updated = await adminProspectsAPI.reenrich(selected.id, enableWebSearch);
      setSelected(updated);
      await load();
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      setError(String(msg || 'Re-enrich failed'));
    } finally {
      setDetailBusy(false);
    }
  };

  const reenrichAllFailed = async () => {
    if (bulkReenriching) return;
    if (failedCount === 0) return;
    if (!window.confirm(`Re-run enrichment on ${failedCount} failed prospects?`)) return;
    setBulkReenriching(true);
    setError(null);
    try {
      const res = await adminProspectsAPI.reenrichFailed(enableWebSearch);
      setLastBatchMsg(
        `Re-queued ${res.reenriched} prospects${
          res.enable_web_search
            ? ` (web search on, est. ~$${res.estimated_web_search_cost_usd.toFixed(2)})`
            : ''
        }.`,
      );
      await load();
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      setError(String(msg || 'Bulk re-enrich failed'));
    } finally {
      setBulkReenriching(false);
    }
  };

  const exportApproved = async () => {
    // Fetch the CSV with the admin bearer token, then trigger a client-side
    // download — `window.open` can't carry auth headers.
    const token = getAuthItem('relopass_token') || '';
    try {
      const resp = await fetch(`${API_BASE_URL}/api/admin/prospects/export.csv?status=approved`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!resp.ok) {
        setError(`Export failed (HTTP ${resp.status})`);
        return;
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `prospects_approved_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError((err as Error)?.message || 'Export failed');
    }
  };

  return (
    <AdminLayout
      title="HR Prospect Pipeline"
      subtitle="Seed → enrich → triage. Approved prospects export to CSV for outreach."
    >
      {error && (
        <div className="mb-4">
          <Alert variant="error">{error}</Alert>
        </div>
      )}

      <Card padding="lg" className="mb-4">
        <h2 className="text-sm font-medium text-[#374151] mb-2">Import a seed batch</h2>
        <p className="text-xs text-[#6b7280] mb-3">
          One company per line: <code>company_name, domain, linkedin, notes</code> — only company_name is required.
          Example: <code>Acme Corp, acme.com, linkedin.com/company/acme, Opened Singapore office Feb</code>
        </p>
        <textarea
          className="w-full border border-[#d1d5db] rounded px-3 py-2 text-sm font-mono mb-3"
          rows={6}
          value={seedText}
          onChange={(e) => setSeedText(e.target.value)}
          placeholder="Acme Corp, acme.com&#10;Globex Ltd, globex.io, linkedin.com/company/globex, expanding in EMEA"
        />
        <div className="flex flex-wrap items-center gap-3 mb-3">
          <label className="flex items-center gap-2 text-sm text-[#374151] cursor-pointer">
            <Checkbox
              checked={enableWebSearch}
              onChange={(e) => setEnableWebSearch(e.target.checked)}
              className="h-4 w-4"
            />
            Enable web search during enrichment
          </label>
          {enableWebSearch && parsedSeeds.length > 0 && costEstimateUsd !== null && (
            <span className="text-xs text-[#6b7280]">
              ~${costEstimateUsd.toFixed(2)} for {parsedSeeds.length} prospects (Tavily, basic search)
            </span>
          )}
          <span className="text-xs text-[#6b7280]">Parsed: {parsedSeeds.length} prospects</span>
        </div>
        <Button onClick={submitBatch} disabled={importing || parsedSeeds.length === 0}>
          {importing ? 'Queuing…' : `Enqueue ${parsedSeeds.length || ''} prospects`}
        </Button>
        {lastBatchMsg && (
          <div className="mt-3 text-xs text-[#15803d]">{lastBatchMsg}</div>
        )}
      </Card>

      <Card padding="lg">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          {STATUS_FILTERS.map((f) => (
            <Button
              key={f.value || 'all'}
              variant={statusFilter === f.value ? 'primary' : 'outline'}
              size="sm"
              onClick={() => setStatusFilter(f.value)}
            >
              {f.label}
            </Button>
          ))}
          <div className="ml-auto flex items-center gap-2">
            <span className="text-xs text-[#6b7280]">{total} total</span>
            {failedCount > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={reenrichAllFailed}
                disabled={bulkReenriching}
                title={
                  enableWebSearch
                    ? 'Web search is ON for this re-run (toggle is in the import form above).'
                    : 'Web search is OFF for this re-run (toggle is in the import form above).'
                }
              >
                {bulkReenriching
                  ? 'Re-queuing…'
                  : `Re-enrich ${failedCount} failed`}
              </Button>
            )}
            <RefreshButton onClick={load} loading={loading} label="Refresh" />
            <Button variant="secondary" size="sm" onClick={exportApproved}>
              Export approved CSV
            </Button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-[#6b7280] border-b border-[#e5e7eb]">
              <tr>
                <th className="py-2 pr-3">Company</th>
                <th className="py-2 pr-3">Score</th>
                <th className="py-2 pr-3">Band</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2 pr-3">Contact title</th>
                <th className="py-2">Hook</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.id}
                  className="border-b border-[#f3f4f6] hover:bg-[#f8fafc] cursor-pointer"
                  onClick={() => openDetail(r)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); void openDetail(r); } }}
                  role="button"
                  tabIndex={0}
                >
                  <td className="py-2 pr-3">
                    <div className="font-medium text-[#0b2b43] inline-flex items-center gap-1.5">
                      {r.company_name}
                      {r.is_test ? <Badge variant="neutral" size="sm">test</Badge> : null}
                    </div>
                    {r.company_domain && (
                      <div className="text-xs text-[#6b7280]">{r.company_domain}</div>
                    )}
                  </td>
                  <td className="py-2 pr-3 font-mono">
                    {r.icp_score !== null ? r.icp_score : '—'}
                  </td>
                  <td className="py-2 pr-3">{bandBadge(r)}</td>
                  <td className="py-2 pr-3">{statusBadge(r.status)}</td>
                  <td className="py-2 pr-3 text-[#374151]">
                    {r.suggested_contact_title || '—'}
                  </td>
                  <td className="py-2 text-[#374151] max-w-md truncate">
                    {r.suggested_hook || '—'}
                  </td>
                </tr>
              ))}
              {rows.length === 0 && !loading && (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-[#6b7280]">
                    No prospects yet. Paste a seed batch above to get started.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {selected && (
        <div
          className="fixed inset-0 bg-black/30 flex justify-end z-50"
          onClick={(e) => { if (e.target === e.currentTarget) setSelected(null); }}
          onKeyDown={(e) => { if (e.key === 'Escape') setSelected(null); }}
          role="button"
          tabIndex={-1}
          aria-label="Close detail"
        >
          <div
            className="bg-white w-full max-w-xl h-full overflow-y-auto p-6 shadow-xl"
          >
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="text-xl font-semibold text-[#0b2b43]">
                  {selected.company_name}
                </h2>
                {selected.company_domain && (
                  <div className="text-sm text-[#6b7280]">
                    <a
                      href={`https://${selected.company_domain.replace(/^https?:\/\//, '')}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline"
                    >
                      {selected.company_domain}
                    </a>
                  </div>
                )}
                {selected.company_linkedin_url && (
                  <div className="text-sm text-[#6b7280]">
                    <a
                      href={selected.company_linkedin_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline"
                    >
                      LinkedIn
                    </a>
                  </div>
                )}
              </div>
              <Button unstyled
                className="text-[#6b7280] hover:text-[#0b2b43]"
                onClick={() => setSelected(null)}
                aria-label="Close"
              >
                ✕
              </Button>
            </div>

            <div className="flex items-center gap-2 mb-3">
              {statusBadge(selected.status)}
              {bandBadge(selected)}
              {selected.icp_score !== null && (
                <span className="text-sm font-mono text-[#374151]">
                  score {selected.icp_score}
                </span>
              )}
              {selected.web_search_used && (
                <Badge variant="info">web search</Badge>
              )}
            </div>

            {selected.enrichment_error && (
              <div className="mb-3">
                <Alert variant="error">{selected.enrichment_error}</Alert>
              </div>
            )}

            <section className="mb-4">
              <h3 className="text-sm font-semibold text-[#374151] mb-1">Suggested hook</h3>
              <p className="text-sm text-[#0b2b43]">
                {selected.suggested_hook || '—'}
              </p>
            </section>

            <section className="mb-4">
              <h3 className="text-sm font-semibold text-[#374151] mb-1">Suggested contact</h3>
              <p className="text-sm text-[#0b2b43]">
                {selected.suggested_contact_title || '—'}
              </p>
            </section>

            {selected.enriched && Object.keys(selected.enriched).length > 0 && (
              <section className="mb-4">
                <h3 className="text-sm font-semibold text-[#374151] mb-1">
                  Enrichment payload
                </h3>
                <pre className="text-xs bg-[#f8fafc] p-3 rounded border border-[#e5e7eb] overflow-x-auto">
                  {JSON.stringify(selected.enriched, null, 2)}
                </pre>
              </section>
            )}

            <div className="flex flex-wrap gap-2 pt-4 border-t border-[#e5e7eb]">
              <Button
                variant="primary"
                disabled={detailBusy || selected.status === 'pending_enrichment'}
                onClick={() => triage('approved')}
              >
                Approve
              </Button>
              <Button
                variant="secondary"
                disabled={detailBusy || selected.status === 'pending_enrichment'}
                onClick={() => triage('maybe')}
              >
                Maybe
              </Button>
              <Button
                variant="outline"
                disabled={detailBusy || selected.status === 'pending_enrichment'}
                onClick={() => triage('rejected')}
              >
                Reject
              </Button>
              {selected.status === 'approved' && (
                <Button variant="primary" disabled={detailBusy} onClick={openOnboard}>
                  Onboard as company →
                </Button>
              )}
              {selected.status === 'onboarded' && (
                <Badge variant="success">onboarded</Badge>
              )}
              <div className="ml-auto flex gap-2">
                <Button variant="ghost" disabled={detailBusy} onClick={reenrich}>
                  Re-enrich {enableWebSearch ? '(web search on)' : ''}
                </Button>
                <Button
                  variant="ghost"
                  disabled={detailBusy}
                  onClick={removeSelected}
                  title="Delete this prospect row entirely (different from Reject, which keeps it in the list)"
                >
                  Delete
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {onboardOpen && selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <Card className="w-[30rem] max-w-full">
            <div className="p-4 space-y-3">
              <h3 className="text-lg font-semibold text-[#0b2b43]">Onboard {selected.company_name}</h3>
              <p className="text-sm text-[#6b7280]">
                Creates a live company tenant, seats the primary HR contact, and (optionally) emails them a welcome invite.
              </p>
              <label className="block text-sm">
                <span className="text-[#374151]">HR contact email *</span>
                <input
                  type="email"
                  value={onboardEmail}
                  onChange={(e) => setOnboardEmail(e.target.value)}
                  placeholder="hr@company.com"
                  className="mt-1 w-full rounded border border-[#e2e8f0] px-3 py-2 text-sm"
                />
              </label>
              <label className="block text-sm">
                <span className="text-[#374151]">HR contact name</span>
                <input
                  type="text"
                  value={onboardName}
                  onChange={(e) => setOnboardName(e.target.value)}
                  placeholder="Optional"
                  className="mt-1 w-full rounded border border-[#e2e8f0] px-3 py-2 text-sm"
                />
              </label>
              <label className="flex items-center gap-2 text-sm text-[#374151]">
                <input type="checkbox" checked={onboardWelcome} onChange={(e) => setOnboardWelcome(e.target.checked)} />
                Send a welcome invite email to the HR contact
              </label>
              {onboardMsg && <p className="text-sm text-[#6b7280]">{onboardMsg}</p>}
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="ghost" disabled={onboardBusy} onClick={() => setOnboardOpen(false)}>Close</Button>
                <Button variant="primary" disabled={onboardBusy || !onboardEmail.includes('@')} onClick={() => void doOnboard()}>
                  {onboardBusy ? 'Onboarding…' : 'Onboard'}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </AdminLayout>
  );
};
