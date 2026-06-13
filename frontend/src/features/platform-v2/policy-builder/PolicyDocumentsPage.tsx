/**
 * [P2-8] PolicyDocumentsPage.tsx
 *
 * HR document management screen — upload history, pipeline status badges,
 * SHA-256 integrity, expandable per-category extraction summary, and
 * side-by-side version diff view.
 *
 * Route: /hr/policy-builder/documents
 */
import { useEffect, useState } from 'react';
import { Button } from '../../../components/antigravity/Button';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../../../components/AppShell';
import { HrNoCompanyOnboarding, isNoCompanyError } from '../../../features/policy/hrNoCompanyOnboarding';
import {
  policyBuilderPipelineAPI,
  type PolicyDocumentRow,
  type PipelineStatus,
  type DiffEntry,
  type DiffChangeType,
} from '../../../api/policyBuilderPipeline';

// ---------------------------------------------------------------------------
// Pipeline status badge
// ---------------------------------------------------------------------------

const PIPELINE_STATUS_LABEL: Record<PipelineStatus, string> = {
  uploaded:             'Uploaded',
  extracting_text:      'Extracting',
  text_ready:           'Text ready',
  extracting_facts:     'Classifying',
  ready_for_assistant:  'Awaiting Review',
  failed:               'Failed',
};

const PIPELINE_STATUS_STYLE: Record<PipelineStatus, string> = {
  uploaded:             'bg-slate-100 text-slate-600',
  extracting_text:      'bg-blue-100 text-blue-700',
  text_ready:           'bg-blue-100 text-blue-700',
  extracting_facts:     'bg-amber-100 text-amber-700',
  ready_for_assistant:  'bg-accent-100 text-accent-700',
  failed:               'bg-rose-100 text-rose-700',
};

