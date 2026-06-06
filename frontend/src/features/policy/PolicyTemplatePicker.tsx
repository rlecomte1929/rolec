/**
 * Picker modal for the HR Policy "Start from a template" card (Phase 3).
 *
 * Loads the template list from the backend, lets HR choose one, and
 * posts the selection to apply-template. If the backend responds with
 * 409 ("draft_has_rows"), surfaces a confirm step and retries with
 * `replace_existing_draft: true`.
 *
 * The modal is scoped to this single interaction — minimal, no
 * form-level state, no nested navigation. On success it fires
 * onApplied() and closes; the caller refreshes the page data.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Button } from '../../components/antigravity';
import { policyConfigMatrixAPI } from '../../api/client';

type Template = { key: string; label: string; description: string };

type Props = {
  open: boolean;
  onClose: () => void;
  onApplied: () => void;
  adminCompanyId?: string | null;
};

export const PolicyTemplatePicker: React.FC<Props> = ({
  open,
  onClose,
  onApplied,
  adminCompanyId,
}) => {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);
  const [applyingKey, setApplyingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmReplace, setConfirmReplace] = useState<Template | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    policyConfigMatrixAPI
      .hrListTemplates()
      .then((res) => {
        if (!cancelled) setTemplates(res.templates || []);
      })
      .catch(() => {
        if (!cancelled) setError('Could not load templates. Try again.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  const apply = useCallback(
    async (tpl: Template, replace: boolean) => {
      setApplyingKey(tpl.key);
      setError(null);
      try {
        await policyConfigMatrixAPI.hrApplyTemplate(
          { template_key: tpl.key, replace_existing_draft: replace },
          adminCompanyId ?? undefined
        );
        setConfirmReplace(null);
        onApplied();
        onClose();
      } catch (e: unknown) {
        const ax = e as {
          response?: {
            status?: number;
            data?: { detail?: { code?: string; message?: string } | string };
          };
        };
        const detail = ax.response?.data?.detail;
        const code =
          detail && typeof detail === 'object' && 'code' in detail
            ? (detail as { code?: string }).code
            : undefined;
        if (code === 'draft_has_rows') {
          // Switch to the confirm view — user has to explicitly accept
          // that their current draft will be overwritten.
          setConfirmReplace(tpl);
          return;
        }
        const message =
          detail && typeof detail === 'object' && 'message' in detail
            ? (detail as { message?: string }).message
            : typeof detail === 'string'
            ? detail
            : null;
        setError(message || 'Could not apply the template. Try again.');
      } finally {
        setApplyingKey(null);
      }
    },
    [adminCompanyId, onApplied, onClose]
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Choose a policy template"
      data-testid="policy-template-picker"
      onClick={() => !applyingKey && onClose()}
    >
      <div
        className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[#0b2b43]">
            Start from a template
          </h2>
          <Button unstyled
            type="button"
            onClick={onClose}
            disabled={!!applyingKey}
            className="text-slate-500 hover:text-[#0b2b43] px-2 py-1 rounded disabled:opacity-50"
            aria-label="Close template picker"
          >
            Close
          </Button>
        </div>
        <div className="p-6 overflow-y-auto flex-1">
          {error && (
            <Alert variant="error" className="mb-4">
              {error}
            </Alert>
          )}
          {loading ? (
            <p className="text-sm text-slate-600">Loading templates…</p>
          ) : confirmReplace ? (
            <div>
              <Alert variant="warning" className="mb-4">
                A draft with pending rows is already in progress for this company.
                Applying the <strong>{confirmReplace.label}</strong> template will
                replace every row in that draft. The currently-live published
                version is not affected and employees keep seeing it.
              </Alert>
              <p className="text-sm text-slate-600">
                Proceed? You can still edit individual rows in the row drawer after
                the template is applied.
              </p>
              <div className="mt-4 flex gap-2 justify-end">
                <Button
                  variant="outline"
                  onClick={() => setConfirmReplace(null)}
                  disabled={!!applyingKey}
                >
                  Keep my current draft
                </Button>
                <Button
                  onClick={() => void apply(confirmReplace, true)}
                  disabled={!!applyingKey}
                >
                  {applyingKey === confirmReplace.key
                    ? 'Replacing draft…'
                    : `Replace draft with ${confirmReplace.label}`}
                </Button>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {templates.map((tpl) => (
                <Button unstyled
                  key={tpl.key}
                  type="button"
                  onClick={() => void apply(tpl, false)}
                  disabled={!!applyingKey}
                  className="text-left p-4 rounded-lg border border-slate-200 hover:border-[#0b2b43] hover:bg-slate-50 transition disabled:opacity-60 disabled:cursor-not-allowed"
                  data-testid={`template-card-${tpl.key}`}
                >
                  <div className="text-sm font-semibold text-[#0b2b43]">
                    {tpl.label}
                  </div>
                  <p className="text-xs text-slate-600 mt-2 leading-relaxed">
                    {tpl.description}
                  </p>
                  <div className="mt-3 text-xs font-medium text-[#0b2b43]">
                    {applyingKey === tpl.key ? 'Applying…' : 'Use this template →'}
                  </div>
                </Button>
              ))}
            </div>
          )}
          <p className="text-xs text-slate-500 mt-4">
            Templates seed a fresh draft with level-tiered caps (Entry Level /
            Manager / Director / VP / C-suite). The live published version is
            unchanged — employees continue seeing the current policy until you
            publish the replacement.
          </p>
        </div>
      </div>
    </div>
  );
};
