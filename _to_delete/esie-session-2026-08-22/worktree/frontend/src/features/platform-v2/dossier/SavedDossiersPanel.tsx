/**
 * [P3-6] SavedDossiersPanel
 *
 * Shows a list of saved DossierPackage records for a case.
 * Each row displays: name, form count, generated_at, stale badge,
 * and action buttons: Download PDF, Download ZIP, Regenerate, Delete.
 *
 * Stale badge appears when the server returns is_stale=true (i.e. a FieldValue
 * was updated after the dossier was last generated).
 */

import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Download, FileText, Loader2, RefreshCw, Trash2 } from 'lucide-react';
import { Button } from '../../../components/antigravity/Button';
import { dossierPackageAPI, type DossierPackageDetail } from '../../../api/dossier';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SavedDossiersPanelProps {
  caseId: string;
  /** Called whenever the list changes (after delete/regenerate) so parent can refresh if needed. */
  onChanged?: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SavedDossiersPanel({ caseId, onChanged }: SavedDossiersPanelProps) {
  const [packages, setPackages] = useState<DossierPackageDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Per-package in-flight states
  const [regenerating, setRegenerating] = useState<Record<string, boolean>>({});
  const [deleting, setDeleting] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const pkgs = await dossierPackageAPI.list(caseId);
      setPackages(pkgs);
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(err.response?.data?.detail || err.message || 'Failed to load saved dossiers');
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleRegenerate = useCallback(
    async (pkg: DossierPackageDetail) => {
      setRegenerating((prev) => ({ ...prev, [pkg.id]: true }));
      try {
        const updated = await dossierPackageAPI.regenerate(caseId, pkg.id);
        setPackages((prev) => prev.map((p) => (p.id === pkg.id ? updated : p)));
        onChanged?.();
      } catch (e) {
        const err = e as { response?: { data?: { detail?: string } }; message?: string };
        alert(err.response?.data?.detail || err.message || 'Regeneration failed');
      } finally {
        setRegenerating((prev) => ({ ...prev, [pkg.id]: false }));
      }
    },
    [caseId, onChanged],
  );

  const handleDelete = useCallback(
    async (pkg: DossierPackageDetail) => {
      if (!window.confirm(`Delete "${pkg.name}"? This cannot be undone.`)) return;
      setDeleting((prev) => ({ ...prev, [pkg.id]: true }));
      try {
        await dossierPackageAPI.delete(caseId, pkg.id);
        setPackages((prev) => prev.filter((p) => p.id !== pkg.id));
        onChanged?.();
      } catch (e) {
        const err = e as { response?: { data?: { detail?: string } }; message?: string };
        alert(err.response?.data?.detail || err.message || 'Delete failed');
        setDeleting((prev) => ({ ...prev, [pkg.id]: false }));
      }
    },
    [caseId, onChanged],
  );

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500 py-4">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading saved dossiers…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
        {error}
      </div>
    );
  }

  if (packages.length === 0) {
    return (
      <div className="text-sm text-slate-500 py-4">
        No saved dossier packages yet. Use the{' '}
        <span className="font-medium text-slate-700">Build dossier</span> button to create one.
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="saved-dossiers-panel">
      {packages.map((pkg) => {
        const isRegen = !!regenerating[pkg.id];
        const isDel = !!deleting[pkg.id];
        const generatedLabel = pkg.generated_at
          ? new Date(pkg.generated_at).toLocaleString(undefined, {
              dateStyle: 'medium',
              timeStyle: 'short',
            })
          : 'Not generated yet';

        return (
          <div
            key={pkg.id}
            className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden"
            data-testid="saved-dossier-row"
          >
            {/* Header row */}
            <div className="flex items-start justify-between gap-3 px-4 py-3.5">
              <div className="flex items-start gap-3 min-w-0">
                <FileText className="h-4 w-4 text-slate-400 flex-none mt-0.5" />
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-slate-800 truncate">{pkg.name}</span>
                    {/* Stale badge */}
                    {pkg.is_stale && (
                      <span
                        data-testid="stale-badge"
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200"
                      >
                        <AlertTriangle className="h-3 w-3" />
                        Fields updated
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {pkg.form_ids.length} form{pkg.form_ids.length === 1 ? '' : 's'} · Generated {generatedLabel}
                    {pkg.cover_page ? ' · Cover page' : ''}
                  </div>
                </div>
              </div>
            </div>

            {/* Stale warning banner */}
            {pkg.is_stale && (
              <div className="mx-4 mb-3 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-800">
                <AlertTriangle className="h-3.5 w-3.5 flex-none mt-0.5" />
                <span>
                  Form fields were updated after this dossier was generated. Click{' '}
                  <strong>Regenerate</strong> to rebuild with the latest values.
                </span>
              </div>
            )}

            {/* Action bar */}
            <div className="flex flex-wrap items-center gap-2 px-4 pb-3.5">
              {/* Download PDF */}
              <a
                href={dossierPackageAPI.getPdfUrl(caseId, pkg.id)}
                download
                data-testid="download-pdf-link"
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50"
              >
                <Download className="h-3.5 w-3.5" />
                PDF
              </a>

              {/* Download ZIP */}
              <a
                href={dossierPackageAPI.getZipUrl(caseId, pkg.id)}
                download
                data-testid="download-zip-link"
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50"
              >
                <Download className="h-3.5 w-3.5" />
                ZIP
              </a>

              {/* Regenerate */}
              <Button unstyled
                type="button"
                data-testid="regenerate-button"
                disabled={isRegen || isDel}
                onClick={() => void handleRegenerate(pkg)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50 disabled:opacity-50"
              >
                {isRegen ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="h-3.5 w-3.5" />
                )}
                {isRegen ? 'Regenerating…' : 'Regenerate'}
              </Button>

              {/* Delete */}
              <Button unstyled
                type="button"
                data-testid="delete-button"
                disabled={isRegen || isDel}
                onClick={() => void handleDelete(pkg)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-xs font-medium text-red-600 shadow-sm transition-colors hover:bg-red-50 disabled:opacity-50 ml-auto"
              >
                {isDel ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Trash2 className="h-3.5 w-3.5" />
                )}
                Delete
              </Button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default SavedDossiersPanel;