function PipelineStatusBadge({
  status,
  error,
}: {
  status: PipelineStatus | null;
  error?: string | null;
}) {
  if (!status) {
    return <span className="text-slate-400 text-xs">—</span>;
  }
  const label = PIPELINE_STATUS_LABEL[status] ?? status;
  const style = PIPELINE_STATUS_STYLE[status] ?? 'bg-slate-100 text-slate-600';
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${style}`}
      title={status === 'failed' && error ? error : undefined}
    >
      {status === 'failed' && <span>⚠</span>}
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// SHA display
// ---------------------------------------------------------------------------

function ShaChip({ hash }: { hash: string | null }) {
  if (!hash) return <span className="text-slate-300 text-xs">—</span>;
  const short = hash.slice(-8);
  return (
    <code
      className="text-xs font-mono text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded cursor-help"
      title={hash}
    >
      {short}
    </code>
  );
}

// ---------------------------------------------------------------------------
// Diff view
// ---------------------------------------------------------------------------

const DIFF_STYLE: Record<DiffChangeType, string> = {
  added:     'bg-emerald-50 text-emerald-800',
  removed:   'bg-rose-50 text-rose-700 line-through',
  modified:  'bg-amber-50 text-amber-800',
  unchanged: 'text-slate-600',
};

const DIFF_INDICATOR: Record<DiffChangeType, string> = {
  added:     '+ Added',
  removed:   '− Removed',
  modified:  '~ Changed',
  unchanged: '',
};

function DiffView({
  entries,
  docAName,
  docBName,
  addedCount,
  removedCount,
  modifiedCount,
  onClose,
}: {
  entries: DiffEntry[];
  docAName: string;
  docBName: string;
  addedCount: number;
  removedCount: number;
  modifiedCount: number;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-bold text-[#0b2b43]">Version diff</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              <span className="font-medium">{docAName}</span>
              {' → '}
              <span className="font-medium">{docBName}</span>
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs font-semibold">
            <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-700">+{addedCount} added</span>
            <span className="px-2 py-0.5 rounded bg-rose-100 text-rose-700">−{removedCount} removed</span>
            <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-700">~{modifiedCount} changed</span>
            <Button unstyled
              type="button"
              onClick={onClose}
              className="ml-2 text-slate-400 hover:text-slate-700 text-xl font-bold"
              aria-label="Close diff view"
            >
              ×
            </Button>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-auto flex-1">
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 bg-[#f8fafc]">
              <tr className="border-b border-slate-200">
                <th className="py-2 px-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Category</th>
                <th className="py-2 px-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Before</th>
                <th className="py-2 px-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">After</th>
                <th className="py-2 px-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Change</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => {
                const rowStyle = entry.change_type !== 'unchanged' ? DIFF_STYLE[entry.change_type] : '';
                const formatVal = (v: string | null, u: string | null, c: string | null) => {
                  if (!v) return '—';
                  const parts = c ? [c, v] : [v];
                  if (u) parts.push(`/ ${u}`);
                  return parts.join(' ');
                };
                return (
                  <tr key={entry.category_code} className={`border-b border-slate-100 ${rowStyle}`}>
                    <td className="py-2.5 px-4">
                      <span className="text-xs font-mono text-slate-400 mr-1.5">{entry.category_code}</span>
                      <span className="font-medium">{entry.category_display_name}</span>
                    </td>
                    <td className="py-2.5 px-4 text-slate-600">
                      {formatVal(entry.value_before, entry.unit_before, entry.currency_before)}
                    </td>
                    <td className="py-2.5 px-4">
                      {formatVal(entry.value_after, entry.unit_after, entry.currency_after)}
                    </td>
                    <td className="py-2.5 px-4">
                      {entry.change_type !== 'unchanged' && (
                        <span className="text-xs font-semibold">
                          {DIFF_INDICATOR[entry.change_type]}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Document row (expandable)
// ---------------------------------------------------------------------------

function DocumentRow({
  doc,
  onCompare,
}: {
  doc: PolicyDocumentRow;
  onCompare: (doc: PolicyDocumentRow) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const uploadDate = new Date(doc.uploaded_at).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  });

  return (
    <>
      <tr className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
        {/* Expand toggle + filename */}
        <td className="py-3 px-4">
          <Button unstyled
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="flex items-center gap-2 text-left w-full group"
          >
            <svg
              className={`w-3.5 h-3.5 text-slate-400 flex-shrink-0 transition-transform ${expanded ? 'rotate-90' : ''}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
            <div>
              <div className="text-sm font-medium text-[#0b2b43] group-hover:underline">
                {doc.filename}
              </div>
              {doc.file_size_bytes && (
                <div className="text-[10px] text-slate-400">
                  {(doc.file_size_bytes / 1024).toFixed(0)} KB
                </div>
              )}
            </div>
          </Button>
        </td>

        {/* Uploaded by */}
        <td className="py-3 px-4">
          <span className="text-sm text-slate-700">{doc.uploaded_by_name ?? '—'}</span>
        </td>

        {/* Date */}
        <td className="py-3 px-4">
          <span className="text-sm text-slate-700">{uploadDate}</span>
        </td>

        {/* Hash */}
        <td className="py-3 px-4">
          <ShaChip hash={doc.sha256_hash} />
        </td>

        {/* Pipeline status */}
        <td className="py-3 px-4">
          <PipelineStatusBadge status={doc.assistant_import_status} error={doc.error_message} />
        </td>

        {/* Values extracted */}
        <td className="py-3 px-4 text-center">
          <span className="text-sm font-semibold text-slate-700">{doc.extracted_value_count}</span>
        </td>

        {/* Actions */}
        <td className="py-3 px-4">
          <Button unstyled
            type="button"
            onClick={() => onCompare(doc)}
            disabled={!doc.snapshot_id}
            className="text-xs font-medium text-[#0b2b43] hover:underline disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Compare with previous
          </Button>
        </td>
      </tr>

      {/* Expandable extraction summary */}
      {expanded && doc.category_summary.length > 0 && (
        <tr className="border-b border-slate-100 bg-slate-50/60">
          <td colSpan={7} className="px-8 py-3">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
              {doc.category_summary.map((cat) => (
                <div
                  key={cat.category_code}
                  className="bg-white rounded-lg border border-slate-200 px-3 py-2"
                >
                  <div className="flex items-start justify-between gap-1">
                    <div>
                      <div className="text-[10px] text-slate-400 font-mono">{cat.category_code}</div>
                      <div className="text-xs font-medium text-slate-700 truncate">{cat.category_display_name}</div>
                    </div>
                    {cat.confidence_score != null && (
                      <span
                        className={`text-[10px] font-bold px-1 py-0.5 rounded flex-shrink-0 ${
                          cat.confidence_score >= 0.90
                            ? 'bg-emerald-100 text-emerald-700'
                            : cat.confidence_score >= 0.70
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-rose-100 text-rose-700'
                        }`}
                      >
                        {Math.round(cat.confidence_score * 100)}%
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-600 mt-1 font-medium">
                    {cat.currency && `${cat.currency} `}
                    {cat.value ?? '—'}
                    {cat.unit && ` / ${cat.unit}`}
                  </div>
                </div>
              ))}
            </div>
          </td>
        </tr>
      )}

      {expanded && doc.category_summary.length === 0 && (
        <tr className="border-b border-slate-100 bg-slate-50/60">
          <td colSpan={7} className="px-8 py-3 text-xs text-slate-400 italic">
            No extraction summary available yet.
          </td>
        </tr>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function PolicyDocumentsPage() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<PolicyDocumentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [noCompany, setNoCompany] = useState(false);  // [T2.4] HR not linked to a company yet
  const [diffState, setDiffState] = useState<{
    entries: DiffEntry[];
    docAName: string;
    docBName: string;
    addedCount: number;
    removedCount: number;
    modifiedCount: number;
  } | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    policyBuilderPipelineAPI
      .listDocuments()
      .then((data) => setDocuments(data.documents))
      .catch((e: unknown) => {
        // [T2.4] 403 = HR not linked to a company → onboarding, not a red error banner.
        if (isNoCompanyError(e)) setNoCompany(true);
        else setError(e instanceof Error ? e.message : 'Failed to load documents');
      })
      .finally(() => setLoading(false));
  }, []);

  const handleCompare = async (doc: PolicyDocumentRow) => {
    if (!doc.snapshot_id) return;
    // Find the previous document (the one uploaded just before this one)
    const idx = documents.findIndex((d) => d.id === doc.id);
    const prev = documents[idx + 1]; // documents sorted newest-first
    if (!prev?.snapshot_id) return;

    setDiffLoading(true);
    try {
      const diff = await policyBuilderPipelineAPI.diffDocuments(prev.snapshot_id, doc.snapshot_id);
      setDiffState({
        entries: diff.entries,
        docAName: diff.document_a_name,
        docBName: diff.document_b_name,
        addedCount: diff.added_count,
        removedCount: diff.removed_count,
        modifiedCount: diff.modified_count,
      });
    } catch {
      // silently ignore — could show an inline error
    } finally {
      setDiffLoading(false);
    }
  };

  // [T2.4] HR not linked to a company yet → onboarding state, not an error banner.
  if (noCompany && !loading) {
    return (
      <AppShell>
        <div className="min-h-screen bg-[#f8fafc]">
          <div className="max-w-7xl mx-auto px-6 py-8">
            <HrNoCompanyOnboarding />
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="min-h-screen bg-[#f8fafc]">
        <div className="max-w-7xl mx-auto px-6 py-8">
          {/* Header */}
          <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
            <div>
              <h1 className="text-2xl font-bold text-[#0b2b43]">Policy Documents</h1>
              <p className="text-[#64748b] mt-1">
                Upload history, pipeline status, and version diff for all ingested policy documents.
              </p>
            </div>
            <Button unstyled
              type="button"
              onClick={() => navigate('/hr/policy-builder/review')}
              className="px-4 py-2.5 rounded-xl text-sm font-semibold bg-[#0b2b43] text-white hover:bg-[#0e3a5c] transition-colors"
            >
              Go to review queue →
            </Button>
          </div>

          {loading && (
            <div className="flex justify-center py-20 text-slate-400 text-sm">
              Loading documents…
            </div>
          )}

          {error && !loading && (
            <div className="rounded-xl bg-rose-50 border border-rose-200 px-5 py-4 text-sm text-rose-700">
              {error}
            </div>
          )}

          {!loading && !error && documents.length === 0 && (
            <div className="rounded-2xl border border-[#e2e8f0] bg-white p-12 text-center shadow-sm">
              <div className="text-4xl mb-3">📄</div>
              <h3 className="text-lg font-semibold text-[#0b2b43]">No documents yet</h3>
              <p className="text-slate-500 mt-1 text-sm">
                Upload a policy document from the Policy Builder to get started.
              </p>
            </div>
          )}

          {!loading && !error && documents.length > 0 && (
            <div className="rounded-2xl border border-[#e2e8f0] bg-white shadow-sm overflow-hidden">
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="bg-[#f8fafc] border-b border-[#e2e8f0]">
                    {['Document', 'Uploaded by', 'Date', 'SHA-256', 'Pipeline status', 'Values', 'Actions'].map((h) => (
                      <th
                        key={h}
                        className="py-3 px-4 text-xs font-semibold text-slate-500 uppercase tracking-wide"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <DocumentRow key={doc.id} doc={doc} onCompare={handleCompare} />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {diffLoading && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
              <div className="bg-white rounded-2xl px-8 py-6 text-sm text-slate-600 shadow-xl">
                Loading diff…
              </div>
            </div>
          )}

          {diffState && (
            <DiffView
              entries={diffState.entries}
              docAName={diffState.docAName}
              docBName={diffState.docBName}
              addedCount={diffState.addedCount}
              removedCount={diffState.removedCount}
              modifiedCount={diffState.modifiedCount}
              onClose={() => setDiffState(null)}
            />
          )}
        </div>
      </div>
    </AppShell>
  );
}
